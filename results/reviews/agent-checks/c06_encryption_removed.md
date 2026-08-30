# CloudFix review

**Plan:** `data/plans/c06_encryption_removed.json`
**Reviewed by:** agent-checks
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This plan removes encryption from a production EBS volume holding orders data. The volume is being replaced, and the new volume will be unencrypted where the current one uses KMS encryption. This is a data protection violation that must not be deployed.

Policy rules that fired: D3

## What is changing

0 to create, 0 to update, 1 to replace, 0 to destroy. Worst blast radius: **severe**.

- `aws_ebs_volume.orders_data` will be **replaced** (aws_ebs_volume, production). aws_ebs_volume holds data. A replace destroys the data that is in it today. A final snapshot is configured, so a restore is possible, but it is a restore, not a no-op. This resource is tagged or named as production.

## Why

1. encryption is being removed from a production data volume _(rule D3)_
   - evidence: `resource_changes[0].change.after.encrypted` = `false`  [no verification pass in this rung]
2. the volume held encrypted data before this change _(rule D3)_
   - evidence: `resource_changes[0].change.before.encrypted` = `true`  [no verification pass in this rung]
3. this is a production resource _(rule D3)_
   - evidence: `resource_changes[0].change.before.tags.Environment` = `production`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `ENCRYPTION_REMOVED` on `aws_ebs_volume.orders_data` (replace)
  - `resource_changes[0].change.after.encrypted` = `false`
- **HIGH** `ENCRYPTION_KEY_REMOVED` on `aws_ebs_volume.orders_data` (replace)
  - `resource_changes[0].change.before.kms_key_id` = `arn:aws:kms:us-east-1:111122223333:key/9d1a`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

