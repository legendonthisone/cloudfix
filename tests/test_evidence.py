import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cloudfix import checks  # noqa: E402
from cloudfix.cases import load_cases  # noqa: E402
from cloudfix.evidence import PointerError, check_citation, parse_pointer, resolve  # noqa: E402

DOCUMENT = {
    "resource_changes": [
        {
            "address": "aws_db_instance.orders",
            "change": {"actions": ["delete", "create"], "after": {"publicly_accessible": True}},
        }
    ]
}


class Pointers(unittest.TestCase):
    def test_a_mixed_pointer_parses_into_keys_and_indexes(self):
        self.assertEqual(
            parse_pointer("resource_changes[0].change.after.publicly_accessible"),
            ["resource_changes", 0, "change", "after", "publicly_accessible"],
        )

    def test_resolving_returns_the_value(self):
        self.assertIs(
            resolve(DOCUMENT, "resource_changes[0].change.after.publicly_accessible"), True
        )

    def test_a_missing_key_raises_unless_a_default_is_given(self):
        with self.assertRaises(PointerError):
            resolve(DOCUMENT, "resource_changes[0].change.after.nonsense")
        self.assertIsNone(resolve(DOCUMENT, "resource_changes[0].change.after.nonsense", None))

    def test_an_index_past_the_end_does_not_crash(self):
        self.assertIsNone(resolve(DOCUMENT, "resource_changes[7].change", None))

    def test_an_empty_pointer_is_rejected(self):
        with self.assertRaises(PointerError):
            parse_pointer("   ")


class Citations(unittest.TestCase):
    def test_a_pointer_that_resolves_is_supported(self):
        ok, note = check_citation(DOCUMENT, "resource_changes[0].change.after.publicly_accessible")
        self.assertTrue(ok)
        self.assertIn("true", note.lower())

    def test_a_pointer_that_does_not_exist_is_not_supported(self):
        ok, note = check_citation(DOCUMENT, "resource_changes[3].change.after.acl")
        self.assertFalse(ok)
        self.assertIn("does not exist", note)

    def test_a_claimed_value_that_disagrees_is_not_supported(self):
        ok, note = check_citation(
            DOCUMENT, "resource_changes[0].change.after.publicly_accessible", "false"
        )
        self.assertFalse(ok)
        self.assertIn("not false", note)

    def test_a_claimed_value_that_agrees_is_supported(self):
        ok, _ = check_citation(
            DOCUMENT, "resource_changes[0].change.after.publicly_accessible", "true"
        )
        self.assertTrue(ok)

    def test_gibberish_is_handled_as_unsupported_not_as_a_crash(self):
        ok, _ = check_citation(DOCUMENT, "]][[..", "x")
        self.assertFalse(ok)


class EveryFindingCanProveItself(unittest.TestCase):
    """If a check cites a pointer that does not resolve, the check is lying."""

    def test_all_evidence_on_all_cases_resolves(self):
        for case in load_cases():
            plan = case.load()
            for finding in checks.run_all(plan):
                for item in finding.evidence:
                    ok, note = check_citation(plan.raw, item.pointer)
                    self.assertTrue(
                        ok, "%s: %s %s (%s)" % (case.id, finding.check_id, item.pointer, note)
                    )


if __name__ == "__main__":
    unittest.main()
