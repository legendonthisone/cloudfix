"""
Evidence, and the machinery for proving a claim against it.

A finding without evidence is an opinion. Every finding CloudFix produces carries
a pointer into the original plan JSON, written the way a person would read it:

    resource_changes[3].change.after.publicly_accessible

`resolve` walks that pointer and returns the value actually sitting there. That
is what lets the verification step be a real check rather than a second opinion:
the model is asked to cite a path, the path is resolved against the plan, and a
citation that does not resolve, or that resolves to something other than what the
model said it would, is dropped.

No model is involved in this file. It is string parsing and dictionary lookups,
so it gives the same answer every time it runs.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")

MISSING = object()


class PointerError(ValueError):
    pass


def parse_pointer(pointer: str):
    """Turn resource_changes[3].change.after.foo into a list of steps."""
    if not isinstance(pointer, str) or not pointer.strip():
        raise PointerError("An evidence pointer must be a non empty string")
    steps = []
    position = 0
    text = pointer.strip()
    while position < len(text):
        if text[position] == ".":
            position += 1
            continue
        match = _TOKEN.match(text, position)
        if not match:
            raise PointerError("Could not read the pointer %r at character %d" % (pointer, position))
        key, index = match.group(1), match.group(2)
        steps.append(int(index) if index is not None else key)
        position = match.end()
    if not steps:
        raise PointerError("Empty evidence pointer %r" % pointer)
    return steps


def resolve(document: Any, pointer: str, default=MISSING):
    """Return the value a pointer points at, or default if it does not exist."""
    try:
        steps = parse_pointer(pointer)
    except PointerError:
        if default is MISSING:
            raise
        return default

    node = document
    for step in steps:
        if isinstance(step, int):
            if not isinstance(node, list) or step >= len(node) or step < -len(node):
                if default is MISSING:
                    raise PointerError("%s does not exist in this plan" % pointer)
                return default
            node = node[step]
        else:
            if not isinstance(node, dict) or step not in node:
                if default is MISSING:
                    raise PointerError("%s does not exist in this plan" % pointer)
                return default
            node = node[step]
    return node


def exists(document: Any, pointer: str) -> bool:
    """True when the pointer resolves, even if it resolves to null or false."""
    sentinel = object()
    return resolve(document, pointer, default=sentinel) is not sentinel


def quote(value: Any, limit: int = 200) -> str:
    """Render a value for display next to a finding."""
    if isinstance(value, str):
        rendered = value
    else:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(rendered) > limit:
        rendered = rendered[: limit - 3] + "..."
    return rendered


@dataclass
class Evidence:
    """One quoted fact from the plan, with the pointer that proves it."""

    pointer: str
    value: Any
    note: str = ""

    def to_dict(self) -> dict:
        return {"pointer": self.pointer, "value": self.value, "note": self.note}

    def render(self) -> str:
        line = "%s = %s" % (self.pointer, quote(self.value))
        return line + ("  (%s)" % self.note if self.note else "")


@dataclass
class Finding:
    """Something a deterministic check found in the plan.

    check_id, severity and evidence come from code. Nothing on this object was
    decided by a model, which is what makes the same plan produce the same
    findings on every run.
    """

    check_id: str
    title: str
    severity: str  # critical, high, medium, low
    resource_address: str
    resource_type: str
    action: str
    environment: str
    detail: str
    evidence: list = field(default_factory=list)
    # False when the risk was already true before this change. Policy rule R5
    # turns on this distinction, so it is a field rather than a sentence buried
    # in the detail text where only a human could find it.
    introduced_by_change: bool = True

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "severity": self.severity,
            "resource_address": self.resource_address,
            "resource_type": self.resource_type,
            "action": self.action,
            "environment": self.environment,
            "detail": self.detail,
            "introduced_by_change": self.introduced_by_change,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    def render(self) -> str:
        lines = [
            "[%s] %s  (%s)" % (self.severity.upper(), self.title, self.check_id),
            "  resource: %s  action: %s  environment: %s"
            % (self.resource_address, self.action, self.environment),
            "  %s" % self.detail,
        ]
        if not self.introduced_by_change:
            # State the fact and stop. Naming the policy rule here would be the
            # check doing the judging, which is the one thing the split between
            # code and model exists to prevent. Mapping a fact to a rule is the
            # model's job, and the verifier checks that mapping afterwards.
            lines.append(
                "  introduced_by_change: false. This exact exposure was already "
                "present in the before state of this plan."
            )
        for item in self.evidence:
            lines.append("  evidence: %s" % item.render())
        return "\n".join(lines)


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def sort_findings(findings):
    return sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.resource_address, f.check_id),
    )


def check_citation(plan_document: Any, pointer: str, claimed_value: Optional[str] = None) -> Tuple[bool, str]:
    """Can this citation be proved against the plan.

    Returns (supported, reason). Used by the verification pass, which is why it
    never raises: an unreadable pointer is an unsupported claim, not a crash.
    """
    sentinel = object()
    try:
        value = resolve(plan_document, pointer, default=sentinel)
    except PointerError as exc:
        return False, str(exc)
    if value is sentinel:
        return False, "pointer %s does not exist in this plan" % pointer
    if claimed_value is None or str(claimed_value).strip() == "":
        return True, "resolved to %s" % quote(value)

    actual = quote(value, limit=400)
    claimed = str(claimed_value).strip()
    if claimed == actual or claimed.strip('"') == actual.strip('"') or claimed in actual:
        return True, "resolved to %s" % actual
    return False, "pointer %s resolves to %s, not %s" % (pointer, actual, claimed)
