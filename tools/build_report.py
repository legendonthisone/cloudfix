#!/usr/bin/env python3
"""
Turn the results files into the markdown tables used in README.md and
IMPROVEMENT_CHANGELOG.md.

Run it after an evaluation:

    python tools/build_report.py

It reads only `results/*_results.json`, so every table in the documentation comes
out of a file a judge can open, and no figure in this project is typed by hand.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cloudfix.cases import load_cases  # noqa: E402
from cloudfix.run_eval import LADDER, LADDER_LABELS  # noqa: E402

RESULTS = os.path.join(ROOT, "results")


def load(system):
    path = os.path.join(RESULTS, "%s_results.json" % system)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def pct(value):
    return "%.0f%%" % (value * 100)


def headline_table(systems=("baseline", "scanner", "agent")):
    loaded = [(name, load(name)) for name in systems]
    loaded = [(name, data) for name, data in loaded if data]
    if not loaded:
        return "(no results yet)"

    names = {
        "baseline": "One prompt, no tools",
        "scanner": "Scanner baseline",
        "agent": "CloudFix",
    }
    header = "| Metric | " + " | ".join(names.get(n, n) for n, _ in loaded) + " |"
    divider = "|---" * (len(loaded) + 1) + "|"
    # Fractions, never bare percentages. Sixteen cases is a small number and the
    # denominator is the reader's only defence against reading it as a large one.
    rows = [
        ("Verdict accuracy (primary)", lambda d: "%d/%d" % (d["correct"], d["cases"])),
        ("Dangerous misses", lambda d: "%d/%d" % (
            len(d["dangerous_miss_cases"]), d["cases"])),
        ("Over blocked", lambda d: "%d/%d" % (len(d["over_block_cases"]), d["cases"])),
        ("The 5 hard cases", lambda d: "%d/%d" % (
            d["counts_by_difficulty"]["hard"]["correct"],
            d["counts_by_difficulty"]["hard"]["total"])),
        ("Citations that do not resolve", lambda d: "%d/%d" % (
            d["reasons_unsupported"], d["reasons_total"])),
        ("Model seconds per review", lambda d: "%.1f" % d.get("mean_model_seconds_per_review", 0)),
        ("Cost per review (USD)", lambda d: "%.5f" % d["cost_usd_per_review"]),
    ]
    lines = [header, divider]
    for label, render in rows:
        lines.append("| %s | %s |" % (label, " | ".join(render(d) for _, d in loaded)))
    return "\n".join(lines)


def ladder_table():
    lines = [
        "| What is in the system | Verdict accuracy | Change | Dangerous misses | Over blocked |",
        "|---|---|---|---|---|",
    ]
    previous = None
    for name in LADDER:
        data = load(name)
        if not data:
            continue
        accuracy = data["verdict_accuracy"] * 100
        change = "baseline" if previous is None else "%+.0f pts" % (accuracy - previous)
        lines.append(
            "| %s | **%d/%d** | %s | %d/%d | %d/%d |"
            % (
                LADDER_LABELS[name],
                data["correct"],
                data["cases"],
                change,
                len(data["dangerous_miss_cases"]),
                data["cases"],
                len(data["over_block_cases"]),
                data["cases"],
            )
        )
        previous = accuracy
    return "\n".join(lines)


def per_case_table(systems=("baseline", "scanner", "agent")):
    loaded = [(name, load(name)) for name in systems]
    loaded = [(name, data) for name, data in loaded if data]
    if not loaded:
        return "(no results yet)"
    by_system = {
        name: {row["case_id"]: row for row in data["per_case"]} for name, data in loaded
    }
    short = {"SAFE": "SAFE", "REQUIRES HUMAN REVIEW": "REVIEW", "DO NOT APPLY": "BLOCK", "": "none"}

    lines = [
        "| Case | Difficulty | Ground truth | " + " | ".join(n for n, _ in loaded) + " |",
        "|---" * (3 + len(loaded)) + "|",
    ]
    for case in load_cases():
        cells = []
        for name, _ in loaded:
            row = by_system[name].get(case.id)
            if not row:
                cells.append("-")
                continue
            mark = short.get(row["found_verdict"], row["found_verdict"])
            cells.append(mark if row["verdict_correct"] else "**%s**" % mark)
        lines.append(
            "| `%s` | %s | %s | %s |"
            % (case.id, case.difficulty, short[case.expected_verdict], " | ".join(cells))
        )
    lines.append("")
    lines.append("Bold marks a wrong verdict.")
    return "\n".join(lines)


def consistency_table():
    path = os.path.join(RESULTS, "consistency.json")
    if not os.path.exists(path):
        return "(consistency study not run yet)"
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    lines = [
        "| System | Verdict accuracy per run | Same verdict every run |",
        "|---|---|---|",
    ]
    for report in payload["reports"]:
        values = report["verdict_accuracy_by_sample"]
        cases = report["cases"]
        per_run = ", ".join("%d/%d" % (round(v * cases), cases) for v in values) or "n/a"
        stable = "%d/%d" % (round(report["verdict_stability"] * cases), cases)
        lines.append("| %s | %s | %s |" % (report["system"], per_run, stable))
    return "\n".join(lines)


def totals():
    out = []
    for name in LADDER:
        data = load(name)
        if not data:
            continue
        out.append(
            "%-26s accuracy %5s  dangerous %d  overblock %d  wrong: %s"
            % (
                name,
                "%d/%d" % (data["correct"], data["cases"]),
                len(data["dangerous_miss_cases"]),
                len(data["over_block_cases"]),
                ", ".join(data["wrong_cases"]) or "none",
            )
        )
    return "\n".join(out)


def main():
    print("## Headline comparison\n")
    print(headline_table())
    print("\n\n## Ablation ladder\n")
    print(ladder_table())
    print("\n\n## Every case\n")
    print(per_case_table())
    print("\n\n## Consistency\n")
    print(consistency_table())
    print("\n\n## Summary lines\n")
    print(totals())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
