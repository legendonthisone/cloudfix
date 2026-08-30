"""
The evaluation runner.

Runs any rung of the ladder over the same sixteen cases, scores them all with the
same scorer, writes every review and every trajectory to disk, and prints the
comparison.

  python run.py eval --system both --mode replay
  python run.py eval --system ladder --mode replay
  python run.py eval --system agent --cases c07_prod_db_replace_clean
  python run.py eval --system both --samples 3
"""

import argparse
import json
import os
import sys
import time

from . import agent as agent_system
from . import baseline as baseline_system
from . import policy
from . import scanner as scanner_system
from .cases import load_cases
from .decision import render_markdown
from .model import ModelClient, ModelError, estimate_cost_usd
from .scoring import aggregate, score_review

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS_DIR = os.path.join(_PROJECT_ROOT, "results")
TRAJECTORY_DIR = os.path.join(_PROJECT_ROOT, "trajectories")
REVIEW_DIR = os.path.join(RESULTS_DIR, "reviews")


# The ladder. Rungs 1 to 5 each change exactly one thing from the rung above, so
# the difference between two rows is attributable to that change and nothing
# else. The sixth row is the system that actually ships, which is rung 3 plus
# verification, because rung 4 showed the blast radius summary made the model
# worse and rung 5 showed verification catching that damage.
LADDER = [
    "baseline",
    "scanner",
    "agent-checks",
    "agent-checks-blast",
    "agent-checks-blast-verify",
    "agent",
]

LADDER_LABELS = {
    "baseline": "One prompt, policy in the prompt, no tools",
    "scanner": "Deterministic checks plus a fixed severity gate, no model",
    "agent-checks": "Model judges the deterministic checks",
    "agent-checks-blast": "Plus the blast radius summary in the prompt",
    "agent-checks-blast-verify": "Plus the verification pass",
    "agent": "SHIPPED: checks plus verification, blast out of the prompt",
}

AGENT_OPTIONS = {
    "agent": {"use_blast": False, "verify_enabled": True},
    "agent-checks-blast-verify": {"use_blast": True, "verify_enabled": True},
    "agent-checks-blast": {"use_blast": True, "verify_enabled": False},
    "agent-checks": {"use_blast": False, "verify_enabled": False},
}

USES_MODEL = {"baseline"} | set(AGENT_OPTIONS)


def _ensure(path):
    os.makedirs(path, exist_ok=True)
    return path


def run_system(name, cases, client, quiet=False):
    records = []
    for index, case in enumerate(cases, start=1):
        if not quiet:
            sys.stdout.write("  [%2d/%2d] %-30s " % (index, len(cases), case.id))
            sys.stdout.flush()

        plan = case.load()
        started = time.time()
        try:
            if name == "baseline":
                result = baseline_system.review(plan, client)
            elif name == "scanner":
                result = scanner_system.review(plan)
            else:
                result = agent_system.review(plan, client, **AGENT_OPTIONS[name])
        except ModelError:
            raise
        except Exception as exc:  # noqa: BLE001 - a crash is a result, record it
            from .decision import ReviewResult

            result = ReviewResult(
                decision=None, seconds=time.time() - started, error="crashed: %s" % exc
            )

        score = score_review(case, result, plan)
        records.append({"case": case, "plan": plan, "result": result, "score": score})

        if not quiet:
            mark = "ok   " if score.verdict_correct else "WRONG"
            print(
                "%s  got %-22s expected %-22s %s"
                % (
                    mark,
                    score.found_verdict or "(none)",
                    score.expected_verdict,
                    "repairs %d" % score.repairs if score.repairs else "",
                )
            )
    return records


def write_outputs(name, records, model_name):
    _ensure(RESULTS_DIR)
    _ensure(os.path.join(TRAJECTORY_DIR, name))
    _ensure(os.path.join(REVIEW_DIR, name))

    for record in records:
        case, result, plan = record["case"], record["result"], record["plan"]

        with open(
            os.path.join(REVIEW_DIR, name, case.id + ".md"), "w", encoding="utf-8"
        ) as handle:
            handle.write(
                render_markdown(
                    result,
                    plan_path="data/plans/" + case.plan_file,
                    model_name=model_name if name in USES_MODEL else "none, this rung uses no model",
                    system=name,
                    plan=plan,
                )
            )

        trajectory = {
            "system": name,
            "case_id": case.id,
            "case_title": case.title,
            "model": model_name if name in USES_MODEL else None,
            "plan_file": "data/plans/" + case.plan_file,
            "ground_truth": {
                "expected_verdict": case.expected_verdict,
                "rules": case.rules,
                "why": case.why,
                "difficulty": case.difficulty,
            },
            "how_to_read": (
                "Steps run in order. kind=tool is deterministic code, kind=model is a "
                "call to the language model, kind=skipped is a step this rung "
                "deliberately removed. Every model step carries the exact "
                "system_prompt and user_prompt it was sent, so the run can be "
                "followed from the instructions through to the verdict. A verify "
                "step's output.defects is the feedback handed back to the model, and "
                "the repair step after it shows what it did with that feedback."
            ),
            "steps": result.steps,
            "repairs": result.repairs,
            "error": result.error,
            "final_decision": result.decision.to_dict() if result.decision else None,
            "human_checkpoint": policy.HUMAN_CHECKPOINT_TEXT,
            "score": record["score"].to_dict(),
        }
        with open(
            os.path.join(TRAJECTORY_DIR, name, case.id + ".json"), "w", encoding="utf-8"
        ) as handle:
            json.dump(trajectory, handle, indent=2, ensure_ascii=False)

    scores = [r["score"] for r in records]
    summary = aggregate(scores)
    summary["system"] = name
    summary["label"] = LADDER_LABELS.get(name, name)
    summary["model"] = model_name if name in USES_MODEL else None
    summary["mean_model_seconds_per_review"] = round(
        sum(r["result"].model_seconds for r in records) / float(len(records)), 2
    )
    summary["total_input_tokens"] = sum(r["result"].input_tokens for r in records)
    summary["total_output_tokens"] = sum(r["result"].output_tokens for r in records)
    summary["total_model_calls"] = sum(r["result"].model_calls for r in records)
    summary["cost_usd_total"] = round(
        estimate_cost_usd(summary["total_input_tokens"], summary["total_output_tokens"]), 4
    )
    summary["cost_usd_per_review"] = round(summary["cost_usd_total"] / float(len(records)), 5)
    summary["per_case"] = [s.to_dict() for s in scores]

    path = os.path.join(RESULTS_DIR, "%s_results.json" % name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
    return summary, path


def print_ladder(summaries):
    lookup = {s["system"]: s for s in summaries}
    print()
    print("ABLATION LADDER, each row adds one design choice")
    print("%-62s %-9s %-8s %-9s %-9s"
          % ("WHAT IS IN THE SYSTEM", "VERDICT", "CHANGE", "DANGEROUS", "OVERBLOCK"))
    print("-" * 104)
    previous = None
    for name in LADDER:
        summary = lookup.get(name)
        if not summary:
            continue
        accuracy = summary["verdict_accuracy"] * 100
        change = "" if previous is None else "%+.0f pts" % (accuracy - previous)
        print(
            "%-62s %-9s %-8s %-9s %-9s"
            % (
                LADDER_LABELS[name],
                "%.0f%%" % accuracy,
                change,
                "%.0f%%" % (summary["dangerous_miss_rate"] * 100),
                "%.0f%%" % (summary["over_block_rate"] * 100),
            )
        )
        previous = accuracy
    print()
    for name in LADDER:
        summary = lookup.get(name)
        if summary and summary["wrong_cases"]:
            print("%-22s wrong on: %s" % (name, ", ".join(summary["wrong_cases"])))


def print_comparison(summaries):
    if len(summaries) < 2:
        return
    left = next((s for s in summaries if s["system"] == "baseline"), None)
    right = next((s for s in summaries if s["system"] == "agent"), None)
    middle = next((s for s in summaries if s["system"] == "scanner"), None)
    if not left or not right:
        return

    def pct(value):
        return "%.0f%%" % (value * 100)

    columns = ["METRIC", "BASELINE"]
    if middle:
        columns.append("SCANNER")
    columns.append("CLOUDFIX")

    rows = [
        ("Verdict accuracy (primary)", "verdict_accuracy", pct),
        ("Dangerous misses", "dangerous_miss_rate", pct),
        ("Over blocking", "over_block_rate", pct),
        ("Critical resource named", "critical_catch_rate", pct),
        ("Unsupported citations", "unsupported_citation_rate", pct),
    ]

    width = "%-30s %-14s" + (" %-14s" if middle else "") + " %-14s"
    print()
    print(width % tuple(columns))
    print("-" * (76 if middle else 62))
    for label, key, render in rows:
        values = [render(left[key])]
        if middle:
            values.append(render(middle[key]))
        values.append(render(right[key]))
        print(width % tuple([label] + values))

    seconds = [
        "%.1f" % left.get("mean_model_seconds_per_review", 0.0),
    ]
    costs = ["%.5f" % left["cost_usd_per_review"]]
    if middle:
        seconds.append("%.1f" % middle.get("mean_model_seconds_per_review", 0.0))
        costs.append("%.5f" % middle["cost_usd_per_review"])
    seconds.append("%.1f" % right.get("mean_model_seconds_per_review", 0.0))
    costs.append("%.5f" % right["cost_usd_per_review"])
    print(width % tuple(["Model time per review (s)"] + seconds))
    print(width % tuple(["Cost per review (USD)"] + costs))

    print()
    for summary in (left, middle, right):
        if summary and summary["wrong_cases"]:
            print("%-22s wrong on: %s" % (summary["system"], ", ".join(summary["wrong_cases"])))


def consistency_report(system_name, sample_scores):
    """Does the same plan get the same verdict every time it is reviewed.

    A reviewer whose answer moves between runs is a reviewer you cannot put in
    front of a change freeze.
    """
    by_case = {}
    for scores in sample_scores:
        for score in scores:
            by_case.setdefault(score.case_id, []).append(score.found_verdict)

    rows = []
    stable = 0
    for case_id, verdicts in by_case.items():
        if len(set(verdicts)) == 1:
            stable += 1
        rows.append({"case_id": case_id, "verdicts": verdicts, "distinct": len(set(verdicts))})

    per_sample = [
        round(sum(1 for s in scores if s.verdict_correct) / float(len(scores)), 4)
        for scores in sample_scores
        if scores
    ]
    return {
        "system": system_name,
        "samples": len(sample_scores),
        "cases": len(by_case),
        "verdict_accuracy_by_sample": per_sample,
        "verdict_accuracy_mean": round(sum(per_sample) / float(len(per_sample)), 4) if per_sample else 0.0,
        "verdict_stability": round(stable / float(len(by_case) or 1), 4),
        "cases_that_moved": [r for r in rows if r["distinct"] > 1],
        "per_case": rows,
    }


def print_consistency(reports):
    print()
    print("CONSISTENCY, same plan reviewed several times")
    print("%-32s %-24s" % ("SYSTEM", "VERDICT ACCURACY (spread)"))
    print("-" * 62)
    for report in reports:
        values = report["verdict_accuracy_by_sample"]
        spread = "n/a" if not values else "%.0f%% (%.0f to %.0f)" % (
            report["verdict_accuracy_mean"] * 100,
            min(values) * 100,
            max(values) * 100,
        )
        print("%-32s %-24s  same verdict every run: %.0f%%"
              % (report["system"], spread, report["verdict_stability"] * 100))
    for report in reports:
        moved = report["cases_that_moved"]
        if moved:
            print("\n%s changed its mind between runs:" % report["system"])
            for row in moved:
                print("  %-30s %s" % (row["case_id"], " then ".join(row["verdicts"])))
        else:
            print("\n%s gave an identical verdict on every run." % report["system"])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the CloudFix evaluation")
    parser.add_argument(
        "--system",
        choices=tuple(LADDER) + ("both", "ladder"),
        default="both",
        help="both runs baseline, scanner and agent. ladder runs all five rungs.",
    )
    parser.add_argument("--mode", choices=("auto", "live", "replay"), default="auto",
                        help="replay uses only recorded responses and needs no credentials")
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", choices=("bedrock", "anthropic"), default=None)
    parser.add_argument("--region", default=None, help="AWS region, bedrock only")
    parser.add_argument("--cases", default="", help="comma separated case ids, default all")
    parser.add_argument(
        "--samples",
        type=int,
        default=1,
        help="review every case this many times, to measure consistency",
    )
    args = parser.parse_args(argv)

    cases = load_cases()
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
        cases = [c for c in cases if c.id in wanted]
        if not cases:
            parser.error("no cases matched %r" % args.cases)

    client = ModelClient(
        model=args.model, mode=args.mode, provider=args.provider, region=args.region
    )

    if args.system == "both":
        systems = ["baseline", "scanner", "agent"]
    elif args.system == "ladder":
        systems = list(LADDER)
    else:
        systems = [args.system]

    print("Cases: %d | model: %s | mode: %s" % (len(cases), client.model, args.mode))

    summaries = []
    reports = []
    for name in systems:
        print("\n%s" % name.upper())
        sample_scores = []
        samples = 1 if name == "scanner" else args.samples
        for sample in range(1, samples + 1):
            client.nonce = "" if sample == 1 else str(sample)
            if samples > 1:
                print("  sample %d of %d" % (sample, samples))
            try:
                records = run_system(name, cases, client)
            except ModelError as exc:
                print("\n\nStopped before spending anything else.\n")
                print(exc)
                return 2
            sample_scores.append([r["score"] for r in records])
            if sample == 1:
                summary, path = write_outputs(name, records, client.model)
                summaries.append(summary)
                print(
                    "  verdict accuracy: %.0f%%   written to %s"
                    % (summary["verdict_accuracy"] * 100, os.path.relpath(path, _PROJECT_ROOT))
                )
        if samples > 1:
            reports.append(consistency_report(name, sample_scores))

    if args.system == "ladder":
        print_ladder(summaries)
    else:
        print_comparison(summaries)

    if reports:
        print_consistency(reports)
        _ensure(RESULTS_DIR)
        out = os.path.join(RESULTS_DIR, "consistency.json")
        with open(out, "w", encoding="utf-8") as handle:
            json.dump({"samples": args.samples, "reports": reports}, handle, indent=2)
        print("\nWritten to %s" % os.path.relpath(out, _PROJECT_ROOT))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
