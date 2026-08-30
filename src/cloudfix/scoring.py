"""
Scoring, applied identically to every system.

The primary metric is verdict accuracy: did the system return the verdict the
ground truth says the plan deserves. One number, sixteen cases, no partial marks.

Four secondary metrics, because verdict accuracy alone hides the difference
between the two ways of being wrong:

  dangerous miss rate      said something was safer than it is. This is the
                           failure that actually costs a company money
  over block rate          said DO NOT APPLY to a plan that did not deserve it.
                           This is the failure that gets a tool switched off
  critical catch rate      did the review name the resource that mattered
  unsupported citation     share of cited evidence pointers that do not resolve
  rate                     in the plan. Computed here for every system, including
                           the ones that never ran a verification pass, so the
                           number is comparable across the whole ladder
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from . import policy
from .evidence import check_citation


@dataclass
class CaseScore:
    case_id: str
    difficulty: str
    expected_verdict: str
    found_verdict: str
    verdict_correct: bool
    direction: str  # exact, over, under, none
    dangerous_miss: bool
    over_block: bool
    caught_critical: Optional[bool]
    reasons_total: int
    reasons_with_pointer: int
    reasons_unsupported: int
    dismissed_total: int
    repairs: int
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "difficulty": self.difficulty,
            "expected_verdict": self.expected_verdict,
            "found_verdict": self.found_verdict,
            "verdict_correct": self.verdict_correct,
            "direction": self.direction,
            "dangerous_miss": self.dangerous_miss,
            "over_block": self.over_block,
            "caught_critical": self.caught_critical,
            "reasons_total": self.reasons_total,
            "reasons_with_pointer": self.reasons_with_pointer,
            "reasons_unsupported": self.reasons_unsupported,
            "dismissed_total": self.dismissed_total,
            "repairs": self.repairs,
            "error": self.error,
        }


_INDEX = re.compile(r"resource_changes\[(\d+)\]")


def _cited_by_pointer(decision, plan) -> set:
    """Which resources the cited pointers actually land on.

    A pointer such as resource_changes[0].change.actions names its resource by
    position, not by name. Resolving the position to an address is the difference
    between measuring whether a review found the right resource and measuring
    whether it happened to spell the address out in prose.
    """
    found = set()
    for reason in decision.reasons:
        for match in _INDEX.finditer(reason.evidence_pointer or ""):
            index = int(match.group(1))
            if 0 <= index < len(plan.changes):
                found.add(plan.changes[index].address)
    return found


def _mentions_resource(decision, address: str, plan) -> bool:
    if not address:
        return False
    if address in _cited_by_pointer(decision, plan):
        return True
    haystack = " ".join(
        [decision.summary or ""]
        + [r.claim for r in decision.reasons]
        + [r.evidence_pointer for r in decision.reasons]
        + [r.expected_value for r in decision.reasons]
    )
    if address in haystack:
        return True
    short = address.split(".")[-1]
    return bool(short) and short in haystack


def score_review(case, result, plan) -> CaseScore:
    decision = result.decision
    expected = case.expected_verdict

    if decision is None:
        return CaseScore(
            case_id=case.id,
            difficulty=case.difficulty,
            expected_verdict=expected,
            found_verdict="",
            verdict_correct=False,
            direction="none",
            dangerous_miss=True,
            over_block=False,
            caught_critical=False if case.critical_resource else None,
            reasons_total=0,
            reasons_with_pointer=0,
            reasons_unsupported=0,
            dismissed_total=0,
            repairs=result.repairs,
            error=result.error or "no decision produced",
        )

    found = decision.verdict
    correct = found == expected
    expected_rank = policy.SEVERITY_RANK[expected]
    found_rank = policy.SEVERITY_RANK.get(found, 9)

    if correct:
        direction = "exact"
    elif found_rank > expected_rank:
        direction = "under"  # judged the plan safer than it is
    else:
        direction = "over"

    dangerous_miss = direction == "under"
    over_block = found == policy.BLOCK and expected != policy.BLOCK

    with_pointer = 0
    unsupported = 0
    for reason in decision.reasons:
        pointer = (reason.evidence_pointer or "").strip()
        if not pointer:
            unsupported += 1
            continue
        with_pointer += 1
        supported, _ = check_citation(plan.raw, pointer, reason.expected_value)
        if not supported:
            unsupported += 1

    caught = None
    if case.critical_resource:
        caught = _mentions_resource(decision, case.critical_resource, plan)

    return CaseScore(
        case_id=case.id,
        difficulty=case.difficulty,
        expected_verdict=expected,
        found_verdict=found,
        verdict_correct=correct,
        direction=direction,
        dangerous_miss=dangerous_miss,
        over_block=over_block,
        caught_critical=caught,
        reasons_total=len(decision.reasons),
        reasons_with_pointer=with_pointer,
        reasons_unsupported=unsupported,
        dismissed_total=len(decision.dismissed),
        repairs=result.repairs,
        error=result.error,
    )


def _rate(numerator, denominator):
    return round(numerator / float(denominator), 4) if denominator else 0.0


def aggregate(scores: List[CaseScore]) -> dict:
    total = len(scores)
    correct = sum(1 for s in scores if s.verdict_correct)
    reasons_total = sum(s.reasons_total for s in scores)
    unsupported = sum(s.reasons_unsupported for s in scores)
    critical_cases = [s for s in scores if s.caught_critical is not None]

    by_difficulty = {}
    counts_by_difficulty = {}
    for level in ("easy", "medium", "hard"):
        subset = [s for s in scores if s.difficulty == level]
        if subset:
            by_difficulty[level] = _rate(sum(1 for s in subset if s.verdict_correct), len(subset))
            counts_by_difficulty[level] = {
                "correct": sum(1 for s in subset if s.verdict_correct),
                "total": len(subset),
            }

    return {
        # Every rate below is published with its denominator beside it, because a
        # percentage over sixteen cases invites a reader to imagine a larger
        # experiment than the one that was run.
        "cases": total,
        "correct": correct,
        "verdict_accuracy": _rate(correct, total),
        "dangerous_miss_rate": _rate(sum(1 for s in scores if s.dangerous_miss), total),
        "over_block_rate": _rate(sum(1 for s in scores if s.over_block), total),
        "critical_catch_rate": _rate(
            sum(1 for s in critical_cases if s.caught_critical), len(critical_cases)
        ),
        "critical_resource_cases": len(critical_cases),
        "critical_resource_caught": sum(1 for s in critical_cases if s.caught_critical),
        "unsupported_citation_rate": _rate(unsupported, reasons_total),
        "reasons_total": reasons_total,
        "reasons_unsupported": unsupported,
        "dismissals_total": sum(s.dismissed_total for s in scores),
        "repairs_total": sum(s.repairs for s in scores),
        "accuracy_by_difficulty": by_difficulty,
        "counts_by_difficulty": counts_by_difficulty,
        "wrong_cases": [s.case_id for s in scores if not s.verdict_correct],
        "dangerous_miss_cases": [s.case_id for s in scores if s.dangerous_miss],
        "over_block_cases": [s.case_id for s in scores if s.over_block],
        "errors": [s.case_id for s in scores if s.error],
    }
