# CloudFix review

**Plan:** `data/plans/c02_public_s3_bucket.json`
**Reviewed by:** scanner
**Model:** none, this rung uses no model

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

2 findings from the security checks. The gate blocks on high or above.

Policy rules that fired: severity gate

## What is changing

- `aws_s3_bucket_public_access_block.exports` will be **updated** (aws_s3_bucket_public_access_block, production)
- `aws_s3_bucket_acl.exports` will be **created** (aws_s3_bucket_acl, production)

_This rung does not analyse blast radius._

## Why

1. S3_PUBLIC_ACL on aws_s3_bucket_acl.exports: S3 bucket granted a public access control list _(rule severity gate)_
   - evidence: `resource_changes[1].change.after.acl` = `public-read`  [no verification pass in this rung]
2. S3_PUBLIC_ACCESS_UNBLOCKED on aws_s3_bucket_public_access_block.exports: S3 public access protections switched off _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.block_public_acls` = `false`  [no verification pass in this rung]

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

