import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.travel_tools import TravelPlanCreateTool, TravelPlanInspectTool


class TravelToolTests(unittest.TestCase):
    def test_travel_plan_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = TravelPlanCreateTool().execute(
                {
                    "filename": "weekend.md",
                    "title": "Weekend Commute Plan",
                    "origin": "Home area",
                    "destination": "Museum district",
                    "date_range": "2026-06-13",
                    "preferences": ["low walking", "avoid late-night returns"],
                    "constraints": ["verify hours on the day of travel"],
                    "places": [{"name": "City Museum", "kind": "museum", "location": "Museum district", "hours": "10:00-17:00", "cost": "ticketed", "source_ref": "provided fixture"}],
                    "route_options": [{"label": "Transit option", "mode": "metro", "estimated_duration": "35 min", "estimated_cost": "$3", "reliability": "medium", "accessibility": "elevator status unknown"}],
                    "itinerary_days": [{"label": "Saturday", "summary": "Transit-first plan.", "items": [{"time": "10:00", "activity": "Leave home", "location": "Home area"}]}],
                    "source_refs": ["provided fixture"],
                    "uncertainties": ["Live transit disruptions not checked."],
                    "reason": "Verify native travel artifact creation.",
                },
                config,
            )
            inspected = TravelPlanInspectTool().execute({"path": created.output["path"]}, config)
            metadata = json.loads(Path(created.output["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["place_count"], 1)
        self.assertEqual(created.output["route_option_count"], 1)
        self.assertEqual(created.output["approval_status"], "planning_only_not_booked")
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["uncertainty_count"], 1)
        self.assertIn("No bookings", metadata["approval_boundaries"][0])

    def test_travel_plan_requires_title_and_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = TravelPlanCreateTool().execute({"title": "Missing reason"}, config)

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("title and reason", result.summary)


if __name__ == "__main__":
    unittest.main()
