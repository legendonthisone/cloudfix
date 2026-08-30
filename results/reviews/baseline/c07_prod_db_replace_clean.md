# CloudFix review

**Plan:** `data/plans/c07_prod_db_replace_clean.json`
**Reviewed by:** baseline
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This plan replaces the production orders database, which will destroy all data in it. The replacement also disables deletion protection and enables skip_final_snapshot, removing two critical safeguards that protect against data loss. This is a major version upgrade (PostgreSQL 14.9 to 15.4) being performed via replacement instead of in-place upgrade.

Policy rules that fired: D4

## What is changing

- `aws_db_instance.orders` will be **replaced** (aws_db_instance, production)
- `aws_db_parameter_group.orders` will be **replaced** (aws_db_parameter_group, production)
- `aws_ssm_parameter.orders_endpoint` will be **updated** (aws_ssm_parameter, production)

_This rung does not analyse blast radius._

## Why

1. the production database orders-prod is being replaced via delete-create, which destroys the data in it _(rule D4)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [no verification pass in this rung]
2. deletion_protection is being disabled on the production database during replacement _(rule D4)_
   - evidence: `resource_changes[0].change.after.deletion_protection` = `false`  [no verification pass in this rung]
3. skip_final_snapshot is being enabled, preventing a final backup before the database is destroyed _(rule D4)_
   - evidence: `resource_changes[0].change.after.skip_final_snapshot` = `true`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

