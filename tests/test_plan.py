import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cloudfix.plan import PlanError, parse_plan  # noqa: E402


def one(actions, resource_type="aws_s3_bucket", before=None, after=None, address=None, name="thing"):
    return {
        "resource_changes": [
            {
                "address": address or ("%s.%s" % (resource_type, name)),
                "type": resource_type,
                "name": name,
                "change": {"actions": actions, "before": before, "after": after},
            }
        ]
    }


class ActionReading(unittest.TestCase):
    def test_single_actions_pass_through(self):
        for action in ("create", "update", "delete", "no-op", "read"):
            plan = parse_plan(one([action]))
            self.assertEqual(plan.changes[0].action, action)

    def test_delete_then_create_is_a_replacement(self):
        self.assertEqual(parse_plan(one(["delete", "create"])).changes[0].action, "replace")

    def test_create_then_delete_is_also_a_replacement(self):
        self.assertEqual(parse_plan(one(["create", "delete"])).changes[0].action, "replace")

    def test_replace_and_delete_are_destructive_and_update_is_not(self):
        self.assertTrue(parse_plan(one(["delete", "create"])).changes[0].is_destructive)
        self.assertTrue(parse_plan(one(["delete"])).changes[0].is_destructive)
        self.assertFalse(parse_plan(one(["update"])).changes[0].is_destructive)
        self.assertFalse(parse_plan(one(["create"])).changes[0].is_destructive)

    def test_no_ops_are_not_acting_changes(self):
        plan = parse_plan(one(["no-op"]))
        self.assertEqual(plan.acting_changes(), [])


class EnvironmentReading(unittest.TestCase):
    def test_tag_wins(self):
        plan = parse_plan(one(["create"], after={"tags": {"Environment": "production"}}))
        self.assertEqual(plan.changes[0].environment, "production")

    def test_name_is_used_when_there_is_no_tag(self):
        plan = parse_plan(one(["create"], after={"bucket": "lgnd-things-dev"}))
        self.assertEqual(plan.changes[0].environment, "development")

    def test_preprod_is_not_read_as_prod(self):
        plan = parse_plan(one(["create"], after={"tags": {"Environment": "preprod"}}))
        self.assertEqual(plan.changes[0].environment, "staging")

    def test_unknown_when_nothing_says(self):
        plan = parse_plan(one(["create"], after={"bucket": "artifacts"}))
        self.assertEqual(plan.changes[0].environment, "unknown")

    def test_environment_falls_back_to_before_when_the_resource_is_deleted(self):
        plan = parse_plan(one(["delete"], before={"tags": {"Environment": "production"}}, after=None))
        self.assertEqual(plan.changes[0].environment, "production")


class EvidencePaths(unittest.TestCase):
    def test_pointer_is_built_from_the_index(self):
        plan = parse_plan(one(["create"], after={"acl": "public-read"}))
        pointer = plan.changes[0].evidence_path("change", "after", "acl")
        self.assertEqual(pointer, "resource_changes[0].change.after.acl")


class BadInput(unittest.TestCase):
    def test_missing_resource_changes_is_a_clear_error(self):
        with self.assertRaises(PlanError):
            parse_plan({"format_version": "1.2"})

    def test_a_list_is_not_a_plan(self):
        with self.assertRaises(PlanError):
            parse_plan([])

    def test_resource_changes_must_be_a_list(self):
        with self.assertRaises(PlanError):
            parse_plan({"resource_changes": {}})


class References(unittest.TestCase):
    def test_dependents_are_read_from_the_configuration_block(self):
        raw = one(["delete", "create"], resource_type="aws_nat_gateway", name="egress")
        raw["configuration"] = {
            "root_module": {
                "resources": [
                    {
                        "address": "aws_route.a",
                        "expressions": {
                            "nat_gateway_id": {"references": ["aws_nat_gateway.egress.id"]}
                        },
                    },
                    {
                        "address": "aws_route.b",
                        "expressions": {
                            "nat_gateway_id": {"references": ["aws_nat_gateway.egress"]}
                        },
                    },
                    {"address": "aws_s3_bucket.unrelated", "expressions": {}},
                ]
            }
        }
        plan = parse_plan(raw)
        self.assertEqual(
            plan.references_to("aws_nat_gateway.egress"), ["aws_route.a", "aws_route.b"]
        )

    def test_no_configuration_block_means_no_dependents_claimed(self):
        plan = parse_plan(one(["delete"]))
        self.assertEqual(plan.references_to("aws_s3_bucket.thing"), [])


if __name__ == "__main__":
    unittest.main()
