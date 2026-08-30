# CloudFix review

**Plan:** `data/plans/c04_iam_wildcard_admin.json`
**Reviewed by:** scanner
**Model:** none, this rung uses no model

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

1 finding from the security checks. The gate blocks on high or above.

Policy rules that fired: severity gate

## What is changing

- `aws_iam_policy.ci_deploy` will be **updated** (aws_iam_policy, production)

_This rung does not analyse blast radius._

## Why

1. IAM_WILDCARD_ADMIN on aws_iam_policy.ci_deploy: IAM policy grants every action on every resource _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"DeployAnything","Effect":"Allow","Action":"*","Resource":"*"}]}`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `IAM_WILDCARD_ADMIN` on `aws_iam_policy.ci_deploy` (update)
  - `resource_changes[0].change.after.policy` = `{"Version":"2012-10-17","Statement":[{"Sid":"DeployAnything","Effect":"Allow","Action":"*","Resource":"*"}]}`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

