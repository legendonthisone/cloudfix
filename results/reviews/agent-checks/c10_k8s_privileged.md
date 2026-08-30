# CloudFix review

**Plan:** `data/plans/c10_k8s_privileged.json`
**Reviewed by:** agent-checks
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This plan creates a production Kubernetes deployment with host_pid=true and privileged=true, granting the container full host-level access. A compromised log shipper image would compromise the entire node and potentially the cluster.

Policy rules that fired: D5

## What is changing

1 to create, 0 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. container runs with privileged=true in production, granting unrestricted host access _(rule D5)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].container[0].security_context[0].privileged` = `true`  [no verification pass in this rung]
2. container runs with host_pid=true in production, allowing access to all host processes _(rule D5)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].host_pid` = `true`  [no verification pass in this rung]
3. deployment is in production namespace _(rule D5)_
   - evidence: `resource_changes[0].change.after.metadata[0].namespace` = `production`  [no verification pass in this rung]

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

