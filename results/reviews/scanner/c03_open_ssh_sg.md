# CloudFix review

**Plan:** `data/plans/c03_open_ssh_sg.json`
**Reviewed by:** scanner
**Model:** none, this rung uses no model

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

1 finding from the security checks. The gate blocks on high or above.

Policy rules that fired: severity gate

## What is changing

- `aws_security_group.bastion` will be **created** (aws_security_group, production)
- `aws_instance.bastion` will be **created** (aws_instance, production)

_This rung does not analyse blast radius._

## Why

1. SG_ADMIN_PORT_OPEN on aws_security_group.bastion: Remote administration port open to the whole internet _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.ingress[0]`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `SG_ADMIN_PORT_OPEN` on `aws_security_group.bastion` (create)
  - `resource_changes[0].change.after.ingress[0]` = `{"cidr_blocks": ["0.0.0.0/0"], "description": "SSH for the on call engineer", "from_port": 22, "ipv6_cidr_blocks": []...`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

