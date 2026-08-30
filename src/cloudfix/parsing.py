"""
Turning a model reply into a Decision.

Models wrap JSON in prose and in code fences, and they rename fields. This file
is the airlock: everything past it is a strict object, so no other file has to
care what shape the reply arrived in.

Parsing failures are handled the way the rest of the project handles errors. One
retry, and the retry is told exactly what was wrong. A silent fallback would let
a broken reply become a SAFE verdict, which is the worst possible failure for a
tool like this.
"""

import json
import re

from . import policy
from .decision import Decision, Dismissal, Reason


class ParseError(ValueError):
    pass


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_object(text: str) -> dict:
    if not text or not text.strip():
        raise ParseError("the reply was empty")

    candidates = []
    for match in _FENCE.finditer(text):
        candidates.append(match.group(1))
    candidates.append(text)

    for candidate in candidates:
        stripped = candidate.strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(stripped[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except ValueError:
                continue
    raise ParseError("no JSON object could be read out of the reply")


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def coerce_decision(payload: dict) -> Decision:
    if not isinstance(payload, dict):
        raise ParseError("expected a JSON object")

    raw_verdict = payload.get("verdict") or payload.get("decision") or payload.get("recommendation")
    verdict = policy.normalise(_text(raw_verdict))
    if not verdict:
        raise ParseError(
            'verdict must be one of "SAFE", "REQUIRES HUMAN REVIEW" or "DO NOT APPLY", got %r'
            % (raw_verdict,)
        )

    reasons = []
    for entry in _as_list(payload.get("reasons") or payload.get("findings")):
        if isinstance(entry, str):
            reasons.append(Reason(claim=entry.strip()))
            continue
        if not isinstance(entry, dict):
            continue
        claim = _text(entry.get("claim") or entry.get("reason") or entry.get("detail"))
        if not claim:
            continue
        reasons.append(
            Reason(
                claim=claim,
                evidence_pointer=_text(
                    entry.get("evidence_pointer")
                    or entry.get("pointer")
                    or entry.get("evidence")
                ),
                expected_value=_text(
                    entry.get("expected_value") or entry.get("value") or entry.get("quoted_value")
                ),
                rule=_text(entry.get("rule") or entry.get("policy_rule")),
            )
        )

    dismissed = []
    for entry in _as_list(payload.get("dismissed") or payload.get("dismissed_findings")):
        if not isinstance(entry, dict):
            continue
        check_id = _text(entry.get("check_id") or entry.get("id"))
        if not check_id:
            continue
        dismissed.append(
            Dismissal(
                check_id=check_id,
                resource_address=_text(entry.get("resource_address") or entry.get("resource")),
                why=_text(entry.get("why") or entry.get("reason")) or "(no reason given)",
            )
        )

    rules = [_text(r) for r in _as_list(payload.get("rules") or payload.get("policy_rules"))]
    rules = [r for r in rules if r]

    confirmations = [
        _text(c)
        for c in _as_list(
            payload.get("confirmations")
            or payload.get("human_checkpoint")
            or payload.get("confirm")
        )
    ]
    confirmations = [c for c in confirmations if c]

    return Decision(
        verdict=verdict,
        summary=_text(payload.get("summary")),
        rules=rules,
        reasons=reasons,
        dismissed=dismissed,
        confirmations=confirmations,
    )


def parse_decision(text: str) -> Decision:
    return coerce_decision(parse_json_object(text))
