from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from humungousaur.api import run_api_server
from humungousaur.client_protocol import run_client_protocol_stdio
from humungousaur.collectors import (
    collector_status,
    run_collector_loop,
    run_collector_tick,
    save_collector_profile,
)
from humungousaur.config import AgentConfig
from humungousaur.cognition.loop import AutonomousLoopRunner, autonomous_loop_result_to_dict, autonomous_status
from humungousaur.cognition.semantic_events import rebuild_current_context, semantic_events_status
from humungousaur.env import load_workspace_environment
from humungousaur.indexing import FileIndex
from humungousaur.integrations.voice_wakeup import handle_activation, run_activation
from humungousaur.interaction import InteractionHarness, harness_result_to_dict
from humungousaur.memory.event_store import EventStore
from humungousaur.memory.profile import build_user_profile
from humungousaur.memory.summary import SUMMARY_PERIODS, summarize_memory
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.performance import run_benchmarks
from humungousaur.runtime import (
    approval_record_to_dict,
    approve_pending_action,
    reject_pending_action,
    update_pending_approval_input,
)
from humungousaur.safety.approvals import ApprovalStore
from humungousaur.safety.audit import AuditLog
from humungousaur.tools.cognition_tools import (
    AutomationDaemonConfigureTool,
    AutomationDaemonStatusTool,
    AutomationDaemonTickTool,
    MultiAgentBoardTool,
    SkillForgePacksTool,
)
from humungousaur.tools.os_tools import list_screenshot_captures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Humungousaur local-first agent runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run a text task through the local agent")
    run.add_argument("request", help="Natural-language task")
    run.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace the agent may read")
    run.add_argument("--data-dir", type=Path, default=Path("artifacts"), help="Directory for audit logs and notes")
    run.add_argument("--json", action="store_true", help="Print structured JSON")
    run.add_argument("--dry-run", action="store_true", help="Plan and execute read-only actions without writing notes")
    run.add_argument("--approve-high-risk", action="store_true", help="Approve high-risk tool calls for this run")
    _add_planner_args(run)

    audit = subparsers.add_parser("audit", help="Show recent audited runs")
    audit.add_argument("--workspace", type=Path, default=Path.cwd())
    audit.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    audit.add_argument("--limit", type=int, default=10)

    plans = subparsers.add_parser("plans", help="Show recent planner traces")
    plans.add_argument("--workspace", type=Path, default=Path.cwd())
    plans.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    plans.add_argument("--limit", type=int, default=10)
    plans.add_argument("--run-id", default=None)

    voice = subparsers.add_parser("run-activation", help="Run a saved voice-wakeup activation transcript")
    voice.add_argument("activation_json", type=Path, help="Path to voice-wakeup activation metadata JSON")
    voice.add_argument("--workspace", type=Path, default=Path.cwd())
    voice.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    voice.add_argument("--json", action="store_true")
    voice.add_argument("--harness", action="store_true", help="Route the activation through the interaction harness")
    voice.add_argument(
        "--response-mode",
        choices=("text", "voice_prepare", "voice_speak", "silent"),
        default="voice_prepare",
        help="Harness response mode when --harness is used",
    )
    voice.add_argument("--stt-provider", default="", help="Speech-to-text provider for activation audio, such as deepgram")
    voice.add_argument("--tts-provider", default="", help="Text-to-speech provider for harness voice output, such as elevenlabs or system")
    voice.add_argument("--voice-id", default="", help="Provider voice id for TTS output")
    voice.add_argument("--tts-model", default="", help="Provider TTS model id")
    voice.add_argument("--approve-high-risk", action="store_true")
    _add_planner_args(voice)

    stimulus = subparsers.add_parser("stimulus", help="Handle a user, voice, or passive activity stimulus through the interaction harness")
    stimulus.add_argument("text", help="Stimulus text or transcript")
    stimulus.add_argument("--source", default="user_text", help="Stimulus source such as user_text, voice_transcript, activity, screen_ocr, or browser")
    stimulus.add_argument(
        "--response-mode",
        choices=("text", "voice_prepare", "voice_speak", "silent"),
        default=None,
        help="Override harness response mode",
    )
    stimulus.add_argument("--workspace", type=Path, default=Path.cwd())
    stimulus.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    stimulus.add_argument("--json", action="store_true")
    stimulus.add_argument("--tts-provider", default="", help="Text-to-speech provider when response mode is voice_prepare or voice_speak")
    stimulus.add_argument("--voice-id", default="", help="Provider voice id for TTS output")
    stimulus.add_argument("--tts-model", default="", help="Provider TTS model id")
    stimulus.add_argument("--allow-voice-lookup", action="store_true", help="Allow ElevenLabs to choose the first account voice when no voice id is set")
    stimulus.add_argument("--no-playback", action="store_true", help="Synthesize provider audio without playing it locally")
    stimulus.add_argument("--approve-high-risk", action="store_true")
    _add_planner_args(stimulus)

    memory = subparsers.add_parser("memory", help="Show recent memory events")
    memory.add_argument("--workspace", type=Path, default=Path.cwd())
    memory.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    memory.add_argument("--limit", type=int, default=10)

    memory_search = subparsers.add_parser("memory-search", help="Search memory events")
    memory_search.add_argument("query")
    memory_search.add_argument("--workspace", type=Path, default=Path.cwd())
    memory_search.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    memory_search.add_argument("--limit", type=int, default=10)

    memory_summary = subparsers.add_parser("memory-summary", help="Summarize local memory for a day/week/recent period")
    memory_summary.add_argument("--period", choices=sorted(SUMMARY_PERIODS), default="today")
    memory_summary.add_argument("--query", default="")
    memory_summary.add_argument("--workspace", type=Path, default=Path.cwd())
    memory_summary.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    memory_summary.add_argument("--limit", type=int, default=100)
    memory_summary.add_argument("--json", action="store_true")

    memory_profile = subparsers.add_parser("memory-profile", help="Show explicit user profile memories")
    memory_profile.add_argument("--workspace", type=Path, default=Path.cwd())
    memory_profile.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    memory_profile.add_argument("--limit", type=int, default=100)
    memory_profile.add_argument("--json", action="store_true")

    screen_captures = subparsers.add_parser("screen-captures", help="List local screenshot capture metadata")
    screen_captures.add_argument("--workspace", type=Path, default=Path.cwd())
    screen_captures.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    screen_captures.add_argument("--limit", type=int, default=10)
    screen_captures.add_argument("--json", action="store_true")

    benchmark = subparsers.add_parser("benchmark", help="Run local performance benchmarks")
    benchmark.add_argument("--workspace", type=Path, default=Path.cwd())
    benchmark.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    benchmark.add_argument("--iterations", type=int, default=3)
    benchmark.add_argument("--query", default="project")
    benchmark.add_argument("--json", action="store_true")

    index = subparsers.add_parser("index", help="Manage the local file index")
    index.add_argument("--workspace", type=Path, default=Path.cwd())
    index.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    index.add_argument("--rebuild", action="store_true", help="Rebuild the file index")
    index.add_argument("--json", action="store_true")

    autonomous_status_parser = subparsers.add_parser("autonomous-status", help="Inspect autonomous queued events, ready tasks, wakeups, and recent cycles")
    autonomous_status_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    autonomous_status_parser.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    autonomous_status_parser.add_argument("--limit", type=int, default=10)
    autonomous_status_parser.add_argument("--json", action="store_true")

    autonomous_loop = subparsers.add_parser("autonomous-loop", help="Run a bounded autonomous loop over queued events, due wakeups, and ready tasks")
    autonomous_loop.add_argument("--workspace", type=Path, default=Path.cwd())
    autonomous_loop.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    autonomous_loop.add_argument("--max-cycles", type=int, default=10)
    autonomous_loop.add_argument("--idle-sleep-seconds", type=float, default=0.0)
    autonomous_loop.add_argument("--stop-after-idle-cycles", type=int, default=1)
    autonomous_loop.add_argument("--approve-high-risk", action="store_true")
    autonomous_loop.add_argument("--allow-initiative", action="store_true", help="Allow an idle model-led priority review to queue one next action")
    autonomous_loop.add_argument("--json", action="store_true")
    _add_planner_args(autonomous_loop)

    daemon_status = subparsers.add_parser("automation-daemon-status", help="Inspect the persisted automation daemon profile and autonomous queue")
    daemon_status.add_argument("--workspace", type=Path, default=Path.cwd())
    daemon_status.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    daemon_status.add_argument("--limit", type=int, default=10)
    daemon_status.add_argument("--json", action="store_true")

    daemon_configure = subparsers.add_parser("automation-daemon-configure", help="Persist a bounded automation daemon profile")
    daemon_configure.add_argument("--workspace", type=Path, default=Path.cwd())
    daemon_configure.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    daemon_configure.add_argument("--enabled", action="store_true")
    daemon_configure.add_argument("--poll-seconds", type=float, default=5.0)
    daemon_configure.add_argument("--max-cycles-per-tick", type=int, default=3)
    daemon_configure.add_argument("--stop-after-idle-cycles", type=int, default=1)
    daemon_configure.add_argument("--allow-initiative", action="store_true")
    daemon_configure.add_argument("--approve-high-risk", action="store_true")
    daemon_configure.add_argument("--response-mode", default="silent", choices=["silent", "text", "voice_prepare", "voice_speak"])
    daemon_configure.add_argument("--note", default="")
    daemon_configure.add_argument("--json", action="store_true")

    daemon_tick = subparsers.add_parser("automation-daemon-tick", help="Run one bounded automation daemon tick")
    daemon_tick.add_argument("--workspace", type=Path, default=Path.cwd())
    daemon_tick.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    daemon_tick.add_argument("--max-cycles-per-tick", type=int)
    daemon_tick.add_argument("--stop-after-idle-cycles", type=int)
    daemon_tick.add_argument("--allow-initiative", action="store_true")
    daemon_tick.add_argument("--approve-high-risk", action="store_true")
    daemon_tick.add_argument("--json", action="store_true")
    _add_planner_args(daemon_tick)

    collector_status_parser = subparsers.add_parser("collectors-status", help="Inspect continuous local stimulus collector profile and recent events")
    collector_status_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    collector_status_parser.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    collector_status_parser.add_argument("--limit", type=int, default=10)
    collector_status_parser.add_argument("--json", action="store_true")

    collector_configure = subparsers.add_parser("collectors-configure", help="Persist continuous local stimulus collector settings")
    collector_configure.add_argument("--workspace", type=Path, default=Path.cwd())
    collector_configure.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    collector_configure.add_argument("--enabled", action="store_true")
    collector_configure.add_argument("--disabled", action="store_true")
    collector_configure.add_argument("--privacy-mode", choices=("privacy_first",))
    collector_configure.add_argument("--poll-seconds", type=float)
    collector_configure.add_argument("--dwell-seconds", type=float)
    collector_configure.add_argument("--batch-seconds", type=float)
    collector_configure.add_argument("--llm-attention-interval-seconds", type=float)
    collector_configure.add_argument("--response-mode", choices=("silent", "text", "voice_prepare", "voice_speak"))
    collector_configure.add_argument("--no-submit-to-harness", action="store_true")
    collector_configure.add_argument("--run-autonomous-cycle", action="store_true")
    collector_configure.add_argument("--max-events-per-tick", type=int)
    collector_configure.add_argument("--collector-rate-limit", action="append", default=[], help="Per-minute budget as collector=limit")
    collector_configure.add_argument("--rich-capture-opt-in", action="append", default=[], help="Opt in a rich collector such as clipboard, screen_ocr, screenshot, video_frame, or audio_activity")
    collector_configure.add_argument("--rich-capture-opt-out", action="append", default=[])
    collector_configure.add_argument("--watch-path", action="append", default=[])
    collector_configure.add_argument("--enable-collector", action="append", default=[])
    collector_configure.add_argument("--disable-collector", action="append", default=[])
    collector_configure.add_argument("--note", default="")
    collector_configure.add_argument("--json", action="store_true")

    collector_tick = subparsers.add_parser("collectors-tick", help="Run one continuous stimulus collector tick")
    collector_tick.add_argument("--workspace", type=Path, default=Path.cwd())
    collector_tick.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    collector_tick.add_argument("--force", action="store_true")
    collector_tick.add_argument("--dry-run", action="store_true")
    collector_tick.add_argument("--json", action="store_true")
    _add_planner_args(collector_tick)

    collector_loop = subparsers.add_parser("collectors-loop", help="Run repeated local stimulus collector ticks")
    collector_loop.add_argument("--workspace", type=Path, default=Path.cwd())
    collector_loop.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    collector_loop.add_argument("--max-ticks", type=int, default=0)
    collector_loop.add_argument("--force", action="store_true")
    collector_loop.add_argument("--json", action="store_true")
    _add_planner_args(collector_loop)

    events_status = subparsers.add_parser("events-status", help="Inspect semantic events, current context, and autonomous action candidates")
    events_status.add_argument("--workspace", type=Path, default=Path.cwd())
    events_status.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    events_status.add_argument("--limit", type=int, default=20)
    events_status.add_argument("--json", action="store_true")

    events_rebuild = subparsers.add_parser("events-rebuild-context", help="Regenerate current_context.md and events.md from local semantic events")
    events_rebuild.add_argument("--workspace", type=Path, default=Path.cwd())
    events_rebuild.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    events_rebuild.add_argument("--limit", type=int, default=40)
    events_rebuild.add_argument("--json", action="store_true")

    multi_agent_board = subparsers.add_parser("multi-agent-board", help="Inspect specialist coordination board")
    multi_agent_board.add_argument("--workspace", type=Path, default=Path.cwd())
    multi_agent_board.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    multi_agent_board.add_argument("--limit", type=int, default=20)
    multi_agent_board.add_argument("--json", action="store_true")

    skill_forge_packs = subparsers.add_parser("skill-forge-packs", help="List forged SKILL.md packs")
    skill_forge_packs.add_argument("--workspace", type=Path, default=Path.cwd())
    skill_forge_packs.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    skill_forge_packs.add_argument("--limit", type=int, default=20)
    skill_forge_packs.add_argument("--json", action="store_true")

    approvals = subparsers.add_parser("approvals", help="List approval queue items")
    approvals.add_argument("--workspace", type=Path, default=Path.cwd())
    approvals.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    approvals.add_argument("--status", default="pending", help="Filter by status, or 'all'")
    approvals.add_argument("--limit", type=int, default=20)

    approve = subparsers.add_parser("approve", help="Approve and execute one pending approval token")
    approve.add_argument("approval_token")
    approve.add_argument("--workspace", type=Path, default=Path.cwd())
    approve.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    approve.add_argument("--note", default="approved from CLI")
    approve.add_argument("--json", action="store_true")

    reject = subparsers.add_parser("reject", help="Reject one pending approval token")
    reject.add_argument("approval_token")
    reject.add_argument("--workspace", type=Path, default=Path.cwd())
    reject.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    reject.add_argument("--note", default="rejected from CLI")

    edit_approval = subparsers.add_parser("approval-edit", help="Edit one pending approval tool_input JSON")
    edit_approval.add_argument("approval_token")
    edit_approval.add_argument("tool_input_json", help="Replacement tool_input object as JSON")
    edit_approval.add_argument("--workspace", type=Path, default=Path.cwd())
    edit_approval.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    edit_approval.add_argument("--note", default="edited from CLI")
    edit_approval.add_argument("--json", action="store_true")

    serve = subparsers.add_parser("serve", help="Run the local Humungousaur HTTP API daemon")
    serve.add_argument("--workspace", type=Path, default=Path.cwd())
    serve.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    _add_planner_args(serve)

    client_protocol = subparsers.add_parser("client-protocol-stdio", help="Run the native JSONL client protocol over stdio")
    client_protocol.add_argument("--workspace", type=Path, default=Path.cwd())
    client_protocol.add_argument("--data-dir", type=Path, default=Path("artifacts"))
    _add_planner_args(client_protocol)

    return parser


def main() -> None:
    _configure_console_output()
    parser = build_parser()
    args = parser.parse_args()
    load_workspace_environment(args.workspace)

    config = AgentConfig(
        workspace=args.workspace,
        data_dir=args.data_dir,
        dry_run=getattr(args, "dry_run", False),
        planner_provider=getattr(args, "planner", "model"),
        model_provider=getattr(args, "model_provider", "auto"),
        model_name=getattr(args, "model", "gpt-5-mini"),
        model_base_url=getattr(args, "model_base_url", None),
        model_api_key_env=getattr(args, "model_api_key_env", None),
        model_timeout_seconds=getattr(args, "model_timeout_seconds", 45.0),
    ).normalized()

    if args.command == "run":
        result = AgentOrchestrator(config).run(args.request, approve_high_risk=args.approve_high_risk)
        if args.json:
            print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        else:
            print(result.final_response)
            if result.note_path:
                print(f"\nSaved note: {result.note_path}")
            print(f"Run ID: {result.run_id}")
        return

    if args.command == "audit":
        audit_log = AuditLog(config.audit_db_path)
        print(json.dumps(audit_log.recent_runs(limit=args.limit), indent=2, ensure_ascii=False))
        return

    if args.command == "plans":
        audit_log = AuditLog(config.audit_db_path)
        payload = audit_log.get_plan_trace(args.run_id) if args.run_id else audit_log.recent_plan_traces(limit=args.limit)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if args.command == "run-activation":
        if args.harness:
            result = handle_activation(
                args.activation_json,
                config,
                response_mode=args.response_mode,
                approve_high_risk=args.approve_high_risk,
                stt_provider=args.stt_provider,
                tts_provider=args.tts_provider,
                voice_id=args.voice_id,
                tts_model=args.tts_model,
            )
            if args.json:
                print(json.dumps(harness_result_to_dict(result), indent=2, ensure_ascii=False))
            else:
                print(result.run.final_response if result.run is not None else result.decision.reason)
                if result.voice_result:
                    print(f"\nVoice response: {result.voice_result.get('response_id', 'prepared')}")
                if result.run is not None:
                    print(f"Run ID: {result.run.run_id}")
            return
        result = run_activation(args.activation_json, config)
        if args.json:
            print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        else:
            print(result.final_response)
            if result.note_path:
                print(f"\nSaved note: {result.note_path}")
            print(f"Run ID: {result.run_id}")
        return

    if args.command == "stimulus":
        result = InteractionHarness(config).handle(
            {
                "text": args.text,
                "source": args.source,
                "metadata": {
                    "tts_provider": args.tts_provider,
                    "voice_id": args.voice_id,
                    "tts_model": args.tts_model,
                    "allow_voice_lookup": args.allow_voice_lookup,
                    "playback": not args.no_playback,
                },
            },
            response_mode=args.response_mode,
            approve_high_risk=args.approve_high_risk,
        )
        if args.json:
            print(json.dumps(harness_result_to_dict(result), indent=2, ensure_ascii=False))
        else:
            print(f"Decision: {result.decision.decision} ({result.decision.reason})")
            if result.run is not None:
                print(result.run.final_response)
                print(f"Run ID: {result.run.run_id}")
            if result.voice_result:
                print(f"Voice response: {result.voice_result.get('response_id', 'prepared')}")
        return

    if args.command == "memory":
        store = EventStore(config.memory_db_path)
        print(json.dumps(store.tail(limit=args.limit), indent=2, ensure_ascii=False))
        return

    if args.command == "memory-search":
        store = EventStore(config.memory_db_path)
        print(json.dumps(store.search(args.query, limit=args.limit), indent=2, ensure_ascii=False))
        return

    if args.command == "memory-summary":
        payload = summarize_memory(
            EventStore(config.memory_db_path),
            period=args.period,
            query=args.query,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["summary"])
        return

    if args.command == "memory-profile":
        payload = build_user_profile(EventStore(config.memory_db_path), limit=args.limit)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["summary"])
        return

    if args.command == "screen-captures":
        payload = {
            "captures": list_screenshot_captures(config, limit=args.limit),
            "image_bytes_served": False,
        }
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            captures = payload["captures"]
            print(f"Screen captures: {len(captures)} local metadata record(s).")
            for capture in captures:
                print(f"- {capture['filename']} {capture.get('created_at', '')}: {capture.get('reason', '')}")
        return

    if args.command == "benchmark":
        result = run_benchmarks(config, iterations=args.iterations, query=args.query)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            for benchmark in result["benchmarks"]:
                print(
                    f"{benchmark['name']}: avg {benchmark['avg_ms']} ms "
                    f"(min {benchmark['min_ms']} ms, max {benchmark['max_ms']} ms)"
                )
        return

    if args.command == "index":
        index = FileIndex(config.file_index_db_path)
        result = index.rebuild(config) if args.rebuild else index.status(config)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(
                f"Index {'usable' if result['usable'] else 'not usable'}: "
                f"{result['indexed_files']} files, {result['indexed_lines']} lines"
            )
        return

    if args.command == "autonomous-status":
        payload = autonomous_status(config, limit=args.limit)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                f"Autonomous status: {len(payload['queued_events'])} queued event(s), "
                f"{len(payload['ready_tasks'])} ready task(s), "
                f"{len(payload['scheduled_wakeups'])} scheduled wakeup(s), "
                f"{len(payload.get('active_triggers', []))} active trigger(s)."
            )
        return

    if args.command == "autonomous-loop":
        result = AutonomousLoopRunner(config).run(
            max_cycles=args.max_cycles,
            idle_sleep_seconds=args.idle_sleep_seconds,
            stop_after_idle_cycles=args.stop_after_idle_cycles,
            approve_high_risk=args.approve_high_risk,
            allow_initiative=args.allow_initiative,
        )
        payload = autonomous_loop_result_to_dict(result)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                f"Autonomous loop: {payload['cycle_count']} cycle(s), "
                f"stopped={payload['stopped_reason']}, idle_cycles={payload['idle_cycles']}."
            )
            for cycle in payload["cycles"]:
                print(f"- {cycle['status']}: {cycle['reason']}")
        return

    if args.command == "automation-daemon-status":
        result = AutomationDaemonStatusTool().execute({"limit": args.limit}, config)
        payload = {"status": result.status.value, "summary": result.summary, **result.output}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            profile = payload["profile"]
            autonomous = payload["autonomous"]
            print(
                f"Automation daemon: enabled={profile['enabled']}, poll={profile['poll_seconds']}s, "
                f"tick_cycles={profile['max_cycles_per_tick']}, queued={len(autonomous['queued_events'])}, "
                f"wakeups={len(autonomous['scheduled_wakeups'])}."
            )
        return

    if args.command == "automation-daemon-configure":
        result = AutomationDaemonConfigureTool().execute(
            {
                "enabled": args.enabled,
                "poll_seconds": args.poll_seconds,
                "max_cycles_per_tick": args.max_cycles_per_tick,
                "stop_after_idle_cycles": args.stop_after_idle_cycles,
                "allow_initiative": args.allow_initiative,
                "approve_high_risk": args.approve_high_risk,
                "response_mode": args.response_mode,
                "note": args.note,
            },
            config,
        )
        payload = {"status": result.status.value, "summary": result.summary, **result.output}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(result.summary)
        return

    if args.command == "automation-daemon-tick":
        tool_input = {}
        if args.max_cycles_per_tick is not None:
            tool_input["max_cycles_per_tick"] = args.max_cycles_per_tick
        if args.stop_after_idle_cycles is not None:
            tool_input["stop_after_idle_cycles"] = args.stop_after_idle_cycles
        if args.allow_initiative:
            tool_input["allow_initiative"] = True
        if args.approve_high_risk:
            tool_input["approve_high_risk"] = True
        result = AutomationDaemonTickTool().execute(tool_input, config)
        payload = {"status": result.status.value, "summary": result.summary, **result.output}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(result.summary)
            for cycle in payload.get("loop", {}).get("cycles", []):
                print(f"- {cycle['status']}: {cycle['reason']}")
        return

    if args.command == "collectors-status":
        payload = collector_status(config, limit=args.limit)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            profile = payload["profile"]
            print(
                f"Collectors: enabled={profile['enabled']}, poll={profile['poll_seconds']}s, "
                f"recent={len(payload['recent_events'])}."
            )
            for name, enabled in profile["collectors"].items():
                print(f"- {name}: {'on' if enabled else 'off'}")
        return

    if args.command == "collectors-configure":
        payload: dict[str, object] = {}
        if args.enabled:
            payload["enabled"] = True
        if args.disabled:
            payload["enabled"] = False
        if args.privacy_mode is not None:
            payload["privacy_mode"] = args.privacy_mode
        if args.poll_seconds is not None:
            payload["poll_seconds"] = args.poll_seconds
        if args.dwell_seconds is not None:
            payload["dwell_seconds"] = args.dwell_seconds
        if args.batch_seconds is not None:
            payload["batch_seconds"] = args.batch_seconds
        if args.llm_attention_interval_seconds is not None:
            payload["llm_attention_interval_seconds"] = args.llm_attention_interval_seconds
        if args.response_mode is not None:
            payload["response_mode"] = args.response_mode
        if args.no_submit_to_harness:
            payload["submit_to_harness"] = False
        if args.run_autonomous_cycle:
            payload["run_autonomous_cycle"] = True
        if args.max_events_per_tick is not None:
            payload["max_events_per_tick"] = args.max_events_per_tick
        if args.watch_path:
            payload["watch_paths"] = args.watch_path
        collectors: dict[str, bool] = {}
        for name in args.enable_collector:
            collectors[name] = True
        for name in args.disable_collector:
            collectors[name] = False
        if collectors:
            payload["collectors"] = collectors
        rich_capture_opt_in: dict[str, bool] = {}
        for name in args.rich_capture_opt_in:
            rich_capture_opt_in[name] = True
        for name in args.rich_capture_opt_out:
            rich_capture_opt_in[name] = False
        if rich_capture_opt_in:
            payload["rich_capture_opt_in"] = rich_capture_opt_in
        rate_limits: dict[str, int] = {}
        for item in args.collector_rate_limit:
            if "=" in item:
                name, value = item.split("=", 1)
                try:
                    rate_limits[name.strip()] = int(value.strip())
                except ValueError:
                    pass
        if rate_limits:
            payload["collector_rate_limits_per_minute"] = rate_limits
        if args.note:
            payload["note"] = args.note
        profile = save_collector_profile(config, payload)
        output = {"profile": asdict(profile), "status": collector_status(config)}
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(f"Collectors configured: enabled={profile.enabled}, poll={profile.poll_seconds}s.")
        return

    if args.command == "collectors-tick":
        result = run_collector_tick(config, force=args.force, dry_run=args.dry_run)
        payload = asdict(result)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                f"Collector tick: collected={len(payload['collected'])}, "
                f"submitted={len(payload['submitted'])}, skipped={len(payload['skipped'])}."
            )
        return

    if args.command == "collectors-loop":
        payload = run_collector_loop(config, max_ticks=args.max_ticks, force=args.force)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"Collector loop: {payload['tick_count']} tick(s).")
        return

    if args.command == "events-status":
        payload = semantic_events_status(config, limit=args.limit)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                f"Semantic events: {len(payload['semantic_events'])} recent, "
                f"actions={len(payload['action_candidates'])}, queued={len(payload['queued_action_events'])}."
            )
            print(f"Current context: {payload['current_context_path']}")
            print(f"Events: {payload['events_path']}")
        return

    if args.command == "events-rebuild-context":
        payload = rebuild_current_context(config, limit=args.limit)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                f"Rebuilt context with {payload['semantic_event_count']} semantic event(s) "
                f"and {payload['action_candidate_count']} action candidate(s)."
            )
            print(f"Current context: {payload['current_context_path']}")
            print(f"Events: {payload['events_path']}")
        return

    if args.command == "multi-agent-board":
        result = MultiAgentBoardTool().execute({"limit": args.limit}, config)
        payload = {"status": result.status.value, "summary": result.summary, **result.output}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(result.summary)
        return

    if args.command == "skill-forge-packs":
        result = SkillForgePacksTool().execute({"limit": args.limit}, config)
        payload = {"status": result.status.value, "summary": result.summary, **result.output}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(result.summary)
            for pack in payload["packs"]:
                print(f"- {pack['name']}: {pack['relative_path']}")
        return

    if args.command == "approvals":
        store = ApprovalStore(config.approvals_db_path)
        status = None if args.status == "all" else args.status
        print(json.dumps([approval_record_to_dict(record) for record in store.list(status=status, limit=args.limit)], indent=2, ensure_ascii=False))
        return

    if args.command == "approve":
        try:
            result = approve_pending_action(config, args.approval_token, args.note)
        except (KeyError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(result["summary"])
            if result.get("stdout"):
                print(result["stdout"])
        return

    if args.command == "reject":
        try:
            result = reject_pending_action(config, args.approval_token, args.note)
        except (KeyError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command == "approval-edit":
        try:
            tool_input = json.loads(args.tool_input_json)
            if not isinstance(tool_input, dict):
                raise ValueError("tool_input_json must decode to a JSON object.")
            result = update_pending_approval_input(config, args.approval_token, tool_input, args.note)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(result["summary"])
        return

    if args.command == "serve":
        try:
            run_api_server(config, host=args.host, port=args.port)
        except OSError as exc:
            if exc.errno in {48, 98}:
                raise SystemExit(
                    f"Humungousaur API could not bind to {args.host}:{args.port}; the address is already in use."
                ) from exc
            raise
        return

    if args.command == "client-protocol-stdio":
        run_client_protocol_stdio(config)
        return

    raise ValueError(f"Unknown command: {args.command}")


def _configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _add_planner_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--planner",
        choices=("model", "explicit"),
        default="model",
        help="Planner provider to use",
    )
    parser.add_argument(
        "--model-provider",
        choices=("auto", "openai-responses", "openai-chat", "groq", "ollama", "local-openai", "grok"),
        default="auto",
        help="Model provider used when --planner model",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-mini",
        help="Model name used when --planner model",
    )
    parser.add_argument(
        "--model-base-url",
        default=None,
        help="Override the model provider base URL",
    )
    parser.add_argument(
        "--model-api-key-env",
        default=None,
        help="Environment variable that contains the model API key",
    )
    parser.add_argument(
        "--model-timeout-seconds",
        type=float,
        default=45.0,
        help="Timeout for each model request",
    )


if __name__ == "__main__":
    main()
