# CloudFix review

**Plan:** `data/plans/c04_iam_wildcard_admin.json`
**Reviewed by:** baseline
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This change grants the CI/CD deployment role complete administrator access to the entire AWS account. The policy is being updated from scoped S3 permissions (get/put on a specific artifacts bucket) to Action:* on Resource:*, which is unbounded privilege across all AWS services and resources in production.

Policy rules that fired: D2

## What is changing

- `aws_iam_policy.ci_deploy` will be **updated** (aws_iam_policy, production)

_This rung does not analyse blast radius._

## Why

1. the IAM policy is being updated to grant every action on every resource _(rule D2)_
   - evidence: `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"DeployAnything","Effect":"Allow","Action":"*","Resource":"*"}]}`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

