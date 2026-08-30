import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cloudfix import blast  # noqa: E402
from cloudfix.cases import load_cases  # noqa: E402
from cloudfix.plan import parse_plan  # noqa: E402


def plan_with(resource_type, actions, before=None, after=None, name="thing", configuration=None):
    raw = {
        "resource_changes": [
            {
                "address": "%s.%s" % (resource_type, name),
                "type": resource_type,
                "name": name,
                "change": {"actions": actions, "before": before, "after": after},
            }
        ]
    }
    if configuration:
        raw["configuration"] = configuration
    return parse_plan(raw)


def case(case_id):
    for entry in load_cases():
        if entry.id == case_id:
            return entry
    raise AssertionError(case_id)


class Tiers(unittest.TestCase):
    def test_destroying_a_database_is_severe_and_loses_data(self):
        report = blast.analyse(
            plan_with("aws_db_instance", ["delete"], before={"identifier": "orders-prod"})
        )
        self.assertEqual(report.worst_tier, "severe")
        self.assertTrue(report.any_data_loss)

    def test_replacing_a_production_load_balancer_is_elevated_not_severe(self):
        report = blast.analyse(
            plan_with(
                "aws_lb", ["delete", "create"],
                before={"tags": {"Environment": "production"}},
                after={"tags": {"Environment": "production"}},
            )
        )
        self.assertEqual(report.worst_tier, "elevated")
        self.assertFalse(report.any_data_loss)

    def test_replacing_a_development_instance_is_routine(self):
        report = blast.analyse(
            plan_with(
                "aws_instance", ["delete", "create"],
                before={"tags": {"Environment": "development"}},
                after={"tags": {"Environment": "development"}},
            )
        )
        self.assertEqual(report.worst_tier, "routine")

    def test_an_in_place_update_is_routine(self):
        report = blast.analyse(
            plan_with("aws_db_instance", ["update"], before={"a": 1}, after={"a": 2})
        )
        self.assertEqual(report.worst_tier, "routine")

    def test_creating_something_new_destroys_nothing(self):
        report = blast.analyse(plan_with("aws_db_instance", ["create"], after={"a": 1}))
        self.assertEqual(report.worst_tier, "routine")
        self.assertEqual(report.notable(), [])

    def test_a_plan_of_no_ops_has_no_blast_radius(self):
        report = blast.analyse(plan_with("aws_s3_bucket", ["no-op"], before={}, after={}))
        self.assertEqual(report.worst_tier, "none")


class Guards(unittest.TestCase):
    def test_skipping_the_final_snapshot_marks_the_change_unrecoverable(self):
        report = blast.analyse(
            plan_with(
                "aws_db_instance", ["delete", "create"],
                before={"skip_final_snapshot": False, "tags": {"Environment": "production"}},
                after={"skip_final_snapshot": True, "tags": {"Environment": "production"}},
            )
        )
        impact = report.impacts[0]
        self.assertEqual(impact.tier, "severe")
        self.assertFalse(impact.recoverable)
        self.assertIn("not take a last backup", " ".join(impact.reasons))

    def test_a_final_snapshot_keeps_a_restore_path(self):
        report = blast.analyse(
            plan_with(
                "aws_db_instance", ["delete", "create"],
                before={"skip_final_snapshot": False},
                after={"skip_final_snapshot": False},
            )
        )
        self.assertIn("a restore is possible", " ".join(report.impacts[0].reasons))

    def test_turning_deletion_protection_off_raises_the_tier(self):
        report = blast.analyse(
            plan_with(
                "aws_lb", ["update"],
                before={"enable_deletion_protection": True, "tags": {"Environment": "production"}},
                after={"enable_deletion_protection": False, "tags": {"Environment": "production"}},
            )
        )
        self.assertEqual(report.worst_tier, "elevated")
        self.assertIn("deletion_protection", " ".join(report.impacts[0].reasons))


class Dependents(unittest.TestCase):
    def test_two_dependents_lift_a_routine_change_to_elevated(self):
        configuration = {
            "root_module": {
                "resources": [
                    {"address": "aws_route.a",
                     "expressions": {"x": {"references": ["aws_nat_gateway.thing"]}}},
                    {"address": "aws_route.b",
                     "expressions": {"x": {"references": ["aws_nat_gateway.thing"]}}},
                ]
            }
        }
        report = blast.analyse(
            plan_with("aws_nat_gateway", ["delete", "create"], before={}, after={},
                      configuration=configuration)
        )
        self.assertEqual(report.worst_tier, "elevated")
        self.assertEqual(report.impacts[0].dependents, ["aws_route.a", "aws_route.b"])

    def test_dependents_never_push_a_change_all_the_way_to_severe(self):
        configuration = {
            "root_module": {
                "resources": [
                    {"address": "aws_route.%d" % i,
                     "expressions": {"x": {"references": ["aws_nat_gateway.thing"]}}}
                    for i in range(6)
                ]
            }
        }
        report = blast.analyse(
            plan_with(
                "aws_nat_gateway", ["delete", "create"],
                before={"tags": {"Environment": "production"}},
                after={"tags": {"Environment": "production"}},
                configuration=configuration,
            )
        )
        self.assertEqual(report.worst_tier, "elevated")


class OnTheRealCases(unittest.TestCase):
    def test_the_clean_looking_database_replacement_is_severe(self):
        report = blast.analyse(case("c07_prod_db_replace_clean").load())
        self.assertEqual(report.worst_tier, "severe")
        self.assertTrue(report.any_data_loss)

    def test_the_safe_tagging_case_is_routine(self):
        self.assertEqual(blast.analyse(case("c01_safe_tagging").load()).worst_tier, "routine")

    def test_blast_analysis_is_deterministic(self):
        for entry in load_cases():
            first = blast.analyse(entry.load()).to_dict()
            second = blast.analyse(entry.load()).to_dict()
            self.assertEqual(first, second, entry.id)


if __name__ == "__main__":
    unittest.main()
