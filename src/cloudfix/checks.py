"""
The deterministic security checks.

Every function in this file is ordinary Python. Same plan in, same findings out,
every single time, like a calculator. No model is involved anywhere here.

That split is the whole design. The checks establish facts. The agent above them
does the judging: which facts matter here, how far the damage reaches, and what a
human should do about it. Keeping the facts in code is what makes the primary
metric objective and what lets a judge reproduce the numbers exactly.

Two rules every check follows, and both of them are the difference between this
and a text scanner:

  1. Read the AFTER state, not the file. A plan that REMOVES an open SSH rule
     has "0.0.0.0/0" sitting in its text, and a scanner that greps will flag it.
     The after state is what will exist once the change is applied, so a rule
     being closed produces no finding.

  2. Say whether the change introduced the problem. A risk that was already
     there before this plan is a real risk, but it is not this deploy's fault,
     and blocking a deploy for it is how a tool trains people to ignore it.
     Those findings are reported one severity lower and labelled.
"""

import json
from typing import Any, Dict, Iterable, List, Tuple

from .evidence import Evidence, Finding, sort_findings
from .plan import Plan, ResourceChange

WORLD_CIDRS = ("0.0.0.0/0", "::/0")

ADMIN_PORTS = {22: "SSH", 3389: "RDP", 23: "Telnet", 5985: "WinRM", 5986: "WinRM"}
DATABASE_PORTS = {
    3306: "MySQL",
    5432: "PostgreSQL",
    1433: "SQL Server",
    27017: "MongoDB",
    6379: "Redis",
    9200: "Elasticsearch",
    5984: "CouchDB",
    11211: "Memcached",
}

SEVERITY_STEP_DOWN = {"critical": "high", "high": "medium", "medium": "low", "low": "low"}


def _lower(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _world_facing(rule: Dict[str, Any]) -> Tuple[bool, str, str]:
    """Does this rule open to the whole internet. Returns (yes, cidr, field name)."""
    for field in ("cidr_blocks", "ipv6_cidr_blocks"):
        for cidr in _as_list(rule.get(field)):
            if str(cidr) in WORLD_CIDRS:
                return True, str(cidr), field
    for field in ("cidr_ipv4", "cidr_ipv6"):
        value = rule.get(field)
        if value is not None and str(value) in WORLD_CIDRS:
            return True, str(value), field
    return False, "", ""


def _port_range(rule: Dict[str, Any]) -> Tuple[int, int, str]:
    protocol = _lower(rule.get("protocol", rule.get("ip_protocol", "")))
    if protocol in ("-1", "all", "any"):
        return 0, 65535, protocol or "-1"
    try:
        low = int(rule.get("from_port")) if rule.get("from_port") is not None else 0
    except (TypeError, ValueError):
        low = 0
    try:
        high = int(rule.get("to_port")) if rule.get("to_port") is not None else 65535
    except (TypeError, ValueError):
        high = 65535
    if high < low:
        low, high = high, low
    return low, high, protocol or "tcp"


def _ingress_rules(change: ResourceChange, state: str = "after") -> Iterable[Tuple[str, Dict[str, Any]]]:
    """Yield (evidence pointer prefix, rule dict) for every inbound rule.

    Three Terraform resource types express the same idea, so all three are read:
    the ingress blocks inside aws_security_group, the standalone
    aws_security_group_rule, and the newer aws_vpc_security_group_ingress_rule.
    """
    body = change.after if state == "after" else change.before
    if not isinstance(body, dict):
        return

    if change.type == "aws_security_group":
        for position, rule in enumerate(_as_list(body.get("ingress"))):
            if isinstance(rule, dict):
                yield change.evidence_path("change", state, "ingress", position), rule

    elif change.type == "aws_security_group_rule":
        if _lower(body.get("type")) in ("", "ingress"):
            yield change.evidence_path("change", state), body

    elif change.type in ("aws_vpc_security_group_ingress_rule",):
        yield change.evidence_path("change", state), body


def _rule_signature(rule: Dict[str, Any]) -> str:
    low, high, protocol = _port_range(rule)
    _, cidr, _ = _world_facing(rule)
    return "%s:%s-%s:%s" % (protocol, low, high, cidr)


def _preexisting(change: ResourceChange, rule: Dict[str, Any]) -> bool:
    """Was an identical open rule already in place before this change."""
    signature = _rule_signature(rule)
    for _, before_rule in _ingress_rules(change, state="before"):
        if _rule_signature(before_rule) == signature:
            return True
    return False


def _adjust(severity: str, preexisting: bool) -> str:
    return SEVERITY_STEP_DOWN[severity] if preexisting else severity


def _preexisting_note(preexisting: bool) -> str:
    if not preexisting:
        return ""
    return (
        " This exposure was already present before the change, so it is not "
        "introduced by this deploy. Reported one severity lower for that reason."
    )


# ---------------------------------------------------------------------------
# check 1: inbound ports open to the entire internet
# ---------------------------------------------------------------------------

def check_open_security_groups(plan: Plan) -> List[Finding]:
    findings = []
    for change in plan.acting_changes():
        if change.action == "delete":
            continue  # nothing will exist afterwards, so nothing is exposed
        for pointer, rule in _ingress_rules(change):
            open_to_world, cidr, cidr_field = _world_facing(rule)
            if not open_to_world:
                continue
            low, high, protocol = _port_range(rule)
            preexisting = _preexisting(change, rule)
            span = high - low

            evidence = [
                Evidence(pointer=pointer, value=rule, note="the inbound rule as it will exist"),
            ]

            if protocol in ("-1", "all", "any") or (low == 0 and high >= 65535):
                findings.append(
                    Finding(
                        check_id="SG_ALL_PORTS_OPEN",
                        title="Every inbound port open to the whole internet",
                        severity=_adjust("critical", preexisting),
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "This security group accepts traffic on every port from %s. "
                            "Anything it protects is reachable by anyone."
                            % cidr
                        ) + _preexisting_note(preexisting),
                        evidence=evidence,
                        introduced_by_change=not preexisting,
                    )
                )
                continue

            hit_admin = [p for p in ADMIN_PORTS if low <= p <= high]
            hit_database = [p for p in DATABASE_PORTS if low <= p <= high]

            if hit_admin:
                names = ", ".join("%s (%d)" % (ADMIN_PORTS[p], p) for p in sorted(hit_admin))
                findings.append(
                    Finding(
                        check_id="SG_ADMIN_PORT_OPEN",
                        title="Remote administration port open to the whole internet",
                        severity=_adjust("critical", preexisting),
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "Ports %d to %d are open to %s, which covers %s. Remote login "
                            "should never be reachable from every address on the internet."
                            % (low, high, cidr, names)
                        ) + _preexisting_note(preexisting),
                        evidence=evidence,
                        introduced_by_change=not preexisting,
                    )
                )

            if hit_database:
                names = ", ".join("%s (%d)" % (DATABASE_PORTS[p], p) for p in sorted(hit_database))
                findings.append(
                    Finding(
                        check_id="SG_DATABASE_PORT_OPEN",
                        title="Database port open to the whole internet",
                        severity=_adjust("critical", preexisting),
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "Ports %d to %d are open to %s, which covers %s. A database "
                            "port reachable from the internet is a direct path to the data."
                            % (low, high, cidr, names)
                        ) + _preexisting_note(preexisting),
                        evidence=evidence,
                        introduced_by_change=not preexisting,
                    )
                )

            if not hit_admin and not hit_database and span > 100:
                findings.append(
                    Finding(
                        check_id="SG_WIDE_RANGE_OPEN",
                        title="Wide port range open to the whole internet",
                        severity=_adjust("medium", preexisting),
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "Ports %d to %d, a span of %d ports, are open to %s. Public web "
                            "ports are normal. A wide range is not."
                            % (low, high, span + 1, cidr)
                        ) + _preexisting_note(preexisting),
                        evidence=evidence,
                        introduced_by_change=not preexisting,
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# check 2: S3 buckets readable by the public
# ---------------------------------------------------------------------------

PUBLIC_ACLS = ("public-read", "public-read-write", "authenticated-read")


def check_public_s3(plan: Plan) -> List[Finding]:
    findings = []
    for change in plan.acting_changes():
        if change.action == "delete" or not isinstance(change.after, dict):
            continue
        after = change.after

        if change.type == "aws_s3_bucket_acl":
            acl = _lower(after.get("acl"))
            if acl in PUBLIC_ACLS:
                findings.append(
                    Finding(
                        check_id="S3_PUBLIC_ACL",
                        title="S3 bucket granted a public access control list",
                        severity="critical" if acl != "authenticated-read" else "high",
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "The bucket ACL is set to %r, which makes its objects readable "
                            "outside the account." % acl
                        ),
                        evidence=[
                            Evidence(
                                pointer=change.evidence_path("change", "after", "acl"),
                                value=after.get("acl"),
                                note="the access control list being applied",
                            )
                        ],
                    )
                )

        elif change.type == "aws_s3_bucket_public_access_block":
            flags = {
                key: after.get(key)
                for key in (
                    "block_public_acls",
                    "block_public_policy",
                    "ignore_public_acls",
                    "restrict_public_buckets",
                )
            }
            disabled = [key for key, value in flags.items() if value is False]
            if disabled:
                turned_off = []
                if isinstance(change.before, dict):
                    turned_off = [k for k in disabled if change.before.get(k) is True]
                findings.append(
                    Finding(
                        check_id="S3_PUBLIC_ACCESS_UNBLOCKED",
                        title="S3 public access protections switched off",
                        severity="critical" if len(disabled) == 4 else "high",
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "%d of the 4 public access guards are false (%s). These are the "
                            "safety net that stops a bucket becoming public by accident.%s"
                            % (
                                len(disabled),
                                ", ".join(sorted(disabled)),
                                " This change is what turns them off."
                                if turned_off
                                else "",
                            )
                        ),
                        evidence=[
                            Evidence(
                                pointer=change.evidence_path("change", "after", key),
                                value=flags[key],
                                note="public access guard",
                            )
                            for key in sorted(disabled)
                        ],
                    )
                )

        elif change.type == "aws_s3_bucket_policy":
            policy = _parse_policy(after.get("policy"))
            for position, statement in enumerate(_statements(policy)):
                if _lower(statement.get("Effect")) != "allow":
                    continue
                principal = statement.get("Principal")
                is_public = principal == "*" or (
                    isinstance(principal, dict)
                    and (
                        principal.get("AWS") == "*"
                        or "*" in _as_list(principal.get("AWS"))
                    )
                )
                if not is_public:
                    continue
                conditioned = bool(statement.get("Condition"))
                findings.append(
                    Finding(
                        check_id="S3_PUBLIC_BUCKET_POLICY",
                        title="Bucket policy grants access to any principal",
                        severity="medium" if conditioned else "critical",
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            'Statement %d allows Principal "*", so anyone on the internet '
                            "can call %s on this bucket.%s"
                            % (
                                position,
                                ", ".join(str(a) for a in _as_list(statement.get("Action"))) or "the listed actions",
                                " A Condition block narrows it, so a human should confirm the "
                                "condition really is restrictive." if conditioned else "",
                            )
                        ),
                        evidence=[
                            Evidence(
                                pointer=change.evidence_path("change", "after", "policy"),
                                value=_shorten(after.get("policy")),
                                note="statement %d of the bucket policy" % position,
                            )
                        ],
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# check 3: IAM permissions that are wider than they need to be
# ---------------------------------------------------------------------------

IAM_TYPES = (
    "aws_iam_policy",
    "aws_iam_role_policy",
    "aws_iam_user_policy",
    "aws_iam_group_policy",
)


def _parse_policy(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def _statements(policy: dict) -> List[dict]:
    statements = policy.get("Statement")
    if isinstance(statements, dict):
        return [statements]
    return [s for s in _as_list(statements) if isinstance(s, dict)]


def _shorten(value, limit: int = 600):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def check_iam_wildcards(plan: Plan) -> List[Finding]:
    findings = []
    for change in plan.acting_changes():
        if change.action == "delete" or change.type not in IAM_TYPES:
            continue
        if not isinstance(change.after, dict):
            continue
        policy = _parse_policy(change.after.get("policy"))
        for position, statement in enumerate(_statements(policy)):
            if _lower(statement.get("Effect")) != "allow":
                continue
            actions = [str(a) for a in _as_list(statement.get("Action"))]
            resources = [str(r) for r in _as_list(statement.get("Resource"))]
            if not actions:
                continue

            action_is_total = any(a.strip() == "*" for a in actions)
            action_is_broad = any(a.endswith(":*") for a in actions)
            resource_is_total = any(r.strip() == "*" for r in resources) or not resources

            evidence = [
                Evidence(
                    pointer=change.evidence_path("change", "after", "policy"),
                    value=_shorten(change.after.get("policy")),
                    note="statement %d: Action %s on Resource %s"
                    % (position, actions, resources or ["(none listed)"]),
                )
            ]

            if action_is_total and resource_is_total:
                findings.append(
                    Finding(
                        check_id="IAM_WILDCARD_ADMIN",
                        title="IAM policy grants every action on every resource",
                        severity="critical",
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            'Statement %d allows Action "*" on Resource "*". Whoever holds '
                            "this policy can do anything in the account, including deleting "
                            "the audit trail that would show what they did." % position
                        ),
                        evidence=evidence,
                    )
                )
            elif action_is_total or (action_is_broad and resource_is_total):
                findings.append(
                    Finding(
                        check_id="IAM_WILDCARD_WIDE",
                        title="IAM policy is wider than a single purpose needs",
                        severity="high",
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "Statement %d allows %s on %s. One side of the pair is "
                            "unbounded." % (position, actions, resources or ['"*"'])
                        ),
                        evidence=evidence,
                    )
                )
            elif action_is_broad and not resource_is_total:
                findings.append(
                    Finding(
                        check_id="IAM_BROAD_ACTION_SCOPED",
                        title="IAM policy allows a whole service, but only on named resources",
                        severity="medium",
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "Statement %d allows %s, which is every action in that service, "
                            "but the Resource list is bounded to %s. Broad, and worth a "
                            "human decision, but not unlimited."
                            % (position, actions, resources)
                        ),
                        evidence=evidence,
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# check 4: encryption switched off or never switched on
# ---------------------------------------------------------------------------

ENCRYPTION_FIELDS = {
    "aws_db_instance": "storage_encrypted",
    "aws_rds_cluster": "storage_encrypted",
    "aws_ebs_volume": "encrypted",
    "aws_dynamodb_table": None,  # handled through its nested block
    "aws_efs_file_system": "encrypted",
    "aws_redshift_cluster": "encrypted",
    "aws_sqs_queue": None,
}


def check_encryption(plan: Plan) -> List[Finding]:
    findings = []
    for change in plan.acting_changes():
        if change.action == "delete" or not isinstance(change.after, dict):
            continue
        after = change.after
        before = change.before if isinstance(change.before, dict) else {}

        field = ENCRYPTION_FIELDS.get(change.type)
        if field is not None and after.get(field) is False:
            was_on = before.get(field) is True
            findings.append(
                Finding(
                    check_id="ENCRYPTION_REMOVED" if was_on else "ENCRYPTION_DISABLED",
                    title=(
                        "Encryption at rest turned off by this change"
                        if was_on
                        else "Encryption at rest is not enabled"
                    ),
                    severity="critical" if was_on else "high",
                    resource_address=change.address,
                    resource_type=change.type,
                    action=change.action,
                    environment=change.environment,
                    detail=(
                        "%s is false. %s"
                        % (
                            field,
                            "It was true before this change, so this deploy removes "
                            "encryption from data that is currently protected."
                            if was_on
                            else "The stored data will sit unencrypted on disk.",
                        )
                    ),
                    evidence=[
                        Evidence(
                            pointer=change.evidence_path("change", "after", field),
                            value=after.get(field),
                            note="encryption flag after the change",
                        )
                    ],
                )
            )

        # A KMS key removed from an otherwise encrypted resource is the same event
        # wearing a different hat.
        if before.get("kms_key_id") and after.get("kms_key_id") in (None, ""):
            if change.type in ENCRYPTION_FIELDS:
                findings.append(
                    Finding(
                        check_id="ENCRYPTION_KEY_REMOVED",
                        title="Customer managed encryption key removed",
                        severity="high",
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "kms_key_id was set before this change and is empty after it."
                        ),
                        evidence=[
                            Evidence(
                                pointer=change.evidence_path("change", "before", "kms_key_id"),
                                value=before.get("kms_key_id"),
                                note="the key in use before the change",
                            )
                        ],
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# check 5: databases reachable from outside the network
# ---------------------------------------------------------------------------

DATABASE_TYPES = (
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_rds_cluster_instance",
    "aws_redshift_cluster",
    "aws_docdb_cluster",
)


def check_public_database(plan: Plan) -> List[Finding]:
    findings = []
    for change in plan.acting_changes():
        if change.action == "delete" or change.type not in DATABASE_TYPES:
            continue
        if not isinstance(change.after, dict):
            continue
        if change.after.get("publicly_accessible") is True:
            before = change.before if isinstance(change.before, dict) else {}
            was_private = before.get("publicly_accessible") is False
            findings.append(
                Finding(
                    check_id="DB_PUBLICLY_ACCESSIBLE",
                    title="Database given a public endpoint",
                    severity="critical",
                    resource_address=change.address,
                    resource_type=change.type,
                    action=change.action,
                    environment=change.environment,
                    detail=(
                        "publicly_accessible is true, so this database gets an address that "
                        "resolves from the public internet.%s"
                        % (
                            " It was private before this change."
                            if was_private
                            else ""
                        )
                    ),
                    evidence=[
                        Evidence(
                            pointer=change.evidence_path("change", "after", "publicly_accessible"),
                            value=True,
                            note="public endpoint flag after the change",
                        )
                    ],
                )
            )
    return findings


# ---------------------------------------------------------------------------
# check 6: the guards that protect data from being deleted
# ---------------------------------------------------------------------------
#
# This check exists because of a fact found while fact checking the README, and
# it is here to keep the comparison honest rather than because CloudFix needs it.
#
# The claim in an earlier draft was that a security scanner comes back completely
# clean on the production database replacement. That was too strong. checkov
# ships RDSDeletionProtection.py, a configuration policy for exactly this flag,
# so a real scanner does see one line of that plan. The scanner rung in this
# project is supposed to be at least as strong as the real tools, and without
# this check it was weaker than checkov on the one case used as the headline.
#
# So the scanner gets it. What no configuration policy composes is the sentence
# that decides the deploy: a production database is being REPLACED, and the final
# snapshot is skipped, so the data is gone. The flag and the consequence are not
# the same thing, and only one of them is a decision. blast.py reads the same two
# fields and reaches that second conclusion. Both are in this repository on
# purpose, and the difference between them is the whole argument.

GUARDED_TYPES = DATABASE_TYPES + ("aws_lb", "aws_alb", "aws_dynamodb_table")


def check_data_guards(plan: Plan) -> List[Finding]:
    findings = []
    for change in plan.acting_changes():
        if change.action == "delete" or not isinstance(change.after, dict):
            continue
        if change.type not in GUARDED_TYPES:
            continue
        after = change.after
        before = change.before if isinstance(change.before, dict) else {}

        for field in ("deletion_protection", "enable_deletion_protection"):
            if after.get(field) is False:
                turned_off = before.get(field) is True
                findings.append(
                    Finding(
                        check_id="DELETION_PROTECTION_DISABLED",
                        title="Deletion protection is not enabled",
                        severity="medium",
                        resource_address=change.address,
                        resource_type=change.type,
                        action=change.action,
                        environment=change.environment,
                        detail=(
                            "%s is false.%s This is the guard that stops an accidental "
                            "destroy from succeeding."
                            % (
                                field,
                                " This change is what turns it off." if turned_off else "",
                            )
                        ),
                        evidence=[
                            Evidence(
                                pointer=change.evidence_path("change", "after", field),
                                value=False,
                                note="deletion protection after the change",
                            )
                        ],
                        introduced_by_change=turned_off,
                    )
                )

        if change.type in DATABASE_TYPES and after.get("skip_final_snapshot") is True:
            turned_on = before.get("skip_final_snapshot") is False
            findings.append(
                Finding(
                    check_id="FINAL_SNAPSHOT_SKIPPED",
                    title="No final snapshot will be taken",
                    severity="medium",
                    resource_address=change.address,
                    resource_type=change.type,
                    action=change.action,
                    environment=change.environment,
                    detail=(
                        "skip_final_snapshot is true.%s If this resource is ever "
                        "destroyed there is no backup taken on the way out."
                        % (" This change is what turns it on." if turned_on else "")
                    ),
                    evidence=[
                        Evidence(
                            pointer=change.evidence_path("change", "after", "skip_final_snapshot"),
                            value=True,
                            note="final snapshot setting after the change",
                        )
                    ],
                    introduced_by_change=turned_on,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# check 7: container workloads running with host level privilege
# ---------------------------------------------------------------------------

def check_kubernetes_privilege(plan: Plan) -> List[Finding]:
    findings = []
    for change in plan.acting_changes():
        if change.action == "delete" or not isinstance(change.after, dict):
            continue
        if not change.type.startswith("kubernetes_"):
            continue

        hits = _find_privilege_flags(change.after, change.evidence_path("change", "after"))
        for pointer, label, value in hits:
            findings.append(
                Finding(
                    check_id="K8S_PRIVILEGED_WORKLOAD",
                    title="Container workload asks for host level privilege",
                    severity="critical" if label in ("privileged", "host_pid") else "high",
                    resource_address=change.address,
                    resource_type=change.type,
                    action=change.action,
                    environment=change.environment,
                    detail=(
                        "%s is %s. A container with this setting can reach past its own "
                        "boundary onto the node it runs on, which means a single "
                        "compromised image becomes a compromised host."
                        % (label, value)
                    ),
                    evidence=[
                        Evidence(pointer=pointer, value=value, note="privilege flag on the workload")
                    ],
                )
            )
    return findings


PRIVILEGE_FLAGS = ("privileged", "host_network", "host_pid", "host_ipc", "allow_privilege_escalation")


def _find_privilege_flags(node: Any, pointer: str, depth: int = 0):
    """Walk the nested spec blocks looking for the host privilege switches."""
    out = []
    if depth > 12:
        return out
    if isinstance(node, dict):
        for key, value in node.items():
            child = "%s.%s" % (pointer, key)
            if key in PRIVILEGE_FLAGS and value is True:
                out.append((child, key, value))
            else:
                out.extend(_find_privilege_flags(value, child, depth + 1))
    elif isinstance(node, list):
        for position, item in enumerate(node):
            out.extend(_find_privilege_flags(item, "%s[%d]" % (pointer, position), depth + 1))
    return out


# ---------------------------------------------------------------------------

ALL_CHECKS = (
    ("SECURITY_GROUPS", check_open_security_groups),
    ("PUBLIC_S3", check_public_s3),
    ("IAM_WILDCARDS", check_iam_wildcards),
    ("ENCRYPTION", check_encryption),
    ("PUBLIC_DATABASE", check_public_database),
    ("DATA_GUARDS", check_data_guards),
    ("KUBERNETES_PRIVILEGE", check_kubernetes_privilege),
)


def run_all(plan: Plan) -> List[Finding]:
    """Every check, in a fixed order, sorted by severity. Deterministic."""
    findings: List[Finding] = []
    for _, function in ALL_CHECKS:
        findings.extend(function(plan))
    return sort_findings(findings)


def findings_report(findings: List[Finding]) -> str:
    if not findings:
        return "  (no security findings)"
    return "\n\n".join(finding.render() for finding in findings)
