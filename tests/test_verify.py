import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cloudfix import blast, checks, policy  # noqa: E402
from cloudfix.cases import load_cases  # noqa: E402
from cloudfix.decision import Decision, Dismissal, Reason  # noqa: E402
from cloudfix.verify import verify  # noqa: E402


def case(case_id):
    for entry in load_cases():
        if entry.id == case_id:
            return entry
    raise AssertionError("no such case %s" % case_id)


class EvidenceRule(unittest.TestCase):
    """V1: a reason must point at something the plan actually says."""

    def setUp(self):
        self.plan = case("c05_public_database").load()
        self.findings = checks.run_all(self.plan)
        self.blast = blast.analyse(self.plan)

    def test_a_real_pointer_passes(self):
        decision = Decision(
            verdict=policy.BLOCK,
            reasons=[
                Reason(
                    claim="the database becomes public",
                    evidence_pointer="resource_changes[0].change.after.publicly_accessible",
                    expected_value="true",
                    rule="D1",
                )
            ],
        )
        verdict = verify(decision, self.plan.raw, self.findings, self.blast)
        self.assertTrue(verdict.passed, verdict.defects)
        self.assertEqual(verdict.unsupported_reasons, 0)

    def test_an_invented_pointer_fails(self):
        decision = Decision(
            verdict=policy.BLOCK,
            reasons=[
                Reason(
                    claim="the bucket is public",
                    evidence_pointer="resource_changes[9].change.after.acl",
                    expected_value="public-read",
                )
            ],
        )
        verdict = verify(decision, self.plan.raw, self.findings, self.blast)
        self.assertFalse(verdict.passed)
        self.assertEqual(verdict.unsupported_reasons, 1)
        self.assertIn("does not exist", verdict.defects[0])

    def test_a_pointer_that_resolves_to_something_else_fails(self):
        decision = Decision(
            verdict=policy.BLOCK,
            reasons=[
                Reason(
                    claim="encryption is off",
                    evidence_pointer="resource_changes[0].change.after.storage_encrypted",
                    expected_value="false",
                )
            ],
        )
        verdict = verify(decision, self.plan.raw, self.findings, self.blast)
        self.assertFalse(verdict.passed)

    def test_a_reason_with_no_pointer_at_all_fails(self):
        decision = Decision(verdict=policy.BLOCK, reasons=[Reason(claim="it feels wrong")])
        verdict = verify(decision, self.plan.raw, self.findings, self.blast)
        self.assertFalse(verdict.passed)
        self.assertIn("cites no evidence", verdict.defects[0])

    def test_the_repair_instruction_numbers_every_defect(self):
        decision = Decision(
            verdict=policy.BLOCK,
            reasons=[Reason(claim="a"), Reason(claim="b")],
        )
        verdict = verify(decision, self.plan.raw, self.findings, self.blast)
        text = verdict.repair_instruction()
        self.assertIn("1.", text)
        self.assertIn("2.", text)


class SafeVerdictRule(unittest.TestCase):
    """V2: SAFE may not walk past a critical finding or a severe blast radius."""

    def test_safe_with_a_critical_finding_is_challenged(self):
        plan = case("c03_open_ssh_sg").load()
        findings = checks.run_all(plan)
        decision = Decision(verdict=policy.SAFE, summary="looks fine")
        verdict = verify(decision, plan.raw, findings, blast.analyse(plan))
        self.assertFalse(verdict.passed)
        self.assertIn("SG_ADMIN_PORT_OPEN", " ".join(verdict.defects))

    def test_safe_is_allowed_once_the_finding_is_dismissed_in_writing(self):
        plan = case("c03_open_ssh_sg").load()
        findings = checks.run_all(plan)
        decision = Decision(
            verdict=policy.SAFE,
            dismissed=[
                Dismissal(
                    check_id="SG_ADMIN_PORT_OPEN",
                    resource_address="aws_security_group.bastion",
                    why="a worked example, not a real deployment",
                )
            ],
        )
        verdict = verify(decision, plan.raw, findings, blast.analyse(plan))
        self.assertTrue(verdict.passed, verdict.defects)

    def test_safe_with_a_severe_blast_radius_is_challenged(self):
        plan = case("c07_prod_db_replace_clean").load()
        findings = checks.run_all(plan)
        # Only medium findings here, so V2's finding branch stays quiet and the
        # blast radius branch is the one under test. That is the point of the
        # case: nothing is configured badly enough to block, and the data still
        # stops existing.
        self.assertTrue(all(f.severity == "medium" for f in findings), findings)
        decision = Decision(verdict=policy.SAFE, summary="no serious findings")
        verdict = verify(decision, plan.raw, findings, blast.analyse(plan))
        self.assertFalse(verdict.passed)
        self.assertIn("aws_db_instance.orders", " ".join(verdict.defects))

    def test_the_same_case_passes_verification_when_blocked_with_evidence(self):
        plan = case("c07_prod_db_replace_clean").load()
        decision = Decision(
            verdict=policy.BLOCK,
            rules=["D4"],
            reasons=[
                Reason(
                    claim="orders-prod is replaced with no final snapshot",
                    evidence_pointer="resource_changes[0].change.after.skip_final_snapshot",
                    expected_value="true",
                    rule="D4",
                )
            ],
        )
        verdict = verify(decision, plan.raw, checks.run_all(plan), blast.analyse(plan))
        self.assertTrue(verdict.passed, verdict.defects)

    def test_a_safe_verdict_on_a_genuinely_safe_plan_passes(self):
        plan = case("c11_closing_ssh_rule").load()
        decision = Decision(verdict=policy.SAFE, summary="the open rule is being removed")
        verdict = verify(decision, plan.raw, checks.run_all(plan), blast.analyse(plan))
        self.assertTrue(verdict.passed, verdict.defects)


class OtherRules(unittest.TestCase):
    def test_blocking_with_no_reason_is_challenged(self):
        plan = case("c01_safe_tagging").load()
        decision = Decision(verdict=policy.BLOCK)
        verdict = verify(decision, plan.raw, checks.run_all(plan), blast.analyse(plan))
        self.assertFalse(verdict.passed)
        self.assertIn("no reason was given", " ".join(verdict.defects))

    def test_dismissing_a_check_that_never_fired_is_challenged(self):
        plan = case("c01_safe_tagging").load()
        decision = Decision(
            verdict=policy.SAFE,
            dismissed=[Dismissal(check_id="MADE_UP_CHECK", resource_address="x", why="because")],
        )
        verdict = verify(decision, plan.raw, checks.run_all(plan), blast.analyse(plan))
        self.assertFalse(verdict.passed)
        self.assertIn("no check with that id fired", " ".join(verdict.defects))




class PreexistingRiskRule(unittest.TestCase):
    """V5, added after watching the loop let a real failure through.

    On c15 the agent dismissed a standing SSH exposure in writing, correctly
    observing that this change did not cause it, and returned SAFE. V2 accepted
    the dismissal because a dismissal existed. Policy rule R5, written before any
    of this ran, says that outcome is REQUIRES HUMAN REVIEW.
    """

    def setUp(self):
        self.plan = case("c15_preexisting_open_port").load()
        self.findings = checks.run_all(self.plan)
        self.blast = blast.analyse(self.plan)

    def test_the_check_marks_the_finding_as_not_introduced_by_this_change(self):
        self.assertEqual(len(self.findings), 1)
        self.assertFalse(self.findings[0].introduced_by_change)

    def test_dismissing_it_into_safe_is_challenged(self):
        decision = Decision(
            verdict=policy.SAFE,
            summary="only tags change",
            dismissed=[
                Dismissal(
                    check_id="SG_ADMIN_PORT_OPEN",
                    resource_address="aws_security_group.legacy_ftp",
                    why="the rule existed before this change and is unchanged",
                )
            ],
        )
        verdict = verify(decision, self.plan.raw, self.findings, self.blast)
        self.assertFalse(verdict.passed)
        self.assertIn("rule R5", " ".join(verdict.defects))
        self.assertIn("REQUIRES HUMAN REVIEW", " ".join(verdict.defects))

    def test_review_is_accepted(self):
        decision = Decision(
            verdict=policy.REVIEW,
            rules=["R5"],
            reasons=[
                Reason(
                    claim="SSH is open to the world and was already open before this change",
                    evidence_pointer="resource_changes[0].change.before.ingress[0].cidr_blocks",
                    rule="R5",
                )
            ],
        )
        verdict = verify(decision, self.plan.raw, self.findings, self.blast)
        self.assertTrue(verdict.passed, verdict.defects)

    def test_a_finding_this_change_did_introduce_is_not_caught_by_v5(self):
        """V5 must not fire on ordinary findings, or it becomes a blanket rule."""
        plan = case("c03_open_ssh_sg").load()
        findings = checks.run_all(plan)
        self.assertTrue(findings[0].introduced_by_change)
        decision = Decision(
            verdict=policy.SAFE,
            dismissed=[
                Dismissal(check_id="SG_ADMIN_PORT_OPEN",
                          resource_address="aws_security_group.bastion",
                          why="a worked example")
            ],
        )
        verdict = verify(decision, plan.raw, findings, blast.analyse(plan))
        self.assertTrue(verdict.passed, verdict.defects)


if __name__ == "__main__":
    unittest.main()
