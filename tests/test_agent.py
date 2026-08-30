"""
The agent loop, driven by a scripted stand in for the model.

No credentials, no network, no cost. The point is to prove the machinery around
the model behaves: that verification challenges a bad decision, that the repair
step is given the defects, that the ablation flags really do remove what they say
they remove, and that every token is counted.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cloudfix import agent, policy  # noqa: E402
from cloudfix.cases import load_cases  # noqa: E402
from cloudfix.model import ModelResponse  # noqa: E402


def case(case_id):
    for entry in load_cases():
        if entry.id == case_id:
            return entry
    raise AssertionError(case_id)


class ScriptedClient:
    """Stands in for ModelClient. Returns prepared replies and records the prompts."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.model = "scripted-test-double"

    def complete(self, system, user, max_tokens=2000, temperature=0.0):
        self.prompts.append({"system": system, "user": user})
        text = self.replies.pop(0) if self.replies else '{"verdict": "SAFE"}'
        return ModelResponse(
            text=text,
            model=self.model,
            input_tokens=100,
            output_tokens=50,
            latency_seconds=0.5,
            from_cache=False,
        )


SAFE_WITH_A_MADE_UP_POINTER = json.dumps(
    {
        "verdict": "SAFE",
        "summary": "no security findings, so this is fine",
        "reasons": [
            {
                "claim": "everything is encrypted",
                "evidence_pointer": "resource_changes[41].change.after.storage_encrypted",
                "expected_value": "true",
            }
        ],
    }
)

BLOCK_WITH_A_REAL_POINTER = json.dumps(
    {
        "verdict": "DO NOT APPLY",
        "summary": "orders-prod is replaced with no final snapshot",
        "rules": ["D4"],
        "reasons": [
            {
                "claim": "the production database is replaced and the final snapshot is skipped",
                "rule": "D4",
                "evidence_pointer": "resource_changes[0].change.after.skip_final_snapshot",
                "expected_value": "true",
            }
        ],
        "confirmations": ["a restore path exists for orders-prod"],
    }
)


class VerificationLoop(unittest.TestCase):
    def setUp(self):
        self.plan = case("c07_prod_db_replace_clean").load()

    def test_a_wrong_answer_is_challenged_and_repaired(self):
        client = ScriptedClient([SAFE_WITH_A_MADE_UP_POINTER, BLOCK_WITH_A_REAL_POINTER])
        result = agent.review(self.plan, client)
        self.assertEqual(result.verdict, policy.BLOCK)
        self.assertEqual(result.repairs, 1)
        self.assertIsNone(result.error)

    def test_the_repair_prompt_contains_the_numbered_defects(self):
        client = ScriptedClient([SAFE_WITH_A_MADE_UP_POINTER, BLOCK_WITH_A_REAL_POINTER])
        agent.review(self.plan, client)
        repair_prompt = client.prompts[1]["user"]
        self.assertIn("did not pass verification", repair_prompt)
        self.assertIn("resource_changes[41]", repair_prompt)
        self.assertIn("aws_db_instance.orders", repair_prompt)

    def test_without_verification_the_wrong_answer_survives(self):
        client = ScriptedClient([SAFE_WITH_A_MADE_UP_POINTER])
        result = agent.review(self.plan, client, verify_enabled=False)
        self.assertEqual(result.verdict, policy.SAFE)
        self.assertEqual(result.repairs, 0)

    def test_a_decision_that_holds_up_is_left_alone(self):
        client = ScriptedClient([BLOCK_WITH_A_REAL_POINTER])
        result = agent.review(self.plan, client)
        self.assertEqual(result.repairs, 0)
        self.assertEqual(len(client.prompts), 1)

    def test_the_loop_gives_up_after_the_repair_limit_and_says_so(self):
        client = ScriptedClient([SAFE_WITH_A_MADE_UP_POINTER] * 4)
        result = agent.review(self.plan, client)
        self.assertEqual(result.repairs, 2)
        self.assertIn("verification still failing", result.error)


class AblationFlags(unittest.TestCase):
    def setUp(self):
        self.plan = case("c07_prod_db_replace_clean").load()

    def test_blast_radius_reaches_the_prompt_when_it_is_on(self):
        client = ScriptedClient([BLOCK_WITH_A_REAL_POINTER])
        agent.review(self.plan, client, use_blast=True)
        self.assertIn("BLAST RADIUS ANALYSIS", client.prompts[0]["user"])

    def test_blast_radius_is_absent_from_the_prompt_when_it_is_off(self):
        client = ScriptedClient([BLOCK_WITH_A_REAL_POINTER])
        agent.review(self.plan, client, use_blast=False, verify_enabled=False)
        self.assertNotIn("BLAST RADIUS ANALYSIS", client.prompts[0]["user"])

    def test_the_deterministic_findings_always_reach_the_prompt(self):
        plan = case("c03_open_ssh_sg").load()
        client = ScriptedClient([BLOCK_WITH_A_REAL_POINTER])
        agent.review(plan, client, verify_enabled=False)
        self.assertIn("SG_ADMIN_PORT_OPEN", client.prompts[0]["user"])

    def test_a_plan_with_no_findings_says_so_and_warns_against_reading_it_as_safe(self):
        """c09 replaces a production server and no check fires on it at all.

        Not c07: since the data guard checks were added, c07 produces two medium
        findings, which is the point of those checks existing.
        """
        plan = case("c09_prod_ec2_replace").load()
        client = ScriptedClient([BLOCK_WITH_A_REAL_POINTER])
        agent.review(plan, client, verify_enabled=False)
        self.assertIn("No security check fired", client.prompts[0]["user"])


class Accounting(unittest.TestCase):
    def test_every_call_including_repairs_is_counted(self):
        client = ScriptedClient([SAFE_WITH_A_MADE_UP_POINTER, BLOCK_WITH_A_REAL_POINTER])
        result = agent.review(case("c07_prod_db_replace_clean").load(), client)
        self.assertEqual(result.model_calls, 2)
        self.assertEqual(result.input_tokens, 200)
        self.assertEqual(result.output_tokens, 100)

    def test_a_reply_that_cannot_be_parsed_gets_one_retry_then_reports_the_failure(self):
        client = ScriptedClient(["not json at all", "still not json"])
        result = agent.review(case("c01_safe_tagging").load(), client)
        self.assertIsNone(result.decision)
        self.assertIn("could not read a decision", result.error)
        self.assertEqual(result.model_calls, 2)

    def test_a_bad_first_reply_followed_by_a_good_one_recovers(self):
        client = ScriptedClient(["oops", BLOCK_WITH_A_REAL_POINTER])
        result = agent.review(case("c07_prod_db_replace_clean").load(), client)
        self.assertEqual(result.verdict, policy.BLOCK)


class Trajectories(unittest.TestCase):
    def test_the_trajectory_records_every_tool_and_model_step(self):
        client = ScriptedClient([SAFE_WITH_A_MADE_UP_POINTER, BLOCK_WITH_A_REAL_POINTER])
        result = agent.review(case("c07_prod_db_replace_clean").load(), client)
        names = [step["name"] for step in result.steps]
        for expected in ("parse", "security_checks", "blast_radius", "assess", "verify", "repair"):
            self.assertIn(expected, names)
        kinds = {step["name"]: step["kind"] for step in result.steps}
        self.assertEqual(kinds["security_checks"], "tool")
        self.assertEqual(kinds["blast_radius"], "tool")
        self.assertEqual(kinds["assess"], "model")

    def test_the_trajectory_serialises_to_json(self):
        client = ScriptedClient([BLOCK_WITH_A_REAL_POINTER])
        result = agent.review(case("c07_prod_db_replace_clean").load(), client)
        json.dumps(result.steps)  # must not raise


if __name__ == "__main__":
    unittest.main()


class ShippedConfiguration(unittest.TestCase):
    """What the defaults actually are, held in place by a test.

    The blast radius analysis is computed on every run because the human report
    needs it, and it is deliberately kept out of the model's prompt because the
    evaluation showed it made the model worse. Both halves of that sentence are
    easy to break by accident, so both are tested.
    """

    def test_the_default_keeps_blast_radius_out_of_the_prompt(self):
        client = ScriptedClient([BLOCK_WITH_A_REAL_POINTER])
        agent.review(case("c07_prod_db_replace_clean").load(), client)
        self.assertNotIn("BLAST RADIUS ANALYSIS", client.prompts[0]["user"])

    def test_blast_radius_is_still_computed_for_the_report(self):
        client = ScriptedClient([BLOCK_WITH_A_REAL_POINTER])
        result = agent.review(case("c07_prod_db_replace_clean").load(), client)
        self.assertIsNotNone(result.blast)
        self.assertEqual(result.blast.worst_tier, "severe")
        step = [s for s in result.steps if s["name"] == "blast_radius"][0]
        self.assertEqual(step["kind"], "tool")
        self.assertFalse(step["given_to_model"])

    def test_verification_is_on_by_default(self):
        client = ScriptedClient([SAFE_WITH_A_MADE_UP_POINTER, BLOCK_WITH_A_REAL_POINTER])
        result = agent.review(case("c07_prod_db_replace_clean").load(), client)
        self.assertEqual(result.repairs, 1)
