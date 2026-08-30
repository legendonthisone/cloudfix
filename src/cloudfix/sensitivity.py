"""
How much of the result depends on labels a reasonable person would argue with.

The deepest fair criticism of this evaluation is that the cases are mine, the
policy is mine and the scorer is mine, so a 16/16 measures conformance to my own
judgement. That criticism cannot be answered by adding more of my own cases. It
can be answered by showing what happens when you refuse to accept the two labels
most worth refusing, and publishing the answer whether or not it flatters me.

Two labels are genuinely contested. Both were argued for by external reviewers
reading this repository before submission:

  c15_preexisting_open_port   Labelled REQUIRES HUMAN REVIEW under rule R5. The
                              counter argument is that a tag only deploy
                              introduces nothing, so the deploy is SAFE and the
                              standing exposure belongs in a separate ticket.
                              That is how many platform teams actually work.

  c12_dev_static_website      Labelled REQUIRES HUMAN REVIEW under rule R2. The
                              counter argument is that a bucket tagged
                              development, tagged public, and carrying a website
                              configuration has already declared its intent, so
                              SAFE is defensible without a human.

Run it with:

    python run.py sensitivity

It reads only `results/*_results.json` and `data/cases.json`, so it re-scores the
verdicts that were actually produced. No model is called and nothing is re-run.
"""

import json
import os
from typing import Dict, List

from . import policy
from .cases import load_cases

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS_DIR = os.path.join(_PROJECT_ROOT, "results")

# Each entry: case id, the alternative label, and the argument for it.
CONTESTED = (
    (
        "c15_preexisting_open_port",
        policy.SAFE,
        "a tag only deploy introduces no new exposure, so the deploy is safe and "
        "the standing SSH rule is a separate ticket",
    ),
    (
        "c12_dev_static_website",
        policy.SAFE,
        "a bucket tagged development and public with a website configuration has "
        "declared its intent, so no human is needed",
    ),
)

HEADLINE_SYSTEMS = ("baseline", "scanner", "agent")

DISPLAY = {
    "baseline": "One prompt, no tools",
    "scanner": "Scanner baseline",
    "agent": "CloudFix",
}


def load_found_verdicts(system: str) -> Dict[str, str]:
    path = os.path.join(RESULTS_DIR, "%s_results.json" % system)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {row["case_id"]: row["found_verdict"] for row in data["per_case"]}


def score_against(labels: Dict[str, str], found: Dict[str, str]) -> Dict[str, int]:
    correct = dangerous = over = 0
    for case_id, expected in labels.items():
        got = found.get(case_id, "")
        if got == expected:
            correct += 1
        if policy.SEVERITY_RANK.get(got, 9) > policy.SEVERITY_RANK[expected]:
            dangerous += 1
        if got == policy.BLOCK and expected != policy.BLOCK:
            over += 1
    return {"correct": correct, "dangerous": dangerous, "over_block": over, "total": len(labels)}


def scenarios() -> List[dict]:
    published = {case.id: case.expected_verdict for case in load_cases()}
    out = [{"name": "As published", "labels": dict(published), "changed": []}]
    for case_id, alternative, _ in CONTESTED:
        labels = dict(published)
        labels[case_id] = alternative
        out.append(
            {"name": "%s as SAFE" % case_id.split("_")[0], "labels": labels, "changed": [case_id]}
        )
    both = dict(published)
    for case_id, alternative, _ in CONTESTED:
        both[case_id] = alternative
    out.append(
        {
            "name": "Both as SAFE",
            "labels": both,
            "changed": [case_id for case_id, _, _ in CONTESTED],
        }
    )
    return out


def build_table(systems=HEADLINE_SYSTEMS) -> str:
    found = {name: load_found_verdicts(name) for name in systems}
    if not all(found.values()):
        return "(no results on disk, run the evaluation first)"

    header = "| Ground truth used | " + " | ".join(DISPLAY.get(n, n) for n in systems) + " |"
    lines = [header, "|---" * (len(systems) + 1) + "|"]
    for scenario in scenarios():
        cells = []
        for name in systems:
            s = score_against(scenario["labels"], found[name])
            cells.append("%d/%d" % (s["correct"], s["total"]))
        lines.append("| %s | %s |" % (scenario["name"], " | ".join(cells)))

    lines.append("")
    lines.append("Dangerous misses under the same four labellings:")
    lines.append("")
    lines.append(header.replace("Ground truth used", "Ground truth used"))
    lines.append("|---" * (len(systems) + 1) + "|")
    for scenario in scenarios():
        cells = []
        for name in systems:
            s = score_against(scenario["labels"], found[name])
            cells.append("%d/%d" % (s["dangerous"], s["total"]))
        lines.append("| %s | %s |" % (scenario["name"], " | ".join(cells)))
    return "\n".join(lines)


def main(argv=None):
    print(__doc__.strip().split("Run it with:")[0].strip())
    print()
    print(build_table())
    print()
    found = {name: load_found_verdicts(name) for name in HEADLINE_SYSTEMS}
    if all(found.values()):
        published = {case.id: case.expected_verdict for case in load_cases()}
        both = dict(published)
        for case_id, alternative, _ in CONTESTED:
            both[case_id] = alternative
        a = score_against(published, found["agent"])
        b = score_against(both, found["agent"])
        base_a = score_against(published, found["baseline"])
        base_b = score_against(both, found["baseline"])
        print(
            "Read it this way. Against the scanner the result does not move at all. "
            "Against the unaided prompt it moves from %d/%d versus %d/%d to %d/%d versus "
            "%d/%d, so the accuracy gap over that baseline rests entirely on two "
            "contested labels."
            % (
                a["correct"], a["total"], base_a["correct"], base_a["total"],
                b["correct"], b["total"], base_b["correct"], base_b["total"],
            )
        )
        print(
            "What does not move under any labelling is the direction of the errors: "
            "CloudFix records %d and %d dangerous misses across the two extremes, "
            "because when it is wrong it is wrong toward caution."
            % (a["dangerous"], b["dangerous"])
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
