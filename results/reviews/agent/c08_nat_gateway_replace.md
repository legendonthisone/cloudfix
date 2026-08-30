# CloudFix review

**Plan:** `data/plans/c08_nat_gateway_replace.json`
**Reviewed by:** agent
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This plan replaces the production NAT gateway, moving it to a different subnet. The replacement will cause a brief outage for all egress traffic from private subnets, affecting any workloads that depend on outbound internet connectivity. The route table update depends on the new NAT gateway ID.

Policy rules that fired: R6

## What is changing

0 to create, 1 to update, 1 to replace, 0 to destroy. Worst blast radius: **elevated**.

- `aws_nat_gateway.egress` will be **replaced** (aws_nat_gateway, production). aws_nat_gateway serves live production traffic. A replace interrupts it while the replacement comes up. 2 other resources in this plan reference it, so the effect does not stop at this resource: aws_route.private_default, aws_route.private_default_b.

## Why

1. the production NAT gateway is being replaced, which causes a networking interruption _(rule R6)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [verified against the plan]
2. the NAT gateway is tagged as production environment _(rule R6)_
   - evidence: `resource_changes[0].change.before.tags.Environment` = `production`  [verified against the plan]
3. the route table for private subnets depends on this NAT gateway and will update _(rule R6)_
   - evidence: `resource_changes[1].change.actions` = `["update"]`  [verified against the plan]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] verify that workloads in private subnets can tolerate a brief loss of outbound connectivity during the NAT gateway replacement
- [ ] confirm the subnet change from subnet-0a1b2c3d to subnet-9z8y7x6w is intentional and the new subnet is in the correct availability zone

