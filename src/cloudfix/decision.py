"""
The thing CloudFix actually hands back, and how it is written down.

A decision is not a verdict on its own. A verdict with no evidence is the same
"looks fine to me" a tired engineer gives at 6pm on a Friday, which is the exact
failure this project exists to remove. So a decision carries:

  the verdict            SAFE, REQUIRES HUMAN REVIEW, or DO NOT APPLY
  the policy rules       which numbered rules in docs/VERDICT_POLICY.md fired
  the reasons            each one pointing at a line in the plan that proves it
  what was dismissed     findings that fired but do not apply here, and why
  the human checkpoint   what the person approving still has to confirm

The dismissed list matters as much as the reasons. A tool that only ever adds
warnings gets muted within a month. Saying "this one fired and here is why it
does not apply" is what makes the ones that remain worth reading.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import policy
from .evidence import quote


@dataclass
class Reason:
    claim: str
    evidence_pointer: str = ""
    expected_value: str = ""
    rule: str = ""
    supported: Optional[bool] = None
    support_note: str = ""

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "evidence_pointer": self.evidence_pointer,
            "expected_value": self.expected_value,
            "rule": self.rule,
            "supported": self.supported,
            "support_note": self.support_note,
        }


@dataclass
class Dismissal:
    check_id: str
    resource_address: str
    why: str

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "resource_address": self.resource_address,
            "why": self.why,
        }


@dataclass
class Decision:
    verdict: str
    summary: str = ""
    rules: List[str] = field(default_factory=list)
    reasons: List[Reason] = field(default_factory=list)
    dismissed: List[Dismissal] = field(default_factory=list)
    confirmations: List[str] = field(default_factory=list)

    @property
    def unsupported_reasons(self) -> List[Reason]:
        return [r for r in self.reasons if r.supported is False]

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "summary": self.summary,
            "rules": self.rules,
            "reasons": [r.to_dict() for r in self.reasons],
            "dismissed": [d.to_dict() for d in self.dismissed],
            "confirmations": self.confirmations,
            "unsupported_reason_count": len(self.unsupported_reasons),
        }


@dataclass
class ReviewResult:
    """One complete review of one plan, plus everything needed to audit it."""

    decision: Optional[Decision] = None
    findings: List[Any] = field(default_factory=list)
    blast: Optional[Any] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0
    model_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    model_calls: int = 0
    repairs: int = 0
    from_cache: bool = True
    error: Optional[str] = None
    raw_text: str = ""

    @property
    def verdict(self) -> str:
        return self.decision.verdict if self.decision else ""

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "decision": self.decision.to_dict() if self.decision else None,
            "repairs": self.repairs,
            "model_calls": self.model_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "model_seconds": round(self.model_seconds, 3),
            "error": self.error,
        }


VERDICT_LINE = {
    policy.SAFE: "SAFE. Nothing in this plan weakens security or destroys anything that matters.",
    policy.REVIEW: "REQUIRES HUMAN REVIEW. There is real risk here, and it may be risk somebody has already decided to accept.",
    policy.BLOCK: "DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.",
}


def render_markdown(
    result: ReviewResult,
    plan_path: str,
    model_name: str = "",
    system: str = "",
    plan=None,
) -> str:
    """The report a DevOps engineer reads. Plain, short, and every claim sourced."""
    decision = result.decision
    lines = []
    lines.append("# CloudFix review")
    lines.append("")
    lines.append("**Plan:** `%s`" % plan_path)
    if system:
        lines.append("**Reviewed by:** %s" % system)
    if model_name:
        lines.append("**Model:** %s" % model_name)
    lines.append("")

    if result.error and decision is None:
        lines.append("## Verdict: could not complete")
        lines.append("")
        lines.append(result.error)
        return "\n".join(lines) + "\n"

    lines.append("## Verdict: %s" % decision.verdict)
    lines.append("")
    lines.append(VERDICT_LINE.get(decision.verdict, ""))
    if decision.summary:
        lines.append("")
        lines.append(decision.summary)
    if decision.rules:
        lines.append("")
        lines.append("Policy rules that fired: %s" % ", ".join(decision.rules))

    lines.append("")
    lines.append("## What is changing")
    lines.append("")
    if result.blast is not None:
        counts = result.blast.to_dict()["counts"]
        lines.append(
            "%d to create, %d to update, %d to replace, %d to destroy. Worst blast radius: **%s**."
            % (counts["create"], counts["update"], counts["replace"], counts["delete"], result.blast.worst_tier)
        )
        lines.append("")
        for impact in result.blast.notable():
            lines.append(
                "- `%s` will be **%sd** (%s, %s). %s"
                % (
                    impact.address,
                    impact.action,
                    impact.type,
                    impact.environment,
                    " ".join(impact.reasons),
                )
            )
        if not result.blast.notable():
            lines.append("- Nothing destructive in this plan.")
    elif plan is not None:
        # This rung has no blast radius analysis, so list the actions plainly
        # rather than pretending to an assessment it never made.
        acting = plan.acting_changes()
        if acting:
            for change in acting:
                lines.append(
                    "- `%s` will be **%sd** (%s, %s)"
                    % (change.address, change.action, change.type, change.environment)
                )
        else:
            lines.append("- Nothing. Every resource in this plan is a no-op.")
        lines.append("")
        lines.append("_This rung does not analyse blast radius._")
    else:
        lines.append("- (not analysed by this rung)")

    lines.append("")
    lines.append("## Why")
    lines.append("")
    if decision.reasons:
        for index, reason in enumerate(decision.reasons, start=1):
            head = "%d. %s" % (index, reason.claim)
            if reason.rule:
                head += " _(rule %s)_" % reason.rule
            lines.append(head)
            if reason.evidence_pointer:
                mark = {
                    True: "verified against the plan",
                    False: "DID NOT VERIFY",
                    None: "no verification pass in this rung",
                }[reason.supported]
                lines.append(
                    "   - evidence: `%s`%s  [%s]"
                    % (
                        reason.evidence_pointer,
                        (" = `%s`" % reason.expected_value) if reason.expected_value else "",
                        mark,
                    )
                )
    else:
        lines.append("No risk found that meets any policy rule.")

    if decision.dismissed:
        lines.append("")
        lines.append("## Checked and dismissed")
        lines.append("")
        for item in decision.dismissed:
            lines.append("- `%s` on `%s`: %s" % (item.check_id, item.resource_address, item.why))

    lines.append("")
    lines.append("## Raw findings from the deterministic checks")
    lines.append("")
    if result.findings:
        for finding in result.findings:
            lines.append(
                "- **%s** `%s` on `%s` (%s)"
                % (finding.severity.upper(), finding.check_id, finding.resource_address, finding.action)
            )
            for item in finding.evidence:
                lines.append("  - `%s` = `%s`" % (item.pointer, quote(item.value, 120)))
    else:
        lines.append("- None. No security check fired on this plan.")

    lines.append("")
    lines.append("## Human approval checkpoint")
    lines.append("")
    lines.append(policy.HUMAN_CHECKPOINT_TEXT)
    if decision.confirmations:
        lines.append("")
        lines.append("Before approving, confirm:")
        for item in decision.confirmations:
            lines.append("- [ ] %s" % item)
    lines.append("")
    return "\n".join(lines) + "\n"
