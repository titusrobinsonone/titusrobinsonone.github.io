"""Checks for the salary survey data-quality pipeline (standard library only).

Run from the repository root:
    python -m unittest discover -s src/tests -v
"""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import salary_survey_qa as qa  # noqa: E402

HEADER = list(qa.COLUMNS)


def make_row(**over):
    base = {
        "Timestamp": "4/27/2021 11:02:10", "How old are you?": "25-34",
        "Industry": "Computing or Tech", "Job title": "Data Analyst",
        "Additional context on job title": "", "Annual salary": "75,000",
        "Other monetary comp": "0", "Currency": "USD", "Currency - other": "",
        "Additional context on income": "", "Country": "USA", "State": "Ohio",
        "City": "Columbus", "Overall years of professional experience": "5-7 years",
        "Years of experience in field": "2 - 4 years",
        "Highest level of education completed": "College degree",
        "Gender": "Woman", "Race": "White",
    }
    base.update(over)
    return base


def run_rows(rows):
    tmp = Path(tempfile.mkdtemp())
    src = tmp / "in.csv"
    with src.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    report = qa.run(src, tmp / "out")
    return report, tmp / "out"


class ParsingTests(unittest.TestCase):
    def test_money_formats(self):
        self.assertEqual(qa.parse_money("55,000"), 55000)
        self.assertEqual(qa.parse_money("$72k"), 72000)
        self.assertIsNone(qa.parse_money("about fifty"))
        self.assertIsNone(qa.parse_money(""))

    def test_country_spellings_collapse(self):
        for raw in ["USA", "U.S.", "united states of america", "Untied States", "\U0001F1FA\U0001F1F8"]:
            self.assertEqual(qa.normalize_country(raw)[0], "United States", raw)
        self.assertEqual(qa.normalize_country("England")[0], "United Kingdom")

    def test_country_first_mention_wins(self):
        self.assertEqual(qa.normalize_country("UK for U.S. company")[0], "United Kingdom")
        self.assertEqual(qa.normalize_country("I am located in Canada but I work for a company in the US")[0], "Canada")

    def test_aud_nzd_split_by_country(self):
        self.assertEqual(qa.resolve_currency("AUD/NZD", "", "New Zealand")[0], "NZD")
        self.assertEqual(qa.resolve_currency("AUD/NZD", "", "Australia")[0], "AUD")
        self.assertEqual(qa.resolve_currency("Other", "Dkk", "Denmark")[0], "DKK")


class PrivacyAndCodingTests(unittest.TestCase):
    def test_pii_redaction(self):
        text, hits = qa.redact_pii("email me at jane.doe@example.com or 555-123-4567, see www.site.org")
        self.assertNotIn("jane.doe", text)
        self.assertEqual(hits["EMAIL"], 1)
        self.assertEqual(hits["PHONE"], 1)
        self.assertEqual(hits["URL"], 1)

    def test_codeframe_multicode_and_negation(self):
        self.assertEqual(set(qa.code_open_end("20% bonus plus RSUs")), {"Bonus / incentive", "Equity / stock"})
        self.assertIn("Overtime / shift pay (none)", qa.code_open_end("Salaried, so no overtime is available"))
        self.assertEqual(qa.code_open_end("   "), [])

    def test_k_anonymity_counts_groups(self):
        rows = [{"a": 1, "b": 1}, {"a": 1, "b": 1}, {"a": 2, "b": 1}]
        groups = qa.k_anonymity(rows, ["a", "b"])
        self.assertEqual(groups[(1, 1)], 2)
        self.assertEqual(groups[(2, 1)], 1)


class PipelineTests(unittest.TestCase):
    def test_every_row_reconciles_and_rules_fire(self):
        rows = [
            make_row(),
            make_row(),  # exact duplicate of row 1 (timestamp ignored)
            make_row(**{"Job title": "Analyst II", "Annual salary": "85"}),  # entered in thousands
            make_row(**{"Job title": "PM", "Currency": "Other", "Currency - other": "seashells"}),
            make_row(**{"Job title": "Engineer", "Years of experience in field": "11 - 20 years"}),
            make_row(**{"Job title": "Lead", "State": "Ohio, Kentucky"}),
        ]
        report, out = run_rows(rows)
        self.assertTrue(report["reconciles"])
        self.assertEqual(report["rows_in"], 6)
        rules = {r["rule"] for r in report["rules"]}
        for expected in ["duplicate_submission", "salary_likely_in_thousands_or_hourly",
                         "currency_unresolved", "field_exp_exceeds_overall", "us_multiple_states"]:
            self.assertIn(expected, rules)
        with (out / "rejected.csv").open(encoding="utf-8") as fh:
            self.assertEqual(len(list(csv.DictReader(fh))), 3)
        json.loads((out / "quality_report.json").read_text(encoding="utf-8"))

    def test_source_file_unchanged(self):
        rows = [make_row(), make_row(**{"Job title": "X"})]
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "in.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=HEADER)
            w.writeheader()
            w.writerows(rows)
        before = src.read_bytes()
        qa.run(src, tmp / "out")
        self.assertEqual(before, src.read_bytes())


if __name__ == "__main__":
    unittest.main()
