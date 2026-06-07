import csv
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.analysis import (
    BusinessReportCreateTool,
    ChartArtifactCreateTool,
    ChartArtifactInspectTool,
    CsvDatasetProfileTool,
)


class AnalysisToolTests(unittest.TestCase):
    def test_csv_profile_chart_and_report_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            csv_path = workspace / "sales.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["month", "revenue", "cost"])
                writer.writerow(["Jan", "100", "40"])
                writer.writerow(["Feb", "125", "50"])
                writer.writerow(["Mar", "150", ""])
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            profile = CsvDatasetProfileTool().execute({"path": "sales.csv", "sample_rows": 3}, config)
            chart = ChartArtifactCreateTool().execute(
                {
                    "filename": "sales-chart.svg",
                    "title": "Quarter Revenue",
                    "chart_type": "bar",
                    "x_label": "Month",
                    "y_label": "Revenue",
                    "data": [{"label": "Jan", "value": 100}, {"label": "Feb", "value": 125}, {"label": "Mar", "value": 150}],
                    "source_note": "Source: sales.csv",
                    "reason": "Smoke test chart creation.",
                },
                config,
            )
            chart_inspect = ChartArtifactInspectTool().execute({"path": chart.output["path"]}, config)
            report = BusinessReportCreateTool().execute(
                {
                    "filename": "sales-report.md",
                    "title": "Sales Smoke Report",
                    "audience": "Ops",
                    "period": "Q1",
                    "summary": "Revenue increased month over month in the sample data.",
                    "metrics": [{"name": "Rows", "value": profile.output["row_count"], "note": "Sample rows"}],
                    "findings": ["March has the highest revenue."],
                    "recommendations": ["Review missing March cost before final reporting."],
                    "artifact_paths": [chart.output["path"]],
                    "assumptions": ["Input CSV is a local smoke fixture."],
                    "reason": "Smoke test business reporting.",
                },
                config,
            )

            self.assertEqual(profile.status, ActionStatus.SUCCEEDED)
            self.assertEqual(profile.output["row_count"], 3)
            self.assertEqual(profile.output["missing_counts"]["cost"], 1)
            self.assertEqual(profile.output["numeric_summary"]["revenue"]["max"], 150.0)
            self.assertEqual(chart.status, ActionStatus.SUCCEEDED)
            self.assertTrue(Path(chart.output["path"]).exists())
            self.assertEqual(chart_inspect.status, ActionStatus.SUCCEEDED)
            self.assertEqual(chart_inspect.output["title"], "Quarter Revenue")
            self.assertEqual(chart_inspect.output["point_count"], 3)
            self.assertEqual(report.status, ActionStatus.SUCCEEDED)
            self.assertIn("Sales Smoke Report", Path(report.output["path"]).read_text(encoding="utf-8"))

    def test_analysis_tools_are_in_global_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tools = default_tools(config)

        self.assertIn("csv_dataset_profile", tools)
        self.assertIn("chart_artifact_create", tools)
        self.assertIn("chart_artifact_inspect", tools)
        self.assertIn("business_report_create", tools)
        self.assertEqual(tools["csv_dataset_profile"].capability_group, "analysis")


if __name__ == "__main__":
    unittest.main()
