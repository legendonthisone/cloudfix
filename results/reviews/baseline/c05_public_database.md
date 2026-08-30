# CloudFix review

**Plan:** `data/plans/c05_public_database.json`
**Reviewed by:** baseline
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This change exposes a production PostgreSQL database to the public internet without authentication. The database is being made publicly accessible and a security group rule is opening port 5432 to 0.0.0.0/0, allowing anyone on the internet to attempt connections.

Policy rules that fired: D1

## What is changing

- `aws_db_instance.analytics` will be **updated** (aws_db_instance, production)
- `aws_security_group_rule.analytics_from_office` will be **created** (aws_security_group_rule, unknown)

_This rung does not analyse blast radius._

## Why

1. the production database is being changed from private to publicly accessible _(rule D1)_
   - evidence: `resource_changes[0].change.after.publicly_accessible` = `true`  [no verification pass in this rung]
2. a security group rule is being created that opens the PostgreSQL port 5432 to the entire internet _(rule D1)_
   - evidence: `resource_changes[1].change.after.cidr_blocks` = `["0.0.0.0/0"]`  [no verification pass in this rung]
3. the database holds data and is tagged as production environment _(rule D1)_
   - evidence: `resource_changes[0].change.after.tags.Environment` = `production`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

