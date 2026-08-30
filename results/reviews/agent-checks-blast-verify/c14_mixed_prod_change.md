# CloudFix review

**Plan:** `data/plans/c14_mixed_prod_change.json`
**Reviewed by:** agent-checks-blast-verify
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This plan replaces the production load balancer, which will interrupt live API traffic while the replacement comes up and listeners are recreated. The networking change is required for the other resources (listeners) to function. The security group being created opens 80/443 to the internet, which appears intentional for a public API.

Policy rules that fired: R6, R3

## What is changing

2 to create, 1 to update, 1 to replace, 0 to destroy. Worst blast radius: **elevated**.

- `aws_lb.public_api` will be **replaced** (aws_lb, production). aws_lb serves live production traffic. A replace interrupts it while the replacement comes up. 2 other resources in this plan reference it, so the effect does not stop at this resource: aws_lb_listener.http_redirect, aws_lb_listener.https.

## Why

1. the production load balancer is being replaced, causing downtime for live traffic _(rule R3)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [verified against the plan]
2. two listeners in the configuration depend on this load balancer and will be affected by the replacement _(rule R6)_
   - evidence: `resource_changes[0].address` = `aws_lb.public_api`  [verified against the plan]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] the production API can tolerate the downtime while the load balancer is replaced
- [ ] the subnet change (adding subnet-2a3b4c5d) is intentional and has been validated
- [ ] dependent listeners will automatically recreate and point to the new load balancer

