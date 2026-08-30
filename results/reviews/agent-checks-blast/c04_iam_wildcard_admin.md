# CloudFix review

**Plan:** `data/plans/c04_iam_wildcard_admin.json`
**Reviewed by:** agent-checks-blast
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This change grants the CI/CD pipeline unrestricted administrator access to the entire AWS account. The policy is changing from scoped S3 permissions (get/put on a specific artifacts bucket) to Action '*' on Resource '*', which is unbounded privilege in production.

Policy rules that fired: D2

## What is changing

0 to create, 1 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. the IAM policy is being updated to grant every action on every resource _(rule D2)_
   - evidence: `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"DeployAnything","Effect":"Allow","Action":"*","Resource":"*"}]}`  [no verification pass in this rung]
2. this policy is attached to a production GitHub Actions role, granting the CI/CD pipeline complete account control _(rule D2)_
   - evidence: `resource_changes[1].change.after.role` = `github-actions-prod`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `IAM_WILDCARD_ADMIN` on `aws_iam_policy.ci_deploy` (update)
  - `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"DeployAnything","Effect":"Allow","Action":"*","Resource":"*"}]}`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

