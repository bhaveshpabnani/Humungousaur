import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.travel.implementation import (
    _ixigo_date_label,
    _ixigo_route_url,
    _parse_ixigo_route_trains,
    _parse_ixigo_train_availability,
)
from humungousaur.tools.travel_tools import (
    RailRouteAvailabilityLookupTool,
    TravelBookingIntentInspectTool,
    TravelBookingIntentPrepareTool,
    TravelPlanCreateTool,
    TravelPlanInspectTool,
)


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

    def test_travel_booking_intent_prepare_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            prepared = TravelBookingIntentPrepareTool().execute(
                {
                    "filename": "rail-intent.md",
                    "mode": "rail",
                    "title": "Nagpur to Kharagpur Sleeper Options",
                    "origin": "Nagpur (NGP)",
                    "destination": "Kharagpur Jn (KGP)",
                    "departure_date": "2026-07-02",
                    "travelers": "1 adult",
                    "selected_option_id": "train-18029",
                    "options": [
                        {
                            "option_id": "train-18029",
                            "label": "18029 Mumbai LTT - Shalimar Express",
                            "provider": "RailYatri",
                            "number": "18029",
                            "departure": "13:20",
                            "arrival": "09:05",
                            "class_or_cabin": "SL",
                            "quota_or_fare_family": "General",
                            "fare": "520",
                            "availability_status": "62 Available",
                            "source_ref": "RailYatri live page fixture",
                        }
                    ],
                    "checks": [
                        {
                            "name": "Source-visible date verified",
                            "status": "verified",
                            "evidence": "Page displayed 02 Jul, Thu.",
                        }
                    ],
                    "source_refs": ["fixture"],
                    "reason": "Verify native rail booking intent artifact.",
                },
                config,
            )
            inspected = TravelBookingIntentInspectTool().execute({"path": prepared.output["path"]}, config)
            metadata = json.loads(Path(prepared.output["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(prepared.status, ActionStatus.SUCCEEDED)
        self.assertEqual(prepared.output["booking_status"], "prepared_not_booked")
        self.assertTrue(prepared.output["approval_required"])
        self.assertEqual(prepared.output["option_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["mode"], "rail")
        self.assertEqual(inspected.output["selected_option_id"], "train-18029")
        self.assertEqual(inspected.output["check_count"], 1)
        self.assertIn("No booking", metadata["safety_note"])

    def test_travel_booking_intent_requires_option_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = TravelBookingIntentPrepareTool().execute(
                {"mode": "flight", "options": [{"fare": "$100"}], "reason": "Verify validation."},
                config,
            )

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("requires a label", result.summary)

    def test_travel_booking_intent_schema_requires_concrete_option_label(self) -> None:
        tool = TravelBookingIntentPrepareTool()

        option_schema = tool.input_schema["properties"]["options"]["items"]

        self.assertEqual(option_schema["required"], ["label"])
        self.assertIn("do not use this to search", tool.description)

    def test_rail_lookup_tool_schema_is_read_only_route_availability(self) -> None:
        tool = RailRouteAvailabilityLookupTool()

        self.assertEqual(tool.input_schema["required"], ["journey_date", "reason"])
        self.assertEqual(tool.capability_group, "travel")
        self.assertIn("route/date/class availability", tool.description)
        self.assertIn("does not book", tool.description)

    def test_ixigo_route_url_can_be_constructed_from_origin_destination(self) -> None:
        self.assertEqual(
            _ixigo_route_url("Nagpur (NGP)", "Kharagpur (KGP)"),
            "https://www.ixigo.com/by-train-rail/nagpur-to-kharagpur-by-train",
        )

    def test_ixigo_route_train_parser_extracts_route_links(self) -> None:
        page = """
        <a href="/trains/route-12809-mumbai-csmt-howrah-mail">12809</a>
        <a href="/trains/route-12129-azad-hind-exp">12129</a>
        <a href="/trains/route-12809-mumbai-csmt-howrah-mail">12809</a>
        """

        trains = _parse_ixigo_route_trains(page)

        self.assertEqual([item["train_no"] for item in trains], ["12809", "12129"])
        self.assertEqual(trains[0]["train_name"], "Mumbai Csmt Howrah Mail")

    def test_ixigo_train_availability_parser_classifies_available_and_waitlist(self) -> None:
        available_page = """
        <div>SL</div><div>3A</div>
        <div>July 2026</div>
        <div>Thu, 02 Jul</div><div>AVL4</div><div>Updated a moment ago</div>
        """
        waitlist_page = """
        <div>SL</div>
        <div>July 2026</div>
        <div>Thu, 02 Jul</div><div>WL6</div>
        """

        self.assertEqual(_ixigo_date_label("2026-07-02"), "Thu, 02 Jul")
        available = _parse_ixigo_train_availability(available_page, date_label="Thu, 02 Jul", class_code="SL")
        waitlisted = _parse_ixigo_train_availability(waitlist_page, date_label="Thu, 02 Jul", class_code="SL")

        self.assertEqual(available["category"], "available")
        self.assertEqual(available["status"], "AVL4")
        self.assertEqual(waitlisted["category"], "waitlisted")
        self.assertEqual(waitlisted["status"], "WL6")

    def test_ixigo_train_availability_parser_marks_missing_date_unresolved(self) -> None:
        page = "<div>SL</div><div>July 2026</div><div>Tue, 07 Jul</div><div>NA</div>"

        parsed = _parse_ixigo_train_availability(page, date_label="Thu, 02 Jul", class_code="SL")

        self.assertEqual(parsed["category"], "unresolved")
        self.assertIn("not visible", parsed["evidence"])


if __name__ == "__main__":
    unittest.main()
