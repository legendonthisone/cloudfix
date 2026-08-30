# CloudFix review

**Plan:** `data/plans/c05_public_database.json`
**Reviewed by:** scanner
**Model:** none, this rung uses no model

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

2 findings from the security checks. The gate blocks on high or above.

Policy rules that fired: severity gate

## What is changing

- `aws_db_instance.analytics` will be **updated** (aws_db_instance, production)
- `aws_security_group_rule.analytics_from_office` will be **created** (aws_security_group_rule, unknown)

_This rung does not analyse blast radius._

## Why

1. DB_PUBLICLY_ACCESSIBLE on aws_db_instance.analytics: Database given a public endpoint _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.publicly_accessible` = `true`  [no verification pass in this rung]
2. SG_DATABASE_PORT_OPEN on aws_security_group_rule.analytics_from_office: Database port open to the whole internet _(rule severity gate)_
   - evidence: `resource_changes[1].change.after`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `DB_PUBLICLY_ACCESSIBLE` on `aws_db_instance.analytics` (update)
  - `resource_changes[0].change.after.publicly_accessible` = `true`
- **CRITICAL** `SG_DATABASE_PORT_OPEN` on `aws_security_group_rule.analytics_from_office` (create)
  - `resource_changes[1].change.after` = `{"cidr_blocks": ["0.0.0.0/0"], "description": "BI tool access", "from_port": 5432, "protocol": "tcp", "security_group...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

