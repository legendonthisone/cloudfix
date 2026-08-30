"""
Reviewing one plan, which is what the tool is actually for.

  python run.py review --plan data/plans/c07_prod_db_replace_clean.json
  python run.py review --plan my-plan.json --out review.md
  python run.py review --plan my-plan.json --system scanner

Produce the input from a real repository with:

  terraform plan -out=tfplan
  terraform show -json tfplan > plan.json

Nothing is ever applied. The output is a recommendation and a checklist for the
person who holds the deploy.
"""

import argparse
import json
import os
import sys

from . import agent as agent_system
from . import scanner as scanner_system
from .decision import render_markdown
from .model import ModelClient, ModelError
from .plan import PlanError, load_plan
from .trajectory import write_trajectory

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EXIT_CODES = {"SAFE": 0, "REQUIRES HUMAN REVIEW": 1, "DO NOT APPLY": 2}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review one Terraform plan")
    parser.add_argument("--plan", required=True, help="path to terraform show -json output")
    parser.add_argument("--system", choices=("agent", "scanner"), default="agent")
    parser.add_argument("--mode", choices=("auto", "live", "replay"), default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", choices=("bedrock", "anthropic"), default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--out", default=None, help="write the review to this file as markdown")
    parser.add_argument("--json", action="store_true", help="print the decision as JSON instead")
    parser.add_argument(
        "--trajectory", default=None, help="write the full step by step record to this file"
    )
    args = parser.parse_args(argv)

    try:
        plan = load_plan(args.plan)
    except PlanError as exc:
        print("Could not read that plan.\n%s" % exc)
        return 3

    if args.system == "scanner":
        result = scanner_system.review(plan)
        model_name = "none, this rung uses no model"
    else:
        client = ModelClient(
            model=args.model, mode=args.mode, provider=args.provider, region=args.region
        )
        try:
            result = agent_system.review(plan, client)
        except ModelError as exc:
            print("\n%s" % exc)
            return 4
        model_name = client.model

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        report = render_markdown(
            result, plan_path=args.plan, model_name=model_name, system=args.system, plan=plan
        )
        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(report)
            print("Review written to %s" % args.out)
        else:
            sys.stdout.write(report)

    if args.trajectory:
        write_trajectory(args.trajectory, result, plan_path=args.plan, model=model_name,
                         system=args.system)
        print("Trajectory written to %s" % args.trajectory)

    return EXIT_CODES.get(result.verdict, 5)


if __name__ == "__main__":
    raise SystemExit(main())
