# CloudFix review

**Plan:** `data/plans/c15_preexisting_open_port.json`
**Reviewed by:** agent-checks-blast-verify
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This change only adds tags to an existing security group without modifying security rules. However, the security group has SSH (port 22) open to the entire internet (0.0.0.0/0) in production, which is a security risk that requires human review even though it predates this change.

Policy rules that fired: R5

## What is changing

0 to create, 1 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. SSH port 22 is open to 0.0.0.0/0 in production, which is a remote administration exposure _(rule R5)_
   - evidence: `resource_changes[0].change.after.ingress[0].cidr_blocks` = `["0.0.0.0/0"]`  [verified against the plan]

## Raw findings from the deterministic checks

- **HIGH** `SG_ADMIN_PORT_OPEN` on `aws_security_group.legacy_ftp` (update)
  - `resource_changes[0].change.after.ingress[0]` = `{"cidr_blocks": ["0.0.0.0/0"], "description": "SSH, open since before this repository existed", "from_port": 22, "ipv...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] the SSH exposure on legacy-ftp-prod-sg predates this change but should be reviewed for remediation

