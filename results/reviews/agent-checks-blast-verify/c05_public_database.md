# CloudFix review

**Plan:** `data/plans/c05_public_database.json`
**Reviewed by:** agent-checks-blast-verify
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This change makes a production PostgreSQL database reachable from the public internet without authentication. The database gets a public endpoint and a security group rule opens port 5432 to 0.0.0.0/0, creating a direct path from anywhere on the internet to production data.

Policy rules that fired: D1

## What is changing

1 to create, 1 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. the production database is being given a public endpoint where it had a private one before _(rule D1)_
   - evidence: `resource_changes[0].change.after.publicly_accessible` = `true`  [verified against the plan]
2. a new security group rule opens the PostgreSQL port 5432 to the entire internet _(rule D1)_
   - evidence: `resource_changes[1].change.after.cidr_blocks` = `["0.0.0.0/0"]`  [verified against the plan]
3. this is a production database holding data, as shown by the Environment tag _(rule D1)_
   - evidence: `resource_changes[0].change.after.tags.Environment` = `production`  [verified against the plan]

## Raw findings from the deterministic checks

- **CRITICAL** `DB_PUBLICLY_ACCESSIBLE` on `aws_db_instance.analytics` (update)
  - `resource_changes[0].change.after.publicly_accessible` = `true`
- **CRITICAL** `SG_DATABASE_PORT_OPEN` on `aws_security_group_rule.analytics_from_office` (create)
  - `resource_changes[1].change.after` = `{"cidr_blocks": ["0.0.0.0/0"], "description": "BI tool access", "from_port": 5432, "protocol": "tcp", "security_group...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

