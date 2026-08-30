# CloudFix review

**Plan:** `data/plans/c13_scoped_service_wildcard.json`
**Reviewed by:** agent-checks-blast-verify
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

Creating an IAM policy that grants s3:* (all S3 actions) on the production uploads bucket. While scoped to named resources rather than unbounded, this includes destructive actions like DeleteBucket and DeleteObject that could cause data loss.

Policy rules that fired: R1

## What is changing

1 to create, 0 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. the policy grants s3:*, which is every S3 action including destructive ones like DeleteObject and DeleteBucket, on the production uploads bucket _(rule R1)_
   - evidence: `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"UploadsBucketFullControl","Effect":"Allow","Action":"s3:*","Resource":["arn:aws:s3:::lgnd-uploads-prod","arn:aws:s3:::lgnd-uploads-prod/*"]}]}`  [verified against the plan]

## Raw findings from the deterministic checks

- **MEDIUM** `IAM_BROAD_ACTION_SCOPED` on `aws_iam_role_policy.uploads_worker` (create)
  - `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"UploadsBucketFullControl","Effect":"Allow","Action":"s3:*","Resource":["...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] the uploads-worker-prod role truly needs destructive S3 permissions like DeleteObject and DeleteBucket, not just read/write access
- [ ] there are compensating controls like S3 versioning or backup policies on lgnd-uploads-prod to protect against accidental deletion

