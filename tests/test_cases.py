"""
Ground truth integrity.

The evaluation is only worth as much as its labels, so the labels get tested like
code. Every case must load, name a real rule, and point at a resource that
actually exists in its plan.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cloudfix import policy  # noqa: E402
from cloudfix.cases import load_cases  # noqa: E402

RULE_IDS = {"D1", "D2", "D3", "D4", "D5", "R1", "R2", "R3", "R4", "R5", "R6"}


class GroundTruth(unittest.TestCase):
    def setUp(self):
        self.cases = load_cases()

    def test_there_are_at_least_ten_cases(self):
        self.assertGreaterEqual(len(self.cases), 10)

    def test_case_ids_are_unique(self):
        ids = [c.id for c in self.cases]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_plan_file_loads(self):
        for case in self.cases:
            plan = case.load()
            self.assertTrue(plan.changes, case.id)

    def test_every_verdict_is_one_of_the_three(self):
        for case in self.cases:
            self.assertIn(case.expected_verdict, policy.VERDICTS, case.id)

    def test_every_named_rule_exists_in_the_policy(self):
        for case in self.cases:
            for rule in case.rules:
                self.assertIn(rule, RULE_IDS, case.id)
                self.assertIn("  %s " % rule, policy.POLICY_TEXT, rule)

    def test_a_safe_case_names_no_rule_and_others_do(self):
        for case in self.cases:
            if case.expected_verdict == policy.SAFE:
                self.assertEqual(case.rules, [], case.id)
            else:
                self.assertTrue(case.rules, case.id)

    def test_block_verdicts_only_cite_d_rules_and_review_only_r_rules(self):
        for case in self.cases:
            if case.expected_verdict == policy.BLOCK:
                self.assertTrue(all(r.startswith("D") for r in case.rules), case.id)
            if case.expected_verdict == policy.REVIEW:
                self.assertTrue(all(r.startswith("R") for r in case.rules), case.id)

    def test_every_critical_resource_exists_in_its_plan(self):
        for case in self.cases:
            if not case.critical_resource:
                continue
            addresses = {c.address for c in case.load().changes}
            self.assertIn(case.critical_resource, addresses, case.id)

    def test_every_case_explains_its_label(self):
        for case in self.cases:
            self.assertGreater(len(case.why), 60, case.id)

    def test_all_three_verdicts_are_represented(self):
        found = {c.expected_verdict for c in self.cases}
        self.assertEqual(found, set(policy.VERDICTS))

    def test_at_least_one_hard_case(self):
        self.assertTrue([c for c in self.cases if c.difficulty == "hard"])

    def test_the_plans_contain_no_real_account_identifiers(self):
        """Synthetic data only. 111122223333 is the AWS documentation account."""
        for case in self.cases:
            with open(case.plan_path, "r", encoding="utf-8") as handle:
                text = handle.read()
            for match in ("arn:aws:iam::", "arn:aws:kms:"):
                for piece in text.split(match)[1:]:
                    account = piece.split(":")[0]
                    if account.isdigit():
                        self.assertEqual(account, "111122223333", case.id)

    def test_no_plan_file_is_unused(self):
        used = {c.plan_file for c in self.cases}
        directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "plans"
        )
        on_disk = {name for name in os.listdir(directory) if name.endswith(".json")}
        self.assertEqual(used, on_disk)

    def test_every_plan_is_valid_json_with_resource_changes(self):
        for case in self.cases:
            with open(case.plan_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self.assertIn("resource_changes", raw, case.id)
            self.assertIn("terraform_version", raw, case.id)


if __name__ == "__main__":
    unittest.main()
