"""
Every number in the README, checked against the results files it came from.

Ground rule 09 says connect every claim about your results to the evidence you
submit. This file is that connection, made mechanical. It reads
`results/*_results.json` and asserts that the figures written in `README.md` and
`IMPROVEMENT_CHANGELOG.md` are the figures those files actually contain.

If someone reruns the evaluation and a number moves, these tests fail and the
writeup has to be corrected. A stale claim cannot sit quietly in the README.

The tests skip themselves when the results files are absent, so a fresh clone
that has not run anything yet still passes `python run.py test`.
"""

import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")


# Keys the current scorer writes. A results file from an older run will not have
# them, and that is a stale file rather than a broken project, so the tests below
# skip rather than erroring out with a KeyError.
REQUIRED_KEYS = ("correct", "counts_by_difficulty", "critical_resource_caught")


def load(system):
    path = os.path.join(RESULTS, "%s_results.json" % system)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if any(key not in data for key in REQUIRED_KEYS):
        return None
    return data


def read(name):
    with open(os.path.join(ROOT, name), "r", encoding="utf-8") as handle:
        return handle.read()


def pct(value):
    return "%.0f%%" % (value * 100)


class HeadlineTable(unittest.TestCase):
    SYSTEMS = ("baseline", "scanner", "agent")

    def setUp(self):
        self.data = {name: load(name) for name in self.SYSTEMS}
        if any(value is None for value in self.data.values()):
            self.skipTest(
                "results are missing or predate the current scorer. Run: "
                "python run.py eval --system ladder --mode replay"
            )
        self.readme = read("README.md")

    def row(self, label, render, bold_last=True):
        cells = []
        for index, name in enumerate(self.SYSTEMS):
            value = render(self.data[name])
            last = index == len(self.SYSTEMS) - 1
            cells.append("**%s**" % value if last and bold_last else value)
        return "| %s | %s |" % (label, " | ".join(cells))

    def assertRow(self, label, render, bold_last=True):
        expected = self.row(label, render, bold_last)
        self.assertIn(
            expected,
            self.readme,
            "README does not contain the row the results produce:\n  %s" % expected,
        )

    def test_verdict_accuracy_row(self):
        self.assertRow(
            "Verdict accuracy (primary)", lambda d: "%d/%d" % (d["correct"], d["cases"])
        )

    def test_dangerous_misses_row(self):
        self.assertRow(
            "Dangerous misses",
            lambda d: "%d/%d" % (len(d["dangerous_miss_cases"]), d["cases"]),
        )

    def test_over_blocked_row(self):
        self.assertRow(
            "Over blocked", lambda d: "%d/%d" % (len(d["over_block_cases"]), d["cases"])
        )

    def test_hard_case_row(self):
        self.assertRow(
            "The 5 hard cases",
            lambda d: "%d/%d"
            % (d["counts_by_difficulty"]["hard"]["correct"],
               d["counts_by_difficulty"]["hard"]["total"]),
        )

    def test_the_critical_resource_diagnostic_is_quoted_with_its_denominator(self):
        """It is not in the table, so check the sentence that carries it instead."""
        expected = "Baseline %d/%d, scanner %d/%d, CloudFix %d/%d" % (
            self.data["baseline"]["critical_resource_caught"],
            self.data["baseline"]["critical_resource_cases"],
            self.data["scanner"]["critical_resource_caught"],
            self.data["scanner"]["critical_resource_cases"],
            self.data["agent"]["critical_resource_caught"],
            self.data["agent"]["critical_resource_cases"],
        )
        self.assertIn(expected, self.readme)
        self.assertIn(
            "over the\n13 cases that name one", self.readme.replace("\r", "")
        )

    def test_unsupported_citations_row(self):
        self.assertRow(
            "Citations that do not resolve",
            lambda d: "%d/%d" % (d["reasons_unsupported"], d["reasons_total"]),
        )

    def test_cost_row(self):
        self.assertRow(
            "Cost per review (USD)",
            lambda d: "%.5f" % d["cost_usd_per_review"],
            bold_last=False,
        )

    def test_model_seconds_row(self):
        self.assertRow(
            "Model seconds per review",
            lambda d: "%.1f" % d["mean_model_seconds_per_review"],
            bold_last=False,
        )


class LadderTable(unittest.TestCase):
    """The ladder numbers, in both documents that quote them."""

    LADDER = (
        "baseline",
        "scanner",
        "agent-checks",
        "agent-checks-blast",
        "agent-checks-blast-verify",
        "agent",
    )

    def setUp(self):
        self.data = {name: load(name) for name in self.LADDER}
        if any(value is None for value in self.data.values()):
            self.skipTest(
                "ladder results are missing or predate the current scorer. Run: "
                "python run.py eval --system ladder --mode replay"
            )
        self.readme = read("README.md")
        self.changelog = read("IMPROVEMENT_CHANGELOG.md")

    def test_every_rung_accuracy_appears_in_both_documents(self):
        for name in self.LADDER:
            data = self.data[name]
            value = "%d/%d" % (data["correct"], data["cases"])
            self.assertIn(value, self.readme, name)
            self.assertIn(value, self.changelog, name)

    def test_the_regression_and_the_recovery_are_stated_correctly(self):
        """The whole argument of Part 2 lives in these two deltas."""
        checks_only = self.data["agent-checks"]["verdict_accuracy"] * 100
        with_blast = self.data["agent-checks-blast"]["verdict_accuracy"] * 100
        with_verify = self.data["agent-checks-blast-verify"]["verdict_accuracy"] * 100

        self.assertLess(with_blast, checks_only, "the blast rung is claimed to regress")
        self.assertGreater(with_verify, with_blast, "verification is claimed to recover it")

        for document in (self.readme, self.changelog):
            self.assertIn("%+.0f pts" % (with_blast - checks_only), document)
            self.assertIn("%+.0f pts" % (with_verify - with_blast), document)

    def test_the_shipped_system_needed_no_repairs(self):
        """The hot take rests on this. If it stops being true, the hot take is wrong."""
        self.assertEqual(self.data["agent"]["repairs_total"], 0)
        self.assertIn("zero repairs", (self.readme + self.changelog).lower())

    def test_verification_did_the_work_on_the_blast_path(self):
        self.assertGreaterEqual(self.data["agent-checks-blast-verify"]["repairs_total"], 1)


class ConsistencyClaims(unittest.TestCase):
    def setUp(self):
        path = os.path.join(RESULTS, "consistency.json")
        if not os.path.exists(path):
            self.skipTest("consistency study not run yet")
        with open(path, "r", encoding="utf-8") as handle:
            self.payload = json.load(handle)
        self.readme = read("README.md")

    def test_the_per_run_accuracies_are_quoted_correctly(self):
        """Quoted as fractions, so nobody reads sixteen cases as a large study."""
        for report in self.payload["reports"]:
            values = report["verdict_accuracy_by_sample"]
            cases = report["cases"]
            quoted = ", ".join("%d/%d" % (round(v * cases), cases) for v in values)
            self.assertIn(quoted, self.readme, report["system"])


class NoBarePercentagesInTheHeadlineTable(unittest.TestCase):
    """Sixteen cases is a small number and the README must not hide it.

    Every headline figure is published as a fraction. This asserts the habit
    rather than any particular value, so it keeps holding after a rerun.
    """

    def setUp(self):
        if load("agent") is None:
            self.skipTest("no results on disk yet")
        self.readme = read("README.md")

    def test_the_headline_table_uses_fractions(self):
        start = self.readme.index("| Metric | One prompt, no tools |")
        table = self.readme[start : self.readme.index("One diagnostic", start)]
        for row in ("Verdict accuracy (primary)", "Dangerous misses", "Over blocked",
                    "The 5 hard cases", "Citations that do not resolve"):
            line = [l for l in table.splitlines() if l.startswith("| " + row)]
            self.assertTrue(line, row)
            self.assertNotIn("%", line[0], "%s is quoted as a bare percentage" % row)


class NarrativeClaims(unittest.TestCase):
    """A few sentences in the README assert facts about specific cases."""

    def setUp(self):
        self.scanner = load("scanner")
        self.agent = load("agent")
        self.baseline = load("baseline")
        if not all((self.scanner, self.agent, self.baseline)):
            self.skipTest("no results on disk yet")

    def test_the_scanner_really_does_miss_the_database_destruction(self):
        self.assertIn("c07_prod_db_replace_clean", self.scanner["dangerous_miss_cases"])

    def test_the_scanner_really_does_over_block_the_tag_edit(self):
        self.assertIn("c15_preexisting_open_port", self.scanner["over_block_cases"])

    def test_the_baseline_really_does_fail_on_the_two_named_cases(self):
        self.assertEqual(
            sorted(self.baseline["wrong_cases"]),
            ["c12_dev_static_website", "c15_preexisting_open_port"],
        )

    def test_cloudfix_really_is_wrong_on_nothing(self):
        self.assertEqual(self.agent["wrong_cases"], [])
        self.assertEqual(self.agent["dangerous_miss_cases"], [])
        self.assertEqual(self.agent["over_block_cases"], [])

    def test_the_cost_difference_is_quoted_honestly(self):
        """The README says CloudFix is 13% dearer than the unaided prompt."""
        ratio = self.agent["cost_usd_per_review"] / self.baseline["cost_usd_per_review"]
        self.assertAlmostEqual(ratio, 1.13, places=2)


if __name__ == "__main__":
    unittest.main()
