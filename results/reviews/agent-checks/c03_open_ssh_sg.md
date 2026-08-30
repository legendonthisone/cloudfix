# CloudFix review

**Plan:** `data/plans/c03_open_ssh_sg.json`
**Reviewed by:** agent-checks
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This plan creates a production bastion host with SSH port 22 open to the entire internet (0.0.0.0/0). Remote administration should never be accessible from any IP address without restriction. Use a VPN, security groups restricted to known IPs, or AWS Systems Manager Session Manager instead.

Policy rules that fired: D1

## What is changing

2 to create, 0 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. SSH port 22 is being opened to 0.0.0.0/0 on a production bastion host, making remote administration reachable from the public internet _(rule D1)_
   - evidence: `resource_changes[0].change.after.ingress[0].cidr_blocks` = `["0.0.0.0/0"]`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `SG_ADMIN_PORT_OPEN` on `aws_security_group.bastion` (create)
  - `resource_changes[0].change.after.ingress[0]` = `{"cidr_blocks": ["0.0.0.0/0"], "description": "SSH for the on call engineer", "from_port": 22, "ipv6_cidr_blocks": []...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

