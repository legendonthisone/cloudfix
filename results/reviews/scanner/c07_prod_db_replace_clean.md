# CloudFix review

**Plan:** `data/plans/c07_prod_db_replace_clean.json`
**Reviewed by:** scanner
**Model:** none, this rung uses no model

## Verdict: REQUIRES HUMAN REVIEW

REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.

2 findings from the security checks. The gate blocks on high or above.

Policy rules that fired: severity gate

## What is changing

- `aws_db_instance.orders` will be **replaced** (aws_db_instance, production)
- `aws_db_parameter_group.orders` will be **replaced** (aws_db_parameter_group, production)
- `aws_ssm_parameter.orders_endpoint` will be **updated** (aws_ssm_parameter, production)

_This rung does not analyse blast radius._

## Why

1. DELETION_PROTECTION_DISABLED on aws_db_instance.orders: Deletion protection is not enabled _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.deletion_protection` = `false`  [no verification pass in this rung]
2. FINAL_SNAPSHOT_SKIPPED on aws_db_instance.orders: No final snapshot will be taken _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.skip_final_snapshot` = `true`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **MEDIUM** `DELETION_PROTECTION_DISABLED` on `aws_db_instance.orders` (replace)
  - `resource_changes[0].change.after.deletion_protection` = `false`
- **MEDIUM** `FINAL_SNAPSHOT_SKIPPED` on `aws_db_instance.orders` (replace)
  - `resource_changes[0].change.after.skip_final_snapshot` = `true`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

