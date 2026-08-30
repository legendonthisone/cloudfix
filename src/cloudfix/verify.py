"""
The verification pass.

This is the part the whole project is an argument about. A language model asked
"is your answer right?" will say yes. So nothing here asks it anything. Every
rule below is ordinary code comparing the decision it was handed against the plan
it came from.

Five rules:

  V1  every reason must cite a pointer that resolves in this plan, to the value
      it says it resolves to
  V2  a SAFE verdict may not simply ignore a critical finding or a severe blast
      radius. Dismiss it in writing or do not call the plan safe
  V3  a DO NOT APPLY verdict must give at least one reason
  V4  you may not dismiss a finding that never fired
  V5  a risk this change did not introduce may not be dismissed into SAFE. The
      published policy already routes those to a human under rule R5

V5 was added after watching the loop fail. On c15_preexisting_open_port the agent
dismissed a standing SSH exposure in writing, correctly observing that the change
did not cause it, and returned SAFE. V2 accepted that, because V2 only asked
whether a dismissal existed, never whether the dismissal was allowed to reach the
verdict it reached. R5 had been written before any of this ran. The verifier
simply was not enforcing a rule the policy already contained.

When a rule fails, the decision goes back to the model with a numbered list of
exactly what is wrong. That is the loop. The model is allowed to be wrong. It is
not allowed to be wrong and unchallenged.
"""

from dataclasses import dataclass, field
from typing import List

from . import policy
from .evidence import check_citation


@dataclass
class Verdict:
    passed: bool
    defects: List[str] = field(default_factory=list)
    rules_run: List[str] = field(default_factory=list)
    unsupported_reasons: int = 0
    checked_citations: int = 0

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "defects": self.defects,
            "rules_run": self.rules_run,
            "unsupported_reasons": self.unsupported_reasons,
            "checked_citations": self.checked_citations,
        }

    def repair_instruction(self) -> str:
        lines = [
            "Your decision did not pass verification. Each numbered problem below was "
            "produced by comparing what you wrote against the plan itself, not by a "
            "second opinion.",
            "",
        ]
        for index, defect in enumerate(self.defects, start=1):
            lines.append("%d. %s" % (index, defect))
        lines.append("")
        lines.append(
            "Return the corrected decision as JSON in the same shape. Drop any claim you "
            "cannot point at a real line of the plan for. Do not invent a new pointer to "
            "save a claim. If dropping a claim changes the verdict, change the verdict."
        )
        return "\n".join(lines)


def _dismissed_keys(decision) -> set:
    keys = set()
    for item in decision.dismissed:
        keys.add((item.check_id or "").strip().upper())
        keys.add(
            ((item.check_id or "").strip().upper(), (item.resource_address or "").strip())
        )
    return keys


def _cited_addresses(decision) -> str:
    return " ".join(
        "%s %s %s" % (r.claim, r.evidence_pointer, r.expected_value) for r in decision.reasons
    )


def verify(decision, plan_document, findings, blast_report) -> Verdict:
    defects: List[str] = []
    rules_run = ["V1", "V2", "V3", "V4", "V5"]
    unsupported = 0
    checked = 0

    # V1. Every reason points at something real.
    for index, reason in enumerate(decision.reasons, start=1):
        pointer = (reason.evidence_pointer or "").strip()
        if not pointer:
            reason.supported = False
            reason.support_note = "no evidence pointer given"
            unsupported += 1
            defects.append(
                "Reason %d (%s) cites no evidence. Every reason must name a pointer into "
                "the plan, for example resource_changes[2].change.after.publicly_accessible."
                % (index, reason.claim[:80])
            )
            continue
        checked += 1
        supported, note = check_citation(plan_document, pointer, reason.expected_value)
        reason.supported = supported
        reason.support_note = note
        if not supported:
            unsupported += 1
            defects.append(
                "Reason %d cites %s, and that is not what the plan says: %s. Either cite the "
                "line that actually proves the claim, or drop the claim."
                % (index, pointer, note)
            )

    # V2. A SAFE verdict cannot walk past a critical finding or a severe blast radius.
    if decision.verdict == policy.SAFE:
        dismissed = _dismissed_keys(decision)
        cited = _cited_addresses(decision)
        for finding in findings:
            serious = finding.severity == "critical" or (
                finding.severity == "high" and finding.environment == "production"
            )
            if not serious:
                continue
            key = finding.check_id.strip().upper()
            if key in dismissed or (key, finding.resource_address) in dismissed:
                continue
            if finding.resource_address in cited:
                continue
            defects.append(
                "You returned SAFE while the %s finding %s on %s still stands. Either add it "
                "to dismissed with a reason that the plan supports, or the verdict is not SAFE."
                % (finding.severity, finding.check_id, finding.resource_address)
            )
        if blast_report is not None:
            for impact in blast_report.impacts:
                if impact.tier != "severe":
                    continue
                if impact.address in cited or "BLAST_RADIUS" in dismissed:
                    continue
                defects.append(
                    "You returned SAFE while %s is being %sd and that is a severe blast "
                    "radius (%s). Address it or change the verdict."
                    % (impact.address, impact.action, "; ".join(impact.reasons)[:160])
                )

    # V3. Blocking a deploy without saying why is not a decision.
    if decision.verdict == policy.BLOCK and not decision.reasons:
        defects.append(
            "The verdict is DO NOT APPLY but no reason was given. Nobody can act on that."
        )

    # V5. A risk this change did not cause is not dismissible into SAFE.
    # Policy rule R5 sends it to a human. Blocking the deploy would be wrong,
    # because the deploy did not cause it. Calling the plan SAFE is also wrong,
    # because the risk is still standing there.
    if decision.verdict == policy.SAFE:
        for finding in findings:
            if finding.introduced_by_change:
                continue
            serious = finding.severity in ("critical", "high") or (
                finding.environment == "production" and finding.severity == "medium"
            )
            if not serious:
                continue
            defects.append(
                "You returned SAFE and dismissed %s on %s because this change did not "
                "introduce it. The observation is right and the verdict is not. Policy "
                "rule R5 covers exactly this: a risk that was already true is still a "
                "risk, it just is not this deploy's fault, so it goes to a human. The "
                "verdict is REQUIRES HUMAN REVIEW."
                % (finding.check_id, finding.resource_address)
            )

    # V4. You cannot dismiss something that never fired.
    fired = {f.check_id.strip().upper() for f in findings}
    for item in decision.dismissed:
        key = (item.check_id or "").strip().upper()
        if key and key not in fired and key != "BLAST_RADIUS":
            defects.append(
                "You dismissed %s, but no check with that id fired on this plan. Dismiss only "
                "findings that are in the list you were given." % item.check_id
            )

    return Verdict(
        passed=not defects,
        defects=defects,
        rules_run=rules_run,
        unsupported_reasons=unsupported,
        checked_citations=checked,
    )
