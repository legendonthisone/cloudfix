import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cloudfix import policy, scanner  # noqa: E402
from cloudfix.cases import load_cases  # noqa: E402
from cloudfix.decision import Decision, Reason, ReviewResult  # noqa: E402
from cloudfix.scoring import aggregate, score_review  # noqa: E402


def case(case_id):
    for entry in load_cases():
        if entry.id == case_id:
            return entry
    raise AssertionError(case_id)


class TheExistingWay(unittest.TestCase):
    def test_the_scanner_needs_no_model_and_no_credentials(self):
        result = scanner.review(case("c03_open_ssh_sg").load())
        self.assertEqual(result.model_calls, 0)
        self.assertEqual(result.input_tokens, 0)

    def test_it_blocks_on_a_critical_finding(self):
        self.assertEqual(scanner.review(case("c03_open_ssh_sg").load()).verdict, policy.BLOCK)

    def test_it_passes_a_plan_with_no_findings(self):
        self.assertEqual(scanner.review(case("c01_safe_tagging").load()).verdict, policy.SAFE)

    def test_it_reviews_the_same_plan_the_same_way_every_time(self):
        first = scanner.review(case("c05_public_database").load()).decision.to_dict()
        second = scanner.review(case("c05_public_database").load()).decision.to_dict()
        self.assertEqual(first, second)

    def test_it_sees_the_flag_on_the_database_replacement_and_still_gets_it_wrong(self):
        """The known blind spot, written down as a test rather than as a claim.

        An earlier draft of the README said a scanner comes back completely clean
        on c07. That was too strong: checkov ships RDSDeletionProtection.py, a
        configuration policy for exactly the flag this plan turns off. So the
        scanner rung was given the same check, and it now reports two medium
        findings on c07 and asks for a human.

        It is still wrong, and wrong in the dangerous direction, because the
        ground truth is DO NOT APPLY. Seeing that a checkbox is off is not the
        same as knowing the production data is about to stop existing.
        """
        entry = case("c07_prod_db_replace_clean")
        result = scanner.review(entry.load())
        found = sorted(f.check_id for f in result.findings)
        self.assertEqual(found, ["DELETION_PROTECTION_DISABLED", "FINAL_SNAPSHOT_SKIPPED"])
        self.assertTrue(all(f.severity == "medium" for f in result.findings))
        self.assertEqual(result.verdict, policy.REVIEW)
        self.assertEqual(entry.expected_verdict, policy.BLOCK)

    def test_the_cases_no_configuration_policy_can_reach_at_any_gate_setting(self):
        """The three plans where nothing is configured badly and the deploy still hurts.

        These are the cases that separate a configuration scanner from a
        deployment decision. No check fires on any of them, so no severity gate,
        however strict, can produce anything but SAFE. All three are wrong.
        """
        for case_id in (
            "c08_nat_gateway_replace",
            "c09_prod_ec2_replace",
            "c14_mixed_prod_change",
        ):
            entry = case(case_id)
            result = scanner.review(entry.load())
            self.assertEqual(result.findings, [], case_id)
            self.assertEqual(result.verdict, policy.SAFE, case_id)
            self.assertEqual(entry.expected_verdict, policy.REVIEW, case_id)

    def test_it_over_blocks_the_intentional_static_website(self):
        self.assertEqual(scanner.review(case("c12_dev_static_website").load()).verdict, policy.BLOCK)
        self.assertEqual(case("c12_dev_static_website").expected_verdict, policy.REVIEW)


class Scoring(unittest.TestCase):
    def build(self, verdict, reasons=None):
        return ReviewResult(decision=Decision(verdict=verdict, reasons=reasons or []))

    def test_an_exact_match_scores_correct(self):
        entry = case("c03_open_ssh_sg")
        score = score_review(entry, self.build(policy.BLOCK), entry.load())
        self.assertTrue(score.verdict_correct)
        self.assertEqual(score.direction, "exact")
        self.assertFalse(score.dangerous_miss)

    def test_calling_a_blocked_plan_safe_is_a_dangerous_miss(self):
        entry = case("c03_open_ssh_sg")
        score = score_review(entry, self.build(policy.SAFE), entry.load())
        self.assertTrue(score.dangerous_miss)
        self.assertEqual(score.direction, "under")

    def test_blocking_a_safe_plan_is_an_over_block_not_a_dangerous_miss(self):
        entry = case("c01_safe_tagging")
        score = score_review(entry, self.build(policy.BLOCK), entry.load())
        self.assertTrue(score.over_block)
        self.assertFalse(score.dangerous_miss)
        self.assertEqual(score.direction, "over")

    def test_a_review_verdict_on_a_block_case_is_still_a_dangerous_miss(self):
        entry = case("c03_open_ssh_sg")
        score = score_review(entry, self.build(policy.REVIEW), entry.load())
        self.assertTrue(score.dangerous_miss)

    def test_no_decision_at_all_counts_as_a_dangerous_miss(self):
        entry = case("c03_open_ssh_sg")
        score = score_review(entry, ReviewResult(decision=None, error="crashed"), entry.load())
        self.assertFalse(score.verdict_correct)
        self.assertTrue(score.dangerous_miss)
        self.assertEqual(score.error, "crashed")

    def test_an_invented_citation_is_counted_even_when_verification_never_ran(self):
        entry = case("c03_open_ssh_sg")
        result = self.build(
            policy.BLOCK,
            [
                Reason(claim="a", evidence_pointer="resource_changes[0].change.after.name",
                       expected_value="bastion-prod-sg"),
                Reason(claim="b", evidence_pointer="resource_changes[88].change.after.acl"),
                Reason(claim="c"),
            ],
        )
        score = score_review(entry, result, entry.load())
        self.assertEqual(score.reasons_total, 3)
        self.assertEqual(score.reasons_with_pointer, 2)
        self.assertEqual(score.reasons_unsupported, 2)

    def test_naming_the_critical_resource_is_detected(self):
        entry = case("c03_open_ssh_sg")
        result = self.build(
            policy.BLOCK,
            [Reason(claim="aws_security_group.bastion opens port 22 to the world")],
        )
        self.assertTrue(score_review(entry, result, entry.load()).caught_critical)

    def test_missing_the_critical_resource_is_detected(self):
        entry = case("c03_open_ssh_sg")
        result = self.build(policy.BLOCK, [Reason(claim="something is wrong somewhere")])
        self.assertFalse(score_review(entry, result, entry.load()).caught_critical)


class Aggregation(unittest.TestCase):
    def test_the_scanner_scored_over_the_whole_set_reports_its_real_profile(self):
        scores = []
        for entry in load_cases():
            plan = entry.load()
            scores.append(score_review(entry, scanner.review(plan), plan))
        summary = aggregate(scores)
        self.assertEqual(summary["cases"], len(scores))
        self.assertGreater(summary["verdict_accuracy"], 0.0)
        self.assertLess(summary["verdict_accuracy"], 1.0)
        self.assertIn("c07_prod_db_replace_clean", summary["dangerous_miss_cases"])
        self.assertIn("c12_dev_static_website", summary["over_block_cases"])
        self.assertIn("hard", summary["accuracy_by_difficulty"])


if __name__ == "__main__":
    unittest.main()
