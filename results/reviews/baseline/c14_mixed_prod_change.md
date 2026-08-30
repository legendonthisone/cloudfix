# CloudFix review

**Plan:** `data/plans/c14_mixed_prod_change.json`
**Reviewed by:** baseline
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This plan replaces a production load balancer to add a subnet, which will cause brief downtime as the ALB is recreated. The security group allows public HTTPS/HTTP access, which appears intentional for an API, and a dev S3 bucket is created with force_destroy enabled.

Policy rules that fired: R3, R2

## What is changing

- `aws_lb.public_api` will be **replaced** (aws_lb, production)
- `aws_security_group.public_api` will be **created** (aws_security_group, production)
- `aws_s3_bucket.build_cache` will be **created** (aws_s3_bucket, development)
- `aws_cloudwatch_log_group.api` will be **updated** (aws_cloudwatch_log_group, production)

_This rung does not analyse blast radius._

## Why

1. the production load balancer is being replaced to add a subnet, which causes downtime during the delete-create cycle _(rule R3)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [no verification pass in this rung]
2. a security group allows inbound traffic from 0.0.0.0/0 on ports 80 and 443, which is typical for a public API but should be confirmed as intended _(rule R2)_
   - evidence: `resource_changes[1].change.after.ingress[0].cidr_blocks` = `["0.0.0.0/0"]`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] the load balancer replacement will cause brief downtime and the team has a maintenance window or acceptable impact
- [ ] the public HTTPS/HTTP access on the security group is intended for the customer-facing API
- [ ] dependent resources like listeners will correctly reference the new load balancer ARN after recreation

