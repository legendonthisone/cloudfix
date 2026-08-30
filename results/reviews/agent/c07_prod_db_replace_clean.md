# CloudFix review

**Plan:** `data/plans/c07_prod_db_replace_clean.json`
**Reviewed by:** agent
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This plan replaces the production orders database, which destroys all data in it. The change also disables deletion protection and skips the final snapshot, removing both guards that would normally prevent data loss during a replacement.

Policy rules that fired: D4

## What is changing

0 to create, 1 to update, 2 to replace, 0 to destroy. Worst blast radius: **severe**.

- `aws_db_instance.orders` will be **replaced** (aws_db_instance, production). aws_db_instance holds data. A replace destroys the data that is in it today. skip_final_snapshot is true, so Terraform will not take a last backup on the way out. Once this runs the data is gone with nothing to restore. This resource is tagged or named as production. 2 other resources in this plan reference it, so the effect does not stop at this resource: aws_ecs_task_definition.orders_api, aws_ssm_parameter.orders_endpoint. deletion_protection is being turned off. That guard exists to stop exactly the kind of deletion this change makes possible.

## Why

1. the production database orders-prod is being replaced, which destroys the data in it _(rule D4)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [verified against the plan]
2. deletion protection is being turned off on this production database _(rule D4)_
   - evidence: `resource_changes[0].change.after.deletion_protection` = `false`  [verified against the plan]
3. skip_final_snapshot is being set to true, preventing a backup on destroy _(rule D4)_
   - evidence: `resource_changes[0].change.after.skip_final_snapshot` = `true`  [verified against the plan]

## Raw findings from the deterministic checks

- **MEDIUM** `DELETION_PROTECTION_DISABLED` on `aws_db_instance.orders` (replace)
  - `resource_changes[0].change.after.deletion_protection` = `false`
- **MEDIUM** `FINAL_SNAPSHOT_SKIPPED` on `aws_db_instance.orders` (replace)
  - `resource_changes[0].change.after.skip_final_snapshot` = `true`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

