"""Business-rule and failure-path tests for the portfolio pipeline."""
import contextlib
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import survey_pipeline as pipeline


def row(identifier="SYN-001", **changes):
    return dict({
        "response_id": identifier, "market": "United States", "channel": "Web",
        "submitted_at": "2026-08-03T10:00:00Z", "completed": "true",
        "duration_seconds": "120", "satisfaction_score": "5",
    }, **changes)


class PipelineTests(unittest.TestCase):
    def test_first_valid_id_wins_not_first_invalid_occurrence(self):
        accepted, rejected = pipeline.validate_rows([
            row(satisfaction_score="9"), row(), row(duration_seconds="180"),
        ])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["duration"], 120)
        self.assertEqual([r["reason"] for r in rejected], ["invalid_satisfaction_score", "duplicate_id"])

    def test_kpi_denominators_exclude_incomplete_scores_and_durations(self):
        accepted, rejected = pipeline.validate_rows([
            row("A", duration_seconds="100", satisfaction_score="5"),
            row("B", duration_seconds="120", satisfaction_score="4"),
            row("C", duration_seconds="180", satisfaction_score="2"),
            row("D", duration_seconds="300", completed="false", satisfaction_score=""),
        ])
        self.assertEqual(rejected, [])
        summary = pipeline.summarize(accepted)
        self.assertEqual(summary, {"responses": 4, "completed": 3, "completionRate": 75.0, "csat": 66.67, "medianDuration": 120})

    def test_demo_reconciles_and_has_expected_primary_rejection_reasons(self):
        raw = pipeline.generate_demo()
        clean, rejected = pipeline.validate_rows(raw)
        self.assertEqual((len(raw), len(clean), len(rejected)), (7300, 7200, 100))
        self.assertEqual(pipeline.Counter(r["reason"] for r in rejected), {
            "duplicate_id": 48, "missing_id": 24, "invalid_satisfaction_score": 18, "invalid_duration": 10,
        })
        self.assertEqual(len({r["id"] for r in clean}), 7200)
        self.assertEqual(len({r["week"] for r in clean}), 12)
        self.assertEqual(pipeline.generate_demo(), raw)

    def test_empty_or_missing_header_fails_helpfully(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            for text in ("", ",".join(pipeline.FIELDS) + "\n", "response_id,market\nA,Canada\n"):
                path.write_text(text)
                with self.assertRaises(pipeline.PipelineError):
                    pipeline.read_source(path)

    def test_exports_preserve_source_and_sha_and_do_not_overwrite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "original.csv"
            pipeline.write_csv(source, pipeline.FIELDS, [row(), row("B", completed="false", satisfaction_score="")])
            original = source.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                result = pipeline.run_pipeline(source, root / "out")
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(result["meta"]["inputSha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(result["meta"]["inputRows"], result["meta"]["cleanRows"] + result["meta"]["rejectedRows"])
            clean_input = root / "out" / "survey_clean.csv"
            cleaned_bytes = clean_input.read_bytes()
            with self.assertRaises(pipeline.PipelineError):
                pipeline.run_pipeline(clean_input, root / "out")
            self.assertEqual(clean_input.read_bytes(), cleaned_bytes)

    def test_invalid_category_or_completion_flag_is_quarantined(self):
        accepted, rejected = pipeline.validate_rows([row("A", market="Atlantis"), row("B", completed="maybe")])
        self.assertEqual(accepted, [])
        self.assertEqual([r["reason"] for r in rejected], ["invalid_market", "invalid_completed"])


if __name__ == "__main__":
    unittest.main()
