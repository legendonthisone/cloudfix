# CloudFix review

**Plan:** `data/plans/c13_scoped_service_wildcard.json`
**Reviewed by:** scanner
**Model:** none, this rung uses no model

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

1 finding from the security checks. The gate blocks on high or above.

Policy rules that fired: severity gate

## What is changing

- `aws_iam_role_policy.uploads_worker` will be **created** (aws_iam_role_policy, production)

_This rung does not analyse blast radius._

## Why

1. IAM_BROAD_ACTION_SCOPED on aws_iam_role_policy.uploads_worker: IAM policy allows a whole service, but only on named resources _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"UploadsBucketFullControl","Effect":"Allow","Action":"s3:*","Resource":["arn:aws:s3:::lgnd-uploads-prod","arn:aws:s3:::lgnd-uploads-prod/*"]}]}`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **MEDIUM** `IAM_BROAD_ACTION_SCOPED` on `aws_iam_role_policy.uploads_worker` (create)
  - `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"UploadsBucketFullControl","Effect":"Allow","Action":"s3:*","Resource":["...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

