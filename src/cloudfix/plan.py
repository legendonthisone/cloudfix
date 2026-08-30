"""
Reading a Terraform plan.

A Terraform plan is the preview of what a change will actually do before it
happens. `terraform plan -out=tfplan` writes it, and `terraform show -json tfplan`
turns it into JSON. That JSON is the only input CloudFix ever takes.

Why the plan and not the .tf source files: the plan carries the ACTION. Several
of the risks that matter most, destroying a production database, replacing a live
server, are not visible in the source at all. The source says what should exist.
Only the plan says what is about to be deleted.

The shape we read, which is Terraform's own:

    {
      "format_version": "1.2",
      "terraform_version": "1.9.5",
      "resource_changes": [
        {
          "address": "aws_security_group.web",
          "type": "aws_security_group",
          "name": "web",
          "change": {
            "actions": ["create"],
            "before": null,
            "after": { ... }
          }
        }
      ],
      "configuration": { ... }        optional, used for the dependency graph
    }

Nothing here needs a Terraform install, an AWS account or the network. It is
json.load and dictionaries.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Resources that hold data. Destroying one of these is not the same event as
# destroying something that can be rebuilt from code in ninety seconds.
STATEFUL_TYPES = {
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_rds_cluster_instance",
    "aws_dynamodb_table",
    "aws_s3_bucket",
    "aws_efs_file_system",
    "aws_elasticache_cluster",
    "aws_elasticache_replication_group",
    "aws_redshift_cluster",
    "aws_docdb_cluster",
    "aws_ebs_volume",
}

# Resources whose replacement interrupts live traffic even though no data is lost.
DISRUPTIVE_TYPES = {
    "aws_instance",
    "aws_nat_gateway",
    "aws_lb",
    "aws_alb",
    "aws_eip",
    "aws_ecs_service",
    "aws_eks_node_group",
    "aws_launch_template",
    "aws_autoscaling_group",
}

PRODUCTION_WORDS = ("prod", "production", "live")
STAGING_WORDS = ("stage", "staging", "uat", "preprod", "pre-prod")
DEVELOPMENT_WORDS = ("dev", "develop", "development", "sandbox", "test", "qa", "scratch")


class PlanError(ValueError):
    pass


@dataclass
class ResourceChange:
    """One resource in the plan, plus the things every check wants to know."""

    index: int
    address: str
    type: str
    name: str
    actions: List[str]
    before: Optional[Dict[str, Any]]
    after: Optional[Dict[str, Any]]
    raw: Dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def action(self) -> str:
        """The plan's actions list, collapsed to one word a human would use.

        Terraform writes a replacement as two actions, ["delete", "create"] or
        ["create", "delete"] when the resource is created before it is destroyed.
        Both mean the same thing to a reviewer: the existing resource goes away.
        """
        actions = [a for a in self.actions]
        if actions in (["delete", "create"], ["create", "delete"]):
            return "replace"
        if len(actions) == 1:
            return actions[0]
        if "delete" in actions and "create" in actions:
            return "replace"
        return "+".join(actions) if actions else "no-op"

    @property
    def is_destructive(self) -> bool:
        return self.action in ("delete", "replace")

    @property
    def is_stateful(self) -> bool:
        return self.type in STATEFUL_TYPES

    @property
    def is_disruptive(self) -> bool:
        return self.type in DISRUPTIVE_TYPES

    @property
    def tags(self) -> Dict[str, str]:
        source = self.after if isinstance(self.after, dict) else (self.before or {})
        tags = source.get("tags") or source.get("tags_all") or {}
        return {str(k): str(v) for k, v in tags.items()} if isinstance(tags, dict) else {}

    @property
    def environment(self) -> str:
        """production, staging, development or unknown.

        Read from tags first because a tag is a deliberate statement. Fall back to
        the resource address and name, which is how these things are labelled in
        practice. Never guessed by a model, so it is the same on every run.
        """
        for key in ("Environment", "environment", "Env", "env", "Stage", "stage"):
            value = self.tags.get(key)
            if value:
                lowered = value.strip().lower()
                # Order matters. "preprod" contains "prod", so the narrower words
                # are tested first or every pre-production environment reads as
                # production and every warning becomes a blocked deploy.
                if any(word in lowered for word in STAGING_WORDS):
                    return "staging"
                if any(word in lowered for word in DEVELOPMENT_WORDS):
                    return "development"
                if any(word in lowered for word in PRODUCTION_WORDS):
                    return "production"

        haystack = ("%s %s" % (self.address, self.name)).lower()
        name_source = self.after if isinstance(self.after, dict) else (self.before or {})
        for key in ("name", "identifier", "bucket", "function_name", "cluster_name"):
            value = name_source.get(key)
            if isinstance(value, str):
                haystack += " " + value.lower()

        # Longest words first, so "preprod" is not read as "prod".
        for word in STAGING_WORDS:
            if word in haystack:
                return "staging"
        for word in DEVELOPMENT_WORDS:
            if word in haystack:
                return "development"
        for word in PRODUCTION_WORDS:
            if word in haystack:
                return "production"
        return "unknown"

    def evidence_path(self, *parts) -> str:
        """Build a pointer into the original plan JSON, for example
        resource_changes[3].change.after.publicly_accessible"""
        path = "resource_changes[%d]" % self.index
        for part in parts:
            if isinstance(part, int):
                path += "[%d]" % part
            else:
                path += "." + str(part)
        return path

    def summary(self) -> str:
        return "%s %s (%s, %s)" % (self.action, self.address, self.type, self.environment)


@dataclass
class Plan:
    path: str
    raw: Dict[str, Any] = field(repr=False, default_factory=dict)
    changes: List[ResourceChange] = field(default_factory=list)

    @property
    def terraform_version(self) -> str:
        return str(self.raw.get("terraform_version", "unknown"))

    def acting_changes(self) -> List[ResourceChange]:
        """Everything except no-ops and reads. These are the changes under review."""
        return [c for c in self.changes if c.action not in ("no-op", "read")]

    def references_to(self, address: str) -> List[str]:
        """Which other resources name this one in the plan's configuration block.

        Terraform records the references it resolved while building the plan. When
        the block is present this gives a real dependency count rather than a
        guess. When it is absent the answer is an empty list and every caller
        treats that as unknown rather than as zero risk.
        """
        config = self.raw.get("configuration") or {}
        module = config.get("root_module") or {}
        found = []
        for resource in module.get("resources") or []:
            resource_address = resource.get("address", "")
            if resource_address == address:
                continue
            expressions = resource.get("expressions") or {}
            if _mentions(expressions, address):
                found.append(resource_address)
        return sorted(set(found))

    def to_summary_text(self) -> str:
        """A compact human readable listing, used in prompts and in the CLI."""
        lines = []
        for change in self.acting_changes():
            lines.append("  %-9s %-46s %s" % (change.action, change.address, change.environment))
        return "\n".join(lines) if lines else "  (no changes)"


def _mentions(node: Any, address: str) -> bool:
    """Does this expressions blob reference the given resource address."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "references":
                for reference in value or []:
                    if reference == address or str(reference).startswith(address + "."):
                        return True
            elif _mentions(value, address):
                return True
        return False
    if isinstance(node, list):
        return any(_mentions(item, address) for item in node)
    return False


def load_plan(path: str) -> Plan:
    if not os.path.exists(path):
        raise PlanError("No plan file at %s" % path)
    with open(path, "r", encoding="utf-8") as handle:
        try:
            raw = json.load(handle)
        except ValueError as exc:
            raise PlanError("%s is not valid JSON: %s" % (path, exc)) from exc
    return parse_plan(raw, path=path)


def parse_plan(raw: Dict[str, Any], path: str = "<memory>") -> Plan:
    if not isinstance(raw, dict):
        raise PlanError("A Terraform plan must be a JSON object, got %s" % type(raw).__name__)
    resource_changes = raw.get("resource_changes")
    if resource_changes is None:
        raise PlanError(
            "This JSON has no resource_changes list, so it is not the output of "
            "terraform show -json. %s" % path
        )
    if not isinstance(resource_changes, list):
        raise PlanError("resource_changes must be a list. %s" % path)

    changes = []
    for index, entry in enumerate(resource_changes):
        if not isinstance(entry, dict):
            raise PlanError("resource_changes[%d] is not an object. %s" % (index, path))
        change = entry.get("change") or {}
        actions = change.get("actions") or []
        if not isinstance(actions, list):
            raise PlanError("resource_changes[%d].change.actions must be a list" % index)
        address = entry.get("address") or entry.get("type", "unknown") + ".unnamed"
        changes.append(
            ResourceChange(
                index=index,
                address=address,
                type=entry.get("type", "unknown"),
                name=entry.get("name", ""),
                actions=[str(a) for a in actions],
                before=change.get("before"),
                after=change.get("after"),
                raw=entry,
            )
        )
    return Plan(path=path, raw=raw, changes=changes)
