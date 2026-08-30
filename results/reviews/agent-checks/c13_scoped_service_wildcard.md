# CloudFix review

**Plan:** `data/plans/c13_scoped_service_wildcard.json`
**Reviewed by:** agent-checks
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

Creating an IAM policy that grants all S3 actions (s3:*) on the uploads-prod bucket. While scoped to a single bucket, this includes destructive operations like DeleteObject and DeleteBucket that could cause data loss in production.

Policy rules that fired: R1

## What is changing

1 to create, 0 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. the policy grants s3:* which includes destructive actions like s3:DeleteObject and s3:DeleteBucket on production data _(rule R1)_
   - evidence: `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"UploadsBucketFullControl","Effect":"Allow","Action":"s3:*","Resource":["arn:aws:s3:::lgnd-uploads-prod","arn:aws:s3:::lgnd-uploads-prod/*"]}]}`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **MEDIUM** `IAM_BROAD_ACTION_SCOPED` on `aws_iam_role_policy.uploads_worker` (create)
  - `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"UploadsBucketFullControl","Effect":"Allow","Action":"s3:*","Resource":["...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] verify the uploads-worker role actually needs delete permissions or if it should be restricted to s3:GetObject, s3:PutObject, and s3:ListBucket
- [ ] confirm the bucket has versioning enabled as a safeguard against accidental deletion

