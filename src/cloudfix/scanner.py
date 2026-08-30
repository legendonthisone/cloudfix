"""
The scanner: how this job is actually done today.

checkov and tfsec are the tools a real team already has in its pipeline. They
read Terraform, produce a flat list of findings with severities, and a CI gate
script turns that list into a pass or a fail. Usually the rule is "fail the build
on HIGH or above". That is the whole decision procedure.

This rung reproduces that, and it is deliberately generous to it. It does not use
a text scan. It reuses CloudFix's own action aware checks, which are already
better than a grep for 0.0.0.0/0 because they read the after state. So this is a
stronger opponent than the real thing, on purpose. If CloudFix beats a scanner
that has been handed its own best checks, the comparison is honest.

What it does not have is the thing this project adds: any notion of what is being
destroyed. That is not an oversight in checkov, it is the category. Security
scanners scan configuration. Nothing in that category asks whether the plan
deletes the production database, and a plan that does exactly that, with
everything else configured perfectly, comes back clean.

No model. Free to run. Same answer every time.
"""

import time

from . import checks, policy
from .decision import Decision, Reason, ReviewResult
from .evidence import quote

# The usual CI gate: block on high or above, flag anything medium, otherwise pass.
GATE = {
    "critical": policy.BLOCK,
    "high": policy.BLOCK,
    "medium": policy.REVIEW,
    "low": policy.REVIEW,
}


def review(plan) -> ReviewResult:
    started = time.time()
    findings = checks.run_all(plan)
    steps = [
        {
            "step": 1,
            "name": "scan",
            "kind": "tool",
            "tool": "checks.run_all",
            "output": {"finding_count": len(findings),
                       "findings": [f.to_dict() for f in findings]},
        }
    ]

    verdict = policy.SAFE
    for finding in findings:
        mapped = GATE.get(finding.severity, policy.REVIEW)
        if policy.at_least_as_severe(mapped, verdict):
            verdict = mapped

    reasons = []
    for finding in findings:
        pointer = finding.evidence[0].pointer if finding.evidence else ""
        value = finding.evidence[0].value if finding.evidence else ""
        reasons.append(
            Reason(
                claim="%s on %s: %s"
                % (finding.check_id, finding.resource_address, finding.title),
                evidence_pointer=pointer,
                # quote() renders through JSON, so a Python True is written as the
                # "true" that actually sits in the plan file. Using str() here
                # would have every citation fail its own verification.
                expected_value="" if isinstance(value, (dict, list)) else quote(value),
                rule="severity gate",
            )
        )

    if findings:
        summary = (
            "%d finding%s from the security checks. The gate blocks on high or above."
            % (len(findings), "" if len(findings) == 1 else "s")
        )
    else:
        summary = "No security findings, so the gate passes the plan."

    decision = Decision(
        verdict=verdict,
        summary=summary,
        rules=["severity gate"],
        reasons=reasons,
        dismissed=[],
        confirmations=[],
    )

    steps.append(
        {
            "step": 2,
            "name": "gate",
            "kind": "tool",
            "tool": "scanner.GATE",
            "input": {"severities": [f.severity for f in findings]},
            "output": {"verdict": verdict},
        }
    )

    return ReviewResult(
        decision=decision,
        findings=findings,
        blast=None,
        steps=steps,
        seconds=time.time() - started,
        model_seconds=0.0,
        input_tokens=0,
        output_tokens=0,
        model_calls=0,
        from_cache=True,
    )
