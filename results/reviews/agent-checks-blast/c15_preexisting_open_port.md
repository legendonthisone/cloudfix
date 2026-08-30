# CloudFix review

**Plan:** `data/plans/c15_preexisting_open_port.json`
**Reviewed by:** agent-checks-blast
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: SAFE

SAFE. Nothing in this plan weakens security or destroys anything that matters.

This change only adds tags (Owner, CostCentre) to an existing security group without modifying any security rules. The SSH port open to 0.0.0.0/0 was already present before this change and is not being introduced or expanded by this deploy.

## What is changing

0 to create, 1 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

No risk found that meets any policy rule.

## Checked and dismissed

- `SG_ADMIN_PORT_OPEN` on `aws_security_group.legacy_ftp`: the SSH exposure already existed before this change (introduced_by_change: false). This deploy only adds tags and does not touch the ingress rules. Rule R5 applies: pre-existing risk not introduced by this change.

## Raw findings from the deterministic checks

- **HIGH** `SG_ADMIN_PORT_OPEN` on `aws_security_group.legacy_ftp` (update)
  - `resource_changes[0].change.after.ingress[0]` = `{"cidr_blocks": ["0.0.0.0/0"], "description": "SSH, open since before this repository existed", "from_port": 22, "ipv...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

