# CloudFix review

**Plan:** `data/plans/c08_nat_gateway_replace.json`
**Reviewed by:** baseline
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

The NAT gateway is being replaced, moving to a different subnet. This will cause a brief outage for all private subnet resources that depend on it for internet connectivity. The route table updates automatically to point to the new NAT gateway.

Policy rules that fired: R6

## What is changing

- `aws_nat_gateway.egress` will be **replaced** (aws_nat_gateway, production)
- `aws_route.private_default` will be **updated** (aws_route, unknown)

_This rung does not analyse blast radius._

## Why

1. the NAT gateway is being replaced (delete then create), which will interrupt outbound internet connectivity for private subnets during the transition _(rule R6)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [no verification pass in this rung]
2. the route table that depends on this NAT gateway is being updated in the same plan _(rule R6)_
   - evidence: `resource_changes[1].change.actions` = `["update"]`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] the outage window for private subnet connectivity is acceptable
- [ ] dependent applications can tolerate the brief loss of internet egress
- [ ] the new subnet subnet-9z8y7x6w is properly configured in a public subnet with internet gateway access

