from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.google_workspace import read_google_workspace_events


SPREADSHEET_EDITING_ACTIVITY_STIMULUS_TYPES = {
    "cell_range_selected",
    "cell_range_edited",
    "cell_range_filled",
    "row_inserted",
    "row_deleted",
    "column_inserted",
    "column_deleted",
    "sheet_created",
    "sheet_renamed",
    "sheet_deleted",
}
SPREADSHEET_FORMULA_ACTIVITY_STIMULUS_TYPES = {
    "formula_entered",
    "formula_edited",
    "formula_error_detected",
    "formula_error_resolved",
    "named_range_created",
    "named_range_updated",
    "calculation_started",
    "calculation_completed",
    "calculation_failed",
}
SPREADSHEET_DATA_ANALYSIS_ACTIVITY_STIMULUS_TYPES = {
    "sort_applied",
    "filter_applied",
    "filter_cleared",
    "pivot_table_created",
    "pivot_table_changed",
    "chart_created",
    "chart_updated",
    "data_validation_changed",
    "conditional_format_changed",
}
SPREADSHEET_IMPORT_EXPORT_ACTIVITY_STIMULUS_TYPES = {
    "csv_imported",
    "data_connection_refreshed",
    "data_connection_failed",
    "workbook_export_started",
    "workbook_exported",
    "workbook_export_failed",
    "sheet_shared",
    "permissions_changed",
    "workbook_submitted",
}


def collect_spreadsheet_editing_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "spreadsheet_editing_activity", SPREADSHEET_EDITING_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "spreadsheet_editing_activity", SPREADSHEET_EDITING_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_spreadsheet_formula_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "spreadsheet_formula_activity", SPREADSHEET_FORMULA_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "spreadsheet_formula_activity", SPREADSHEET_FORMULA_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_spreadsheet_data_analysis_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "spreadsheet_data_analysis_activity", SPREADSHEET_DATA_ANALYSIS_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config,
        state,
        "spreadsheet_data_analysis_activity",
        SPREADSHEET_DATA_ANALYSIS_ACTIVITY_STIMULUS_TYPES,
        source="activity",
        max_events=20,
    )


def collect_spreadsheet_import_export_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "spreadsheet_import_export_activity", SPREADSHEET_IMPORT_EXPORT_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config,
        state,
        "spreadsheet_import_export_activity",
        SPREADSHEET_IMPORT_EXPORT_ACTIVITY_STIMULUS_TYPES,
        source="activity",
        max_events=20,
    )
