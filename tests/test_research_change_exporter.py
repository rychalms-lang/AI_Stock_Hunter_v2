import json
import tempfile
import unittest
from pathlib import Path

from research_change_exporter import build_research_changes, export_research_changes


FIELDS = [
    "ticker",
    "sector",
    "action",
    "confidence_score",
    "expected_return",
    "score",
    "best_hold_period",
    "historical_matches",
    "risk",
]


def write_report(root, name, rows, fields=None):
    path = Path(root) / name
    columns = fields or FIELDS
    with path.open("w") as f:
        f.write(",".join(columns) + "\n")
        for row in rows:
            f.write(",".join(str(row.get(field, "")) for field in columns) + "\n")
    return path


def row(ticker, sector="Software", action="WATCH", confidence=80, expected=3, score=50):
    return {
        "ticker": ticker,
        "sector": sector,
        "action": action,
        "confidence_score": confidence,
        "expected_return": expected,
        "score": score,
        "best_hold_period": "5 days",
        "historical_matches": 100,
        "risk": "Low",
    }


class ResearchChangeExporterTest(unittest.TestCase):
    def test_one_report_insufficient_history_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir, "2026-07-01_v2.csv", [row("AAA")])
            result = build_research_changes(Path(temp_dir))
            self.assertEqual(result["status"], "insufficient_history")
            self.assertEqual(result["current_date"], "2026-07-01")

    def test_new_candidate_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir, "2026-07-01_v2.csv", [row("AAA")])
            write_report(temp_dir, "2026-07-02_v2.csv", [row("AAA"), row("BBB")])
            result = build_research_changes(Path(temp_dir))
            self.assertEqual(result["summary"]["new_candidates"], 1)
            self.assertEqual(result["new_candidates"][0]["ticker"], "BBB")

    def test_removed_candidate_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir, "2026-07-01_v2.csv", [row("AAA"), row("BBB")])
            write_report(temp_dir, "2026-07-02_v2.csv", [row("AAA")])
            result = build_research_changes(Path(temp_dir))
            self.assertEqual(result["summary"]["removed_candidates"], 1)
            self.assertEqual(result["removed_candidates"][0]["ticker"], "BBB")

    def test_rank_movement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir, "2026-07-01_v2.csv", [row("AAA"), row("BBB")])
            write_report(temp_dir, "2026-07-02_v2.csv", [row("BBB"), row("AAA")])
            result = build_research_changes(Path(temp_dir))
            self.assertEqual(result["summary"]["rank_changes"], 2)
            self.assertEqual(result["rank_changes"][0]["ticker"], "AAA")

    def test_action_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir, "2026-07-01_v2.csv", [row("AAA", action="WATCH")])
            write_report(temp_dir, "2026-07-02_v2.csv", [row("AAA", action="BUY")])
            result = build_research_changes(Path(temp_dir))
            self.assertEqual(result["summary"]["action_changes"], 1)
            self.assertEqual(result["action_changes"][0]["current_action"], "BUY")

    def test_confidence_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir, "2026-07-01_v2.csv", [row("AAA", confidence=80)])
            write_report(temp_dir, "2026-07-02_v2.csv", [row("AAA", confidence=90)])
            result = build_research_changes(Path(temp_dir))
            self.assertEqual(result["summary"]["confidence_changes"], 1)
            self.assertEqual(result["confidence_changes"][0]["change_points"], 10)

    def test_top_opportunity_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir, "2026-07-01_v2.csv", [row("AAA"), row("BBB")])
            write_report(temp_dir, "2026-07-02_v2.csv", [row("BBB"), row("AAA")])
            result = build_research_changes(Path(temp_dir))
            self.assertEqual(result["top_opportunity_change"]["previous"]["ticker"], "AAA")
            self.assertEqual(result["top_opportunity_change"]["current"]["ticker"], "BBB")

    def test_missing_optional_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fields = ["ticker", "action"]
            write_report(temp_dir, "2026-07-01_v2.csv", [{"ticker": "AAA", "action": "WATCH"}], fields)
            write_report(temp_dir, "2026-07-02_v2.csv", [{"ticker": "AAA", "action": "BUY"}], fields)
            result = build_research_changes(Path(temp_dir))
            self.assertEqual(result["summary"]["action_changes"], 1)
            self.assertIsNone(result["top_opportunity_change"]["current"]["confidence"])

    def test_malformed_report_handling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir, "2026-07-01_v2.csv", [row("AAA")])
            write_report(temp_dir, "2026-07-02_v2.csv", [{"symbol": "AAA"}], ["symbol"])
            with self.assertRaises(ValueError):
                build_research_changes(Path(temp_dir))

    def test_stable_output_ordering(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir, "2026-07-01_v2.csv", [row("AAA")])
            write_report(temp_dir, "2026-07-02_v2.csv", [row("AAA"), row("CCC"), row("BBB")])
            result = build_research_changes(Path(temp_dir))
            self.assertEqual([item["ticker"] for item in result["new_candidates"]], ["CCC", "BBB"])

    def test_json_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reports = root / "reports"
            reports.mkdir()
            write_report(reports, "2026-07-01_v2.csv", [row("AAA")])
            write_report(reports, "2026-07-02_v2.csv", [row("BBB")])
            output = root / "research_changes.json"
            export_research_changes(reports, output)
            with output.open() as f:
                payload = json.load(f)
            self.assertEqual(payload["status"], "ready")

    def test_current_report_parameter_pins_current_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            reports = Path(temp_dir)
            write_report(reports, "2026-07-11_v2.csv", [row("HIMS")])
            write_report(reports, "2026-07-12_v2.csv", [row("AAA")])
            current = write_report(reports, "2026-07-13_v2.csv", [row("SE")])
            write_report(reports, "2026-07-14_v2.csv", [row("ZZZ")])

            result = build_research_changes(reports, current_report=current)

            self.assertEqual(result["current_date"], "2026-07-13")
            self.assertEqual(result["previous_date"], "2026-07-12")
            self.assertEqual(result["top_opportunity_change"]["current"]["ticker"], "SE")


if __name__ == "__main__":
    unittest.main()
