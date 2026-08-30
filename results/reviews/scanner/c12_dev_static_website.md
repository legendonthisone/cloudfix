# CloudFix review

**Plan:** `data/plans/c12_dev_static_website.json`
**Reviewed by:** scanner
**Model:** none, this rung uses no model

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

2 findings from the security checks. The gate blocks on high or above.

Policy rules that fired: severity gate

## What is changing

- `aws_s3_bucket.marketing_site` will be **created** (aws_s3_bucket, development)
- `aws_s3_bucket_website_configuration.marketing_site` will be **created** (aws_s3_bucket_website_configuration, development)
- `aws_s3_bucket_public_access_block.marketing_site` will be **created** (aws_s3_bucket_public_access_block, development)
- `aws_s3_bucket_policy.marketing_site` will be **created** (aws_s3_bucket_policy, development)

_This rung does not analyse blast radius._

## Why

1. S3_PUBLIC_BUCKET_POLICY on aws_s3_bucket_policy.marketing_site: Bucket policy grants access to any principal _(rule severity gate)_
   - evidence: `resource_changes[3].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"PublicReadForWebsite","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::lgnd-marketing-site-dev/*"}]}`  [no verification pass in this rung]
2. S3_PUBLIC_ACCESS_UNBLOCKED on aws_s3_bucket_public_access_block.marketing_site: S3 public access protections switched off _(rule severity gate)_
   - evidence: `resource_changes[2].change.after.block_public_acls` = `false`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `S3_PUBLIC_BUCKET_POLICY` on `aws_s3_bucket_policy.marketing_site` (create)
  - `resource_changes[3].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"PublicReadForWebsite","Effect":"Allow","Principal":"*","Action":"s3:GetO...`
- **CRITICAL** `S3_PUBLIC_ACCESS_UNBLOCKED` on `aws_s3_bucket_public_access_block.marketing_site` (create)
  - `resource_changes[2].change.after.block_public_acls` = `false`
  - `resource_changes[2].change.after.block_public_policy` = `false`
  - `resource_changes[2].change.after.ignore_public_acls` = `false`
  - `resource_changes[2].change.after.restrict_public_buckets` = `false`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

