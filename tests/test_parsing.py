import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cloudfix import policy  # noqa: E402
from cloudfix.parsing import ParseError, parse_decision, parse_json_object  # noqa: E402

GOOD = """{
  "verdict": "DO NOT APPLY",
  "summary": "the production database is replaced with no snapshot",
  "rules": ["D4"],
  "reasons": [
    {"claim": "orders-prod is replaced",
     "rule": "D4",
     "evidence_pointer": "resource_changes[0].change.actions",
     "expected_value": "[\\"delete\\", \\"create\\"]"}
  ],
  "dismissed": [
    {"check_id": "SG_ADMIN_PORT_OPEN", "resource_address": "aws_security_group.a",
     "why": "the rule is being removed"}
  ],
  "confirmations": ["a restore path exists"]
}"""


class Extraction(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_json_object('{"a": 1}'), {"a": 1})

    def test_json_inside_a_code_fence(self):
        self.assertEqual(parse_json_object('```json\n{"a": 1}\n```'), {"a": 1})

    def test_json_with_prose_around_it(self):
        self.assertEqual(
            parse_json_object('Sure, here is the decision:\n{"a": 1}\nHope that helps.'),
            {"a": 1},
        )

    def test_an_empty_reply_is_an_error_not_an_empty_decision(self):
        with self.assertRaises(ParseError):
            parse_json_object("   ")

    def test_prose_with_no_json_is_an_error(self):
        with self.assertRaises(ParseError):
            parse_json_object("I think this plan is fine.")


class DecisionShape(unittest.TestCase):
    def test_a_full_reply_reads_correctly(self):
        decision = parse_decision(GOOD)
        self.assertEqual(decision.verdict, policy.BLOCK)
        self.assertEqual(decision.rules, ["D4"])
        self.assertEqual(len(decision.reasons), 1)
        self.assertEqual(
            decision.reasons[0].evidence_pointer, "resource_changes[0].change.actions"
        )
        self.assertEqual(decision.dismissed[0].check_id, "SG_ADMIN_PORT_OPEN")
        self.assertEqual(decision.confirmations, ["a restore path exists"])

    def test_verdict_wording_is_normalised(self):
        for wording in ("do not apply", "DO_NOT_APPLY", "Do Not Apply", "BLOCK"):
            self.assertEqual(parse_decision('{"verdict": "%s"}' % wording).verdict, policy.BLOCK)
        for wording in ("requires human review", "needs human review", "REVIEW"):
            self.assertEqual(parse_decision('{"verdict": "%s"}' % wording).verdict, policy.REVIEW)
        self.assertEqual(parse_decision('{"verdict": "safe"}').verdict, policy.SAFE)

    def test_an_unknown_verdict_is_rejected_rather_than_guessed(self):
        with self.assertRaises(ParseError):
            parse_decision('{"verdict": "probably fine"}')

    def test_a_missing_verdict_is_rejected(self):
        with self.assertRaises(ParseError):
            parse_decision('{"summary": "no verdict here"}')

    def test_reasons_given_as_plain_strings_still_load(self):
        decision = parse_decision('{"verdict": "SAFE", "reasons": ["nothing changes"]}')
        self.assertEqual(decision.reasons[0].claim, "nothing changes")
        self.assertEqual(decision.reasons[0].evidence_pointer, "")

    def test_alternative_field_names_are_accepted(self):
        decision = parse_decision(
            '{"decision": "SAFE", "reasons": [{"reason": "fine", "pointer": "resource_changes[0]"}]}'
        )
        self.assertEqual(decision.verdict, policy.SAFE)
        self.assertEqual(decision.reasons[0].evidence_pointer, "resource_changes[0]")

    def test_a_dismissal_with_no_check_id_is_dropped_rather_than_half_stored(self):
        decision = parse_decision('{"verdict": "SAFE", "dismissed": [{"why": "no id"}]}')
        self.assertEqual(decision.dismissed, [])


class SeverityOrdering(unittest.TestCase):
    def test_block_is_the_most_severe(self):
        self.assertTrue(policy.at_least_as_severe(policy.BLOCK, policy.REVIEW))
        self.assertTrue(policy.at_least_as_severe(policy.REVIEW, policy.SAFE))
        self.assertFalse(policy.at_least_as_severe(policy.SAFE, policy.REVIEW))


if __name__ == "__main__":
    unittest.main()
