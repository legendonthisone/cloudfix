# CloudFix review

**Plan:** `data/plans/c13_scoped_service_wildcard.json`
**Reviewed by:** baseline
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This plan grants s3:* on a production uploads bucket to a worker role. While scoped to specific resources rather than unbounded, s3:* includes destructive actions like DeleteBucket and PutBucketPolicy that could expose data or cause data loss. This bounded but broad permission requires human review to confirm it matches the principle of least privilege for the worker's actual needs.

Policy rules that fired: R1

## What is changing

- `aws_iam_role_policy.uploads_worker` will be **created** (aws_iam_role_policy, production)

_This rung does not analyse blast radius._

## Why

1. the policy grants s3:* which includes all S3 actions on the uploads bucket and its objects, including destructive operations _(rule R1)_
   - evidence: `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"UploadsBucketFullControl","Effect":"Allow","Action":"s3:*","Resource":["arn:aws:s3:::lgnd-uploads-prod","arn:aws:s3:::lgnd-uploads-prod/*"]}]}`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] verify the uploads worker truly needs s3:* rather than a limited set like s3:GetObject, s3:PutObject, s3:ListBucket
- [ ] confirm this production role should have permissions for destructive operations like s3:DeleteObject and s3:DeleteBucket

