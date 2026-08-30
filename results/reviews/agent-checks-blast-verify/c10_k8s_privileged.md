# CloudFix review

**Plan:** `data/plans/c10_k8s_privileged.json`
**Reviewed by:** agent-checks-blast-verify
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This plan creates a Kubernetes deployment in production with host-level privileges, including privileged mode, host PID namespace, host network, and runs as root. A compromised log shipper container would have complete control over the Kubernetes node.

Policy rules that fired: D5

## What is changing

1 to create, 0 to update, 0 to replace, 0 to destroy. Worst blast radius: **routine**.

- Nothing destructive in this plan.

## Why

1. the container runs with privileged: true, allowing it to bypass all container isolation and access the host _(rule D5)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].container[0].security_context[0].privileged` = `true`  [verified against the plan]
2. the container runs with host_pid: true, allowing it to see and manipulate all processes on the node _(rule D5)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].host_pid` = `true`  [verified against the plan]
3. the workload is deployed to the production namespace _(rule D5)_
   - evidence: `resource_changes[0].change.after.metadata[0].namespace` = `production`  [verified against the plan]

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

Before approving, confirm:
- [ ] verify whether this log shipper truly requires host-level access or if it can be reconfigured with a hostPath volume mount instead
- [ ] confirm whether a DaemonSet with read-only host mounts would accomplish the same goal more safely

