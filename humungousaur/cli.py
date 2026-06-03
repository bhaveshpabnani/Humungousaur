from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from humungousaur.api import run_api_server
from humungousaur.config import AgentConfig
from humungousaur.cognition.loop import AutonomousLoopRunner, autonomous_loop_result_to_dict, autonomous_status
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
    autonomous_loop.add_argument("--json", action="store_true")
    _add_planner_args(autonomous_loop)

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

    return parser


def main() -> None:
    _configure_console_output()
    parser = build_parser()
    args = parser.parse_args()

    config = AgentConfig(
        workspace=args.workspace,
        data_dir=args.data_dir,
        dry_run=getattr(args, "dry_run", False),
        planner_provider=getattr(args, "planner", "model"),
        model_provider=getattr(args, "model_provider", "auto"),
        model_name=getattr(args, "model", "gpt-5-mini"),
        model_base_url=getattr(args, "model_base_url", None),
        model_api_key_env=getattr(args, "model_api_key_env", None),
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
            {"text": args.text, "source": args.source},
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
                f"{len(payload['scheduled_wakeups'])} scheduled wakeup(s)."
            )
        return

    if args.command == "autonomous-loop":
        result = AutonomousLoopRunner(config).run(
            max_cycles=args.max_cycles,
            idle_sleep_seconds=args.idle_sleep_seconds,
            stop_after_idle_cycles=args.stop_after_idle_cycles,
            approve_high_risk=args.approve_high_risk,
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
        run_api_server(config, host=args.host, port=args.port)
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
