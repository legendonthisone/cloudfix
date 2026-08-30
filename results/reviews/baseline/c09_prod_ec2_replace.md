# CloudFix review

**Plan:** `data/plans/c09_prod_ec2_replace.json`
**Reviewed by:** baseline
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

This change replaces the production API instance, which will cause downtime during the replacement. The instance holds no persistent data (stateless compute) but the service interruption requires human approval. The AMI is being updated from ami-0c101f26f147fa7fd to ami-0f9de6e2d2f067fca.

Policy rules that fired: R3

## What is changing

- `aws_instance.api` will be **replaced** (aws_instance, production)

_This rung does not analyse blast radius._

## Why

1. the production API instance is being replaced, causing downtime for a production resource with no data loss _(rule R3)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

Before approving, confirm:
- [ ] deployment window is appropriate for API service downtime
- [ ] load balancer or service discovery will handle the instance replacement
- [ ] AMI ami-0f9de6e2d2f067fca has been tested and validated

