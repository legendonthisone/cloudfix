# CloudFix review

**Plan:** `data/plans/c06_encryption_removed.json`
**Reviewed by:** scanner
**Model:** none, this rung uses no model

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

2 findings from the security checks. The gate blocks on high or above.

Policy rules that fired: severity gate

## What is changing

- `aws_ebs_volume.orders_data` will be **replaced** (aws_ebs_volume, production)

_This rung does not analyse blast radius._

## Why

1. ENCRYPTION_REMOVED on aws_ebs_volume.orders_data: Encryption at rest turned off by this change _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.encrypted` = `false`  [no verification pass in this rung]
2. ENCRYPTION_KEY_REMOVED on aws_ebs_volume.orders_data: Customer managed encryption key removed _(rule severity gate)_
   - evidence: `resource_changes[0].change.before.kms_key_id` = `arn:aws:kms:us-east-1:111122223333:key/9d1a`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `ENCRYPTION_REMOVED` on `aws_ebs_volume.orders_data` (replace)
  - `resource_changes[0].change.after.encrypted` = `false`
- **HIGH** `ENCRYPTION_KEY_REMOVED` on `aws_ebs_volume.orders_data` (replace)
  - `resource_changes[0].change.before.kms_key_id` = `arn:aws:kms:us-east-1:111122223333:key/9d1a`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

