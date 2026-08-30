# CloudFix review

**Plan:** `data/plans/c12_dev_static_website.json`
**Reviewed by:** agent-checks-blast
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

Creating a public S3 static website bucket in development. The bucket is intentionally public (website configuration, public policy, unblocked access), tagged as 'public static marketing site' with DataClassification=public. Human should confirm this is meant to be a website and not accidentally exposing private data.

Policy rules that fired: R2

## What is changing

4 to create, 0 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. bucket is configured as a static website with public read access, which appears intentional based on tags and configuration _(rule R2)_
   - evidence: `resource_changes[1].change.after.index_document` = `[{"suffix": "index.html"}]`  [no verification pass in this rung]

## Checked and dismissed

- `S3_PUBLIC_BUCKET_POLICY` on `aws_s3_bucket_policy.marketing_site`: public read access is expected for a static website bucket, tags explicitly mark this as 'public static marketing site' with DataClassification=public
- `S3_PUBLIC_ACCESS_UNBLOCKED` on `aws_s3_bucket_public_access_block.marketing_site`: public access blocks must be disabled for S3 static website hosting to work, this is required configuration not a misconfiguration

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
- [ ] the bucket name 'lgnd-marketing-site-dev' and tags confirm this is intended as a public marketing website
- [ ] only marketing content (not customer data or credentials) will be uploaded to this bucket
- [ ] this is in the development environment where public website hosting is appropriate

