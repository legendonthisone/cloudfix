# CloudFix review

**Plan:** `data/plans/c10_k8s_privileged.json`
**Reviewed by:** scanner
**Model:** none, this rung uses no model

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

4 findings from the security checks. The gate blocks on high or above.

Policy rules that fired: severity gate

## What is changing

- `kubernetes_deployment.log_shipper` will be **created** (kubernetes_deployment, unknown)

_This rung does not analyse blast radius._

## Why

1. K8S_PRIVILEGED_WORKLOAD on kubernetes_deployment.log_shipper: Container workload asks for host level privilege _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].host_pid` = `true`  [no verification pass in this rung]
2. K8S_PRIVILEGED_WORKLOAD on kubernetes_deployment.log_shipper: Container workload asks for host level privilege _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].container[0].security_context[0].privileged` = `true`  [no verification pass in this rung]
3. K8S_PRIVILEGED_WORKLOAD on kubernetes_deployment.log_shipper: Container workload asks for host level privilege _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].host_network` = `true`  [no verification pass in this rung]
4. K8S_PRIVILEGED_WORKLOAD on kubernetes_deployment.log_shipper: Container workload asks for host level privilege _(rule severity gate)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].container[0].security_context[0].allow_privilege_escalation` = `true`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- **CRITICAL** `K8S_PRIVILEGED_WORKLOAD` on `kubernetes_deployment.log_shipper` (create)
  - `resource_changes[0].change.after.spec[0].template[0].spec[0].host_pid` = `true`
- **CRITICAL** `K8S_PRIVILEGED_WORKLOAD` on `kubernetes_deployment.log_shipper` (create)
  - `resource_changes[0].change.after.spec[0].template[0].spec[0].container[0].security_context[0].privileged` = `true`
- **HIGH** `K8S_PRIVILEGED_WORKLOAD` on `kubernetes_deployment.log_shipper` (create)
  - `resource_changes[0].change.after.spec[0].template[0].spec[0].host_network` = `true`
- **HIGH** `K8S_PRIVILEGED_WORKLOAD` on `kubernetes_deployment.log_shipper` (create)
  - `resource_changes[0].change.after.spec[0].template[0].spec[0].container[0].security_context[0].allow_privilege_escalation` = `true`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

