"""
Blast radius: how far does this change reach if it goes wrong.

This is the half that security scanners do not have. checkov and tfsec read
configuration and answer "is this configured badly". Neither of them asks "what
is about to be destroyed". A plan that deletes a production database with a
perfectly configured everything else scores clean on both, and clean reads as
ship it.

So blast radius is a first class check here, and like the security checks it is
ordinary Python. Same plan in, same answer out.

Three tiers:

  severe    data that exists today will not exist afterwards, or a production
            resource is being destroyed or replaced
  elevated  a production resource is disrupted, or something with dependents is
            being replaced, but the data survives
  routine   changes in place, or changes to things that are cheap to rebuild
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .evidence import Evidence
from .plan import Plan, ResourceChange

TIER_ORDER = {"severe": 0, "elevated": 1, "routine": 2, "none": 3}


@dataclass
class ResourceImpact:
    address: str
    type: str
    action: str
    environment: str
    tier: str
    reasons: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    data_loss: bool = False
    recoverable: bool = True
    evidence: List[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "type": self.type,
            "action": self.action,
            "environment": self.environment,
            "tier": self.tier,
            "reasons": self.reasons,
            "dependents": self.dependents,
            "data_loss": self.data_loss,
            "recoverable": self.recoverable,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    def render(self) -> str:
        lines = [
            "[%s] %s  %s  (%s)" % (self.tier.upper(), self.action, self.address, self.environment)
        ]
        for reason in self.reasons:
            lines.append("  %s" % reason)
        if self.dependents:
            lines.append("  other resources that reference it: %s" % ", ".join(self.dependents))
        for item in self.evidence:
            lines.append("  evidence: %s" % item.render())
        return "\n".join(lines)


@dataclass
class BlastReport:
    impacts: List[ResourceImpact] = field(default_factory=list)
    created: int = 0
    updated: int = 0
    deleted: int = 0
    replaced: int = 0

    @property
    def worst_tier(self) -> str:
        if not self.impacts:
            return "none"
        return sorted(self.impacts, key=lambda i: TIER_ORDER.get(i.tier, 9))[0].tier

    @property
    def any_data_loss(self) -> bool:
        return any(i.data_loss for i in self.impacts)

    def notable(self) -> List[ResourceImpact]:
        return [i for i in self.impacts if i.tier in ("severe", "elevated")]

    def to_dict(self) -> dict:
        return {
            "worst_tier": self.worst_tier,
            "any_data_loss": self.any_data_loss,
            "counts": {
                "create": self.created,
                "update": self.updated,
                "delete": self.deleted,
                "replace": self.replaced,
            },
            "impacts": [i.to_dict() for i in self.impacts],
        }

    def render(self) -> str:
        header = "changes: %d create, %d update, %d replace, %d delete   worst blast radius: %s" % (
            self.created,
            self.updated,
            self.replaced,
            self.deleted,
            self.worst_tier,
        )
        notable = self.notable()
        if not notable:
            return header + "\n  (nothing destructive in this plan)"
        return header + "\n" + "\n".join(i.render() for i in notable)


def _snapshot_skipped(change: ResourceChange) -> bool:
    body = change.before if isinstance(change.before, dict) else {}
    after = change.after if isinstance(change.after, dict) else {}
    return bool(after.get("skip_final_snapshot") or body.get("skip_final_snapshot"))


def _protection_removed(change: ResourceChange) -> bool:
    before = change.before if isinstance(change.before, dict) else {}
    after = change.after if isinstance(change.after, dict) else {}
    for field_name in ("deletion_protection", "enable_deletion_protection"):
        if before.get(field_name) is True and after.get(field_name) is False:
            return True
    return False


def _bump(tier: str) -> str:
    return {"routine": "elevated", "elevated": "severe", "severe": "severe"}[tier]


def analyse_change(change: ResourceChange, plan: Plan) -> ResourceImpact:
    reasons: List[str] = []
    evidence: List[Evidence] = []
    dependents = plan.references_to(change.address)
    tier = "routine"
    data_loss = False
    recoverable = True

    action_evidence = Evidence(
        pointer=change.evidence_path("change", "actions"),
        value=change.actions,
        note="what Terraform will do to this resource",
    )

    if change.is_destructive:
        evidence.append(action_evidence)
        if change.is_stateful:
            data_loss = True
            recoverable = False
            tier = "severe"
            reasons.append(
                "%s holds data. A %s destroys the data that is in it today."
                % (change.type, change.action)
            )
            if _snapshot_skipped(change):
                recoverable = False
                reasons.append(
                    "skip_final_snapshot is true, so Terraform will not take a last backup "
                    "on the way out. Once this runs the data is gone with nothing to restore."
                )
                evidence.append(
                    Evidence(
                        pointer=change.evidence_path("change", "after", "skip_final_snapshot")
                        if isinstance(change.after, dict) and "skip_final_snapshot" in change.after
                        else change.evidence_path("change", "before", "skip_final_snapshot"),
                        value=True,
                        note="no final backup will be taken",
                    )
                )
            else:
                reasons.append(
                    "A final snapshot is configured, so a restore is possible, but it is a "
                    "restore, not a no-op."
                )
        elif change.is_disruptive:
            if change.environment == "production":
                tier = "elevated"
                reasons.append(
                    "%s serves live production traffic. A %s interrupts it while the "
                    "replacement comes up." % (change.type, change.action)
                )
            else:
                tier = "routine"
                reasons.append(
                    "%s serves traffic, but this one is %s, so a %s costs a moment of that "
                    "environment rather than a customer outage."
                    % (change.type, change.environment, change.action)
                )
        else:
            tier = "routine"
            reasons.append(
                "%s is rebuilt from code, so a %s costs time rather than data."
                % (change.type, change.action)
            )

        if change.environment == "production" and "production" not in " ".join(reasons):
            reasons.append("This resource is tagged or named as production.")

        # Dependents widen the effect, but they do not make it irreversible. Severe is
        # reserved for data that will not exist afterwards, so this bump stops at
        # elevated on purpose.
        if len(dependents) >= 2:
            if tier == "routine":
                tier = "elevated"
            reasons.append(
                "%d other resources in this plan reference it, so the effect does not "
                "stop at this resource: %s." % (len(dependents), ", ".join(dependents))
            )

    if _protection_removed(change):
        tier = _bump(tier) if tier != "severe" else "severe"
        reasons.append(
            "deletion_protection is being turned off. That guard exists to stop exactly "
            "the kind of deletion this change makes possible."
        )
        evidence.append(
            Evidence(
                pointer=change.evidence_path("change", "after", "deletion_protection"),
                value=False,
                note="deletion protection after the change",
            )
        )

    if not reasons:
        reasons.append("Changed in place. Nothing is destroyed.")

    return ResourceImpact(
        address=change.address,
        type=change.type,
        action=change.action,
        environment=change.environment,
        tier=tier,
        reasons=reasons,
        dependents=dependents,
        data_loss=data_loss,
        recoverable=recoverable,
        evidence=evidence,
    )


def analyse(plan: Plan) -> BlastReport:
    report = BlastReport()
    for change in plan.acting_changes():
        if change.action == "create":
            report.created += 1
        elif change.action == "update":
            report.updated += 1
        elif change.action == "delete":
            report.deleted += 1
        elif change.action == "replace":
            report.replaced += 1
        report.impacts.append(analyse_change(change, plan))
    report.impacts.sort(key=lambda i: (TIER_ORDER.get(i.tier, 9), i.address))
    return report
