from __future__ import annotations

from typing import Any


_EXPORTS = {
    "ai_assistant_source_status": (".ai_assistants", "ai_assistant_source_status"),
    "append_ai_assistant_event": (".ai_assistants", "append_ai_assistant_event"),
    "append_ai_assistant_health": (".ai_assistants", "append_ai_assistant_health"),
    "append_browser_event": (".browser", "append_browser_event"),
    "append_browser_health": (".browser", "append_browser_health"),
    "append_business_operations_event": (".business_operations", "append_business_operations_event"),
    "append_business_operations_health": (".business_operations", "append_business_operations_health"),
    "append_cloud_file_event": (".cloud_files", "append_cloud_file_event"),
    "append_communication_event": (".communication", "append_communication_event"),
    "append_communication_health": (".communication", "append_communication_health"),
    "append_connector_source_event": (".workspace_connectors", "append_connector_source_event"),
    "append_data_analytics_event": (".data_analytics", "append_data_analytics_event"),
    "append_data_analytics_health": (".data_analytics", "append_data_analytics_health"),
    "append_code_hosting_webhook_event": (".developer", "append_code_hosting_webhook_event"),
    "append_developer_source_event": (".developer", "append_developer_source_event"),
    "append_design_event": (".design", "append_design_event"),
    "append_design_health": (".design", "append_design_health"),
    "append_discord_call_gateway_event": (".meetings", "append_discord_call_gateway_event"),
    "append_discord_gateway_event": (".communication", "append_discord_gateway_event"),
    "append_google_chat_event": (".communication", "append_google_chat_event"),
    "append_google_workspace_event": (".google_workspace", "append_google_workspace_event"),
    "append_google_workspace_health": (".google_workspace", "append_google_workspace_health"),
    "append_google_meet_event": (".meetings", "append_google_meet_event"),
    "append_knowledge_base_event": (".knowledge_base", "append_knowledge_base_event"),
    "append_knowledge_base_health": (".knowledge_base", "append_knowledge_base_health"),
    "append_microsoft_365_event": (".microsoft_365", "append_microsoft_365_event"),
    "append_microsoft_365_health": (".microsoft_365", "append_microsoft_365_health"),
    "append_meeting_source_event": (".meetings", "append_meeting_source_event"),
    "append_meeting_source_health": (".meetings", "append_meeting_source_health"),
    "append_planning_event": (".planning", "append_planning_event"),
    "append_planning_health": (".planning", "append_planning_health"),
    "append_operations_event": (".operations", "append_operations_event"),
    "append_operations_health": (".operations", "append_operations_health"),
    "append_signal_cli_receive": (".communication", "append_signal_cli_receive"),
    "append_slack_events_api_event": (".communication", "append_slack_events_api_event"),
    "append_teams_graph_chat_notification": (".communication", "append_teams_graph_chat_notification"),
    "append_teams_meeting_graph_event": (".meetings", "append_teams_meeting_graph_event"),
    "append_telegram_bot_update": (".communication", "append_telegram_bot_update"),
    "append_webex_webhook_event": (".meetings", "append_webex_webhook_event"),
    "append_whatsapp_cloud_webhook": (".communication", "append_whatsapp_cloud_webhook"),
    "append_zoom_webhook_event": (".meetings", "append_zoom_webhook_event"),
    "browser_source_status": (".browser", "browser_source_status"),
    "business_operations_app_status_records": (".business_operations", "business_operations_app_status_records"),
    "business_operations_source_status": (".business_operations", "business_operations_source_status"),
    "cloud_file_source_status": (".cloud_files", "cloud_file_source_status"),
    "communication_source_status": (".communication", "communication_source_status"),
    "connector_source_manifest_records": (".workspace_connectors", "connector_source_manifest_records"),
    "connector_source_status": (".workspace_connectors", "connector_source_status"),
    "data_analytics_app_status_records": (".data_analytics", "data_analytics_app_status_records"),
    "data_analytics_source_status": (".data_analytics", "data_analytics_source_status"),
    "design_app_status_records": (".design", "design_app_status_records"),
    "design_source_status": (".design", "design_source_status"),
    "google_workspace_source_status": (".google_workspace", "google_workspace_source_status"),
    "knowledge_base_source_status": (".knowledge_base", "knowledge_base_source_status"),
    "meeting_app_status_records": (".meetings", "meeting_app_status_records"),
    "meeting_source_status": (".meetings", "meeting_source_status"),
    "microsoft_365_source_status": (".microsoft_365", "microsoft_365_source_status"),
    "normalize_code_hosting_webhook": (".developer", "normalize_code_hosting_webhook"),
    "normalize_developer_source_event": (".developer", "normalize_developer_source_event"),
    "operations_app_status_records": (".operations", "operations_app_status_records"),
    "operations_source_status": (".operations", "operations_source_status"),
    "planning_source_status": (".planning", "planning_source_status"),
    "planning_source_status_map": (".planning", "planning_source_status_map"),
    "PLANNING_PROVIDER_IDS": (".planning", "PLANNING_PROVIDER_IDS"),
    "read_business_operations_events": (".business_operations", "read_business_operations_events"),
    "read_communication_events": (".communication", "read_communication_events"),
    "read_data_analytics_events": (".data_analytics", "read_data_analytics_events"),
    "read_design_events": (".design", "read_design_events"),
    "read_google_workspace_events": (".google_workspace", "read_google_workspace_events"),
    "read_knowledge_base_events": (".knowledge_base", "read_knowledge_base_events"),
    "read_microsoft_365_events": (".microsoft_365", "read_microsoft_365_events"),
    "read_meeting_source_events": (".meetings", "read_meeting_source_events"),
    "read_operations_events": (".operations", "read_operations_events"),
    "read_planning_events": (".planning", "read_planning_events"),
    "record_connector_source_health": (".workspace_connectors", "record_connector_source_health"),
    "run_business_operations_source_tick": (".business_operations", "run_business_operations_source_tick"),
    "run_communication_source_tick": (".communication", "run_communication_source_tick"),
    "run_connector_source_tick": (".workspace_connectors", "run_connector_source_tick"),
    "run_data_analytics_source_tick": (".data_analytics", "run_data_analytics_source_tick"),
    "run_developer_source_tick": (".developer", "run_developer_source_tick"),
    "run_design_source_tick": (".design", "run_design_source_tick"),
    "run_knowledge_base_source_tick": (".knowledge_base", "run_knowledge_base_source_tick"),
    "run_meeting_source_tick": (".meetings", "run_meeting_source_tick"),
    "run_operations_source_tick": (".operations", "run_operations_source_tick"),
    "run_planning_source_tick": (".planning", "run_planning_source_tick"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    from importlib import import_module

    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = sorted(_EXPORTS)
