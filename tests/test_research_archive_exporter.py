import tempfile
import unittest
from pathlib import Path

import research_archive_exporter


def write_report(root):
    path = Path(root) / "2026-07-02_v2.csv"
    path.write_text(
        "ticker,sector,action,confidence_score,expected_return,score,best_hold_period,historical_matches,risk\n"
        "AAA,Software,WATCH,88,3.5,52.1,5 days,121,Low\n"
    )
    return path


class ResearchArchiveExporterTest(unittest.TestCase):
    def test_archive_detail_payload_contains_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_report(temp_dir)
            original_reports_dir = research_archive_exporter.REPORTS_DIR
            try:
                research_archive_exporter.REPORTS_DIR = Path(temp_dir)
                payload = research_archive_exporter.build_archive()
            finally:
                research_archive_exporter.REPORTS_DIR = original_reports_dir

            self.assertEqual(len(payload["items"]), 1)
            item = payload["items"][0]
            self.assertEqual(item["date"], "2026-07-02")
            self.assertEqual(item["strategy"]["status"], "Champion")
            self.assertEqual(item["source_metadata"]["future_outcomes_exposed"], False)
            self.assertEqual(item["candidates"][0]["ticker"], "AAA")
            self.assertEqual(item["candidates"][0]["best_hold_period_days"], 5)


if __name__ == "__main__":
    unittest.main()
