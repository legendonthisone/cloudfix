# CloudFix review

**Plan:** `data/plans/c15_preexisting_open_port.json`
**Reviewed by:** agent-checks
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This change only adds tags to a security group in production. The SSH port open to the internet was already there and is not introduced by this deploy, but it remains a significant security risk that should be remediated separately.

Policy rules that fired: R5

## What is changing

0 to create, 1 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. SSH port 22 is open to 0.0.0.0/0 in production, allowing remote administration from anywhere on the internet _(rule R5)_
   - evidence: `resource_changes[0].change.after.ingress[0].cidr_blocks` = `["0.0.0.0/0"]`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **HIGH** `SG_ADMIN_PORT_OPEN` on `aws_security_group.legacy_ftp` (update)
  - `resource_changes[0].change.after.ingress[0]` = `{"cidr_blocks": ["0.0.0.0/0"], "description": "SSH, open since before this repository existed", "from_port": 22, "ipv...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] the SSH exposure on legacy-ftp-prod-sg should be restricted to a bastion or VPN range
- [ ] verify that only adding tags is the intended change and the open SSH rule is acknowledged technical debt

