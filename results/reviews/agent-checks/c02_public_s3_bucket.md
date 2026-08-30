# CloudFix review

**Plan:** `data/plans/c02_public_s3_bucket.json`
**Reviewed by:** agent-checks
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This change makes a production bucket holding confidential customer data publicly readable from the internet. The bucket is tagged DataClassification=confidential and named customer-exports-prod, but the plan removes all four public access protections and applies a public-read ACL that exposes its contents to anyone with the URL.

Policy rules that fired: D1

## What is changing

1 to create, 1 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. the bucket is being granted public-read access, making data readable from the public internet _(rule D1)_
   - evidence: `resource_changes[1].change.after.acl` = `public-read`  [no verification pass in this rung]
2. all four public access guards are being disabled, removing the safety net that prevents accidental public exposure _(rule D1)_
   - evidence: `resource_changes[0].change.after.block_public_acls` = `false`  [no verification pass in this rung]
3. the bucket is tagged as containing confidential data in production _(rule D1)_
   - evidence: `resource_changes[1].change.after.tags.DataClassification` = `confidential`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `S3_PUBLIC_ACL` on `aws_s3_bucket_acl.exports` (create)
  - `resource_changes[1].change.after.acl` = `public-read`
- **CRITICAL** `S3_PUBLIC_ACCESS_UNBLOCKED` on `aws_s3_bucket_public_access_block.exports` (update)
  - `resource_changes[0].change.after.block_public_acls` = `false`
  - `resource_changes[0].change.after.block_public_policy` = `false`
  - `resource_changes[0].change.after.ignore_public_acls` = `false`
  - `resource_changes[0].change.after.restrict_public_buckets` = `false`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

