# CloudFix review

**Plan:** `data/plans/c09_prod_ec2_replace.json`
**Reviewed by:** agent
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This plan replaces a production EC2 instance, causing downtime while the new instance launches. The AMI is being updated from ami-0c101f26f147fa7fd to ami-0f9de6e2d2f067fca. No data is lost since EC2 instances are ephemeral, but service interruption is expected.

Policy rules that fired: R3

## What is changing

0 to create, 0 to update, 1 to replace, 0 to destroy. Worst blast radius: **elevated**.

- `aws_instance.api` will be **replaced** (aws_instance, production). aws_instance serves live production traffic. A replace interrupts it while the replacement comes up.

## Why

1. production EC2 instance is being replaced, which causes service downtime _(rule R3)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [verified against the plan]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] the AMI change is intentional and has been tested
- [ ] the downtime window is acceptable for this production service
- [ ] dependent services can handle the API being unavailable during replacement

