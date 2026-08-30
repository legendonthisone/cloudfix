#!/usr/bin/env python3
"""
One entry point, so nobody has to think about PYTHONPATH.

  python run.py test                        run the unit tests, no credentials needed
  python run.py check                       one tiny call, proves the model backend works
  python run.py scan --plan <file>          deterministic checks only, no model, free
  python run.py review --plan <file>        the full CloudFix review of one plan
  python run.py eval --system both --mode replay
  python run.py eval --system ladder --mode replay
  python run.py cases                       list the evaluation cases and their ground truth
  python run.py sensitivity                 what the result becomes if you reject my two most arguable labels
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command, rest = sys.argv[1], sys.argv[2:]

    if command in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    if command == "test":
        import unittest

        loader = unittest.TestLoader()
        suite = loader.discover(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests")
        )
        runner = unittest.TextTestRunner(verbosity=2 if "-v" in rest else 1)
        return 0 if runner.run(suite).wasSuccessful() else 1

    if command == "check":
        from cloudfix.check import main as check_main

        return check_main(rest)

    if command == "review":
        from cloudfix.review_cli import main as review_main

        return review_main(rest)

    if command == "scan":
        from cloudfix.review_cli import main as review_main

        return review_main(rest + ["--system", "scanner"])

    if command == "eval":
        from cloudfix.run_eval import main as eval_main

        return eval_main(rest)

    if command == "sensitivity":
        from cloudfix.sensitivity import main as sensitivity_main

        return sensitivity_main(rest)

    if command == "cases":
        from cloudfix.cases import load_cases

        cases = load_cases()
        print("%-32s %-22s %-8s %s" % ("CASE", "EXPECTED", "RULES", "TITLE"))
        print("-" * 110)
        for case in cases:
            print(
                "%-32s %-22s %-8s %s"
                % (case.id, case.expected_verdict, ",".join(case.rules) or "-", case.title)
            )
        print("\n%d cases. The reasoning behind every label is in data/cases.json." % len(cases))
        return 0

    print("Unknown command %r" % command)
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
