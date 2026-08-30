# CloudFix review

**Plan:** `data/plans/c10_k8s_privileged.json`
**Reviewed by:** baseline
**Model:** us.anthropic.claude-sonnet-4-5-20250929-v1:0

## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This deployment grants a production container host-level privileges including privileged mode, host networking, and host PID namespace access. These capabilities allow the container to break out of isolation and access the underlying node with root permissions, which violates security boundaries in production.

Policy rules that fired: D5

## What is changing

- `kubernetes_deployment.log_shipper` will be **created** (kubernetes_deployment, unknown)

_This rung does not analyse blast radius._

## Why

1. the container runs with privileged: true, granting host-level capabilities _(rule D5)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].container[0].security_context[0].privileged` = `true`  [no verification pass in this rung]
2. host_network: true allows the container to use the host's network namespace _(rule D5)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].host_network` = `true`  [no verification pass in this rung]
3. host_pid: true allows the container to see all processes on the host _(rule D5)_
   - evidence: `resource_changes[0].change.after.spec[0].template[0].spec[0].host_pid` = `true`  [no verification pass in this rung]
4. the deployment is in the production namespace _(rule D5)_
   - evidence: `resource_changes[0].change.after.metadata[0].namespace` = `production`  [no verification pass in this rung]

## Raw findings from the deterministic checks

- None. No security check fired on this plan.

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.

