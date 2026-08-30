# CloudFix review

**Plan:** `data/plans/c07_prod_db_replace_clean.json`
**Reviewed by:** agent-checks-blast
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This plan replaces the production orders database, which will destroy all data in it. Deletion protection is being turned off and skip_final_snapshot is being set to true, so there will be no backup taken and no guard to prevent the destruction. This appears to be a PostgreSQL version upgrade from 14.9 to 15.4 that forces replacement, but the safety guards have been disabled.

Policy rules that fired: D4

## What is changing

0 to create, 1 to update, 2 to replace, 0 to destroy. Worst blast radius: **severe**.

- `aws_db_instance.orders` will be **replaced** (aws_db_instance, production). aws_db_instance holds data. A replace destroys the data that is in it today. skip_final_snapshot is true, so Terraform will not take a last backup on the way out. Once this runs the data is gone with nothing to restore. This resource is tagged or named as production. 2 other resources in this plan reference it, so the effect does not stop at this resource: aws_ecs_task_definition.orders_api, aws_ssm_parameter.orders_endpoint. deletion_protection is being turned off. That guard exists to stop exactly the kind of deletion this change makes possible.

## Why

1. the production database is being replaced, which destroys the data in it _(rule D4)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [no verification pass in this rung]
2. deletion protection is being turned off, removing the guard that prevents accidental destroys _(rule D4)_
   - evidence: `resource_changes[0].change.after.deletion_protection` = `false`  [no verification pass in this rung]
3. skip_final_snapshot is being set to true, so no backup will be taken when the database is destroyed _(rule D4)_
   - evidence: `resource_changes[0].change.after.skip_final_snapshot` = `true`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **MEDIUM** `DELETION_PROTECTION_DISABLED` on `aws_db_instance.orders` (replace)
  - `resource_changes[0].change.after.deletion_protection` = `false`
- **MEDIUM** `FINAL_SNAPSHOT_SKIPPED` on `aws_db_instance.orders` (replace)
  - `resource_changes[0].change.after.skip_final_snapshot` = `true`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

