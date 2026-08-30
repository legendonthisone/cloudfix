# CloudFix review

**Plan:** `data/plans/c08_nat_gateway_replace.json`
**Reviewed by:** agent-checks-blast-verify
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

The production NAT gateway is being replaced, which will interrupt outbound internet connectivity for all resources routing through it. Two routes in this plan depend on it, causing them to update during the transition. This is likely a subnet move, but the timing and impact on production workloads needs human confirmation.

Policy rules that fired: R6

## What is changing

0 to create, 1 to update, 1 to replace, 0 to destroy. Worst blast radius: **elevated**.

- `aws_nat_gateway.egress` will be **replaced** (aws_nat_gateway, production). aws_nat_gateway serves live production traffic. A replace interrupts it while the replacement comes up. 2 other resources in this plan reference it, so the effect does not stop at this resource: aws_route.private_default, aws_route.private_default_b.

## Why

1. production NAT gateway is being replaced, causing network disruption _(rule R6)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [verified against the plan]
2. the NAT gateway replacement is in production environment _(rule R6)_
   - evidence: `resource_changes[0].change.before.tags.Environment` = `production`  [verified against the plan]
3. two routes in this plan reference the NAT gateway being replaced _(rule R6)_
   - evidence: `resource_changes[1].address` = `aws_route.private_default`  [verified against the plan]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] confirm the timing is acceptable for production workloads that route through this NAT gateway
- [ ] verify there is monitoring in place to detect connectivity issues during the replacement
- [ ] check whether a maintenance window is needed for the subnet migration

