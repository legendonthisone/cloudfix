# CloudFix review

**Plan:** `data/plans/c12_dev_static_website.json`
**Reviewed by:** agent
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This plan creates a static website bucket in development with public read access. The configuration is intentional for a marketing site, but requires confirmation that no sensitive data will be uploaded and that development is the correct environment.

Policy rules that fired: R2

## What is changing

4 to create, 0 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. bucket is configured as a public static website, which may be intended for a marketing site _(rule R2)_
   - evidence: `resource_changes[1].change.after.index_document` = `[{"suffix": "index.html"}]`  [verified against the plan]
2. bucket policy grants public read access, consistent with static website hosting _(rule R2)_
   - evidence: `resource_changes[3].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"PublicReadForWebsite","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::lgnd-marketing-site-dev/*"}]}`  [verified against the plan]
3. tags indicate this is intentionally for public marketing content _(rule R2)_
   - evidence: `resource_changes[0].change.after.tags.DataClassification` = `public`  [verified against the plan]

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

Before approving, confirm:
- [ ] the marketing site content is truly public and contains no sensitive data
- [ ] development is the appropriate environment for this public-facing resource
- [ ] force_destroy is acceptable for a development marketing site

