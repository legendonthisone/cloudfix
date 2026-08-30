# CloudFix review

**Plan:** `data/plans/c06_encryption_removed.json`
**Reviewed by:** agent-checks-blast-verify
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This change removes encryption from a production EBS volume holding orders data and replaces the volume, destroying its contents. Both encryption removal and production data destruction are blocking conditions.

Policy rules that fired: D3, D4

## What is changing

0 to create, 0 to update, 1 to replace, 0 to destroy. Worst blast radius: **severe**.

- `aws_ebs_volume.orders_data` will be **replaced** (aws_ebs_volume, production). aws_ebs_volume holds data. A replace destroys the data that is in it today. A final snapshot is configured, so a restore is possible, but it is a restore, not a no-op. This resource is tagged or named as production.

## Why

1. encryption is being removed from a production volume that is currently encrypted _(rule D3)_
   - evidence: `resource_changes[0].change.after.encrypted` = `false`  [verified against the plan]
2. the production EBS volume is being replaced, which destroys the data in it _(rule D4)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [verified against the plan]
3. the resource is tagged as production and named orders-data-prod _(rule D4)_
   - evidence: `resource_changes[0].change.before.tags.Environment` = `production`  [verified against the plan]

## Raw findings from the deterministic checks

- **CRITICAL** `ENCRYPTION_REMOVED` on `aws_ebs_volume.orders_data` (replace)
  - `resource_changes[0].change.after.encrypted` = `false`
- **HIGH** `ENCRYPTION_KEY_REMOVED` on `aws_ebs_volume.orders_data` (replace)
  - `resource_changes[0].change.before.kms_key_id` = `arn:aws:kms:us-east-1:111122223333:key/9d1a`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

