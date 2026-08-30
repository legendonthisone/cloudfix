# CloudFix review

**Plan:** `data/plans/c14_mixed_prod_change.json`
**Reviewed by:** agent
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This plan replaces the production load balancer (adding a subnet) and creates its security group with public HTTPS access. The replacement causes temporary downtime for the customer-facing API. The public exposure on 80/443 appears intentional for a load balancer, but the replacement of a production resource requires confirmation.

Policy rules that fired: R3, R2, R6

## What is changing

2 to create, 1 to update, 1 to replace, 0 to destroy. Worst blast radius: **elevated**.

- `aws_lb.public_api` will be **replaced** (aws_lb, production). aws_lb serves live production traffic. A replace interrupts it while the replacement comes up. 2 other resources in this plan reference it, so the effect does not stop at this resource: aws_lb_listener.http_redirect, aws_lb_listener.https.

## Why

1. the production load balancer is being replaced to add a third subnet, which will cause downtime _(rule R3)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [verified against the plan]
2. a security group allowing public access on ports 80 and 443 is being created _(rule R2)_
   - evidence: `resource_changes[1].change.after.ingress[0].cidr_blocks[0]` = `0.0.0.0/0`  [verified against the plan]
3. the load balancer replacement is a networking change that load balancer listeners depend on _(rule R6)_
   - evidence: `configuration.root_module.resources[0].expressions.load_balancer_arn.references[0]` = `aws_lb.public_api.arn`  [verified against the plan]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] the load balancer replacement is expected and the team has a strategy for managing the brief downtime
- [ ] ports 80 and 443 open to the internet are appropriate for this customer API load balancer

