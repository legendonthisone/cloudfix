# CloudFix review

**Plan:** `data/plans/c09_prod_ec2_replace.json`
**Reviewed by:** agent-checks-blast-verify
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

Production API instance is being replaced, causing downtime while the new instance comes up. This is AMI update from ami-0c101f26f147fa7fd to ami-0f9de6e2d2f067fca. No data loss risk, but service interruption expected.

Policy rules that fired: R3

## What is changing

0 to create, 0 to update, 1 to replace, 0 to destroy. Worst blast radius: **elevated**.

- `aws_instance.api` will be **replaced** (aws_instance, production). aws_instance serves live production traffic. A replace interrupts it while the replacement comes up.

## Why

1. the production API instance is being replaced, which causes downtime _(rule R3)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [verified against the plan]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] verify the AMI ami-0f9de6e2d2f067fca has been tested and is ready for production
- [ ] confirm the deployment window is acceptable for API downtime
- [ ] ensure monitoring is in place to detect when the new instance is healthy

