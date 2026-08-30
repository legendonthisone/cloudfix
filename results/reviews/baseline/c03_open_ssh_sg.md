# CloudFix review

**Plan:** `data/plans/c03_open_ssh_sg.json`
**Reviewed by:** baseline
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This plan creates a production bastion host with SSH port 22 open to the entire internet (0.0.0.0/0). This exposes an administrative interface to the public internet, creating an attack surface for brute force and credential stuffing attempts.

Policy rules that fired: D1

## What is changing

- `aws_security_group.bastion` will be **created** (aws_security_group, production)
- `aws_instance.bastion` will be **created** (aws_instance, production)

_This rung does not analyse blast radius._

## Why

1. SSH port 22 is being opened to 0.0.0.0/0 on a production bastion host _(rule D1)_
   - evidence: `resource_changes[0].change.after.ingress[0].cidr_blocks[0]` = `0.0.0.0/0`  [no verification pass in this rung]
2. the security group is tagged as production environment _(rule D1)_
   - evidence: `resource_changes[0].change.after.tags.Environment` = `production`  [no verification pass in this rung]
3. port 22 is a remote administration port _(rule D1)_
   - evidence: `resource_changes[0].change.after.ingress[0].from_port` = `22`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

