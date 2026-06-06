# Skill Capability Reference Matrix

This matrix records upstream capability surfaces used as design evidence while keeping Humungousaur implementations native.

## Native Boundary

- Do not import or execute Hermes Agent, OpenClaw, Anthropic Skills, ClawHub, Codex plugin, or other upstream skill repository code as Humungousaur runtime capability.
- Use upstream repositories only to identify useful capability categories, safety concerns, workflow shapes, and smoke-test ideas.
- Every runnable skill capability must be exposed through a Humungousaur-owned tool or a Humungousaur-owned `skills/<skill>/scripts/` helper.
- Scripts are discovered by `agent_skill_script_catalog`, inspected by `agent_skill_script_read`, and run only through the approval-gated `agent_skill_script_run`.

## Reference Inputs

- Hermes tools reference: `external_repos/hermes-agent/tools`, plus https://github.com/NousResearch/hermes-agent/tree/main/tools.
- Hermes plugin reference: `external_repos/hermes-agent/plugins`, plus https://github.com/NousResearch/hermes-agent/tree/main/plugins.
- OpenClaw scripts reference: `external_repos/openclaw/scripts`, plus https://github.com/openclaw/openclaw/tree/main/scripts.

## Capability Mapping

| Reference capability family | Reference examples | Humungousaur native surface | Skill/script implementation target |
| --- | --- | --- | --- |
| Shell and code execution | `terminal_tool.py`, `code_execution_tool.py`, environment helpers | `run_shell_command`, `python_interpreter`, `python_interpreter_runs` | Add scripts for repeated mechanical workflows such as repo inspection, CSV profiling, build log summarization, and readiness checks. |
| Browser and web control | `browser_tool.py`, `browser_cdp_tool.py`, browser plugins, web provider plugins | `browser_open`, `browser_observe`, `browser_live_*`, `research_web_pages` | Browser skills should bind to browser tools directly; scripts may only prepare inputs or summarize local artifacts. |
| Computer and desktop use | `computer_use/`, `computer_use_tool.py` | `os_windows`, `os_observe_ui`, `os_click_element`, `os_type_text`, `screenshot_capture` | Desktop-control skills should use observation-first OS tools and approval-gated actions, not script-driven mouse automation. |
| Files and repository work | `file_tools.py`, `file_operations.py`, `patch_parser.py`, OpenClaw QA scripts | `list_files`, `read_file`, `write_note`, `search_workspace`, `run_shell_command` | Add native scripts for repo inventory, structured manifest detection, diff summarization, and local test evidence collection. |
| Skill management | `skills_tool.py`, `skills_hub.py`, `skill_manager_tool.py`, `skills_guard.py` | `agent_skill_catalog`, `agent_skill_read`, `agent_skill_import`, `agent_skill_script_*`, `skill_forge_*` | Every important skill should declare concrete tools and add scripts when a repeatable capability is needed. |
| Tool search and large catalogs | `tool_search.py`, registry helpers | `tool_search`, `tool_describe`, `capability_surface` | Capability-discovery skills should search tool metadata and pass chosen tools to the model, not keyword-route tasks. |
| Delegation and multi-agent work | `delegate_tool.py`, `mixture_of_agents_tool.py`, OpenClaw PR/release scripts | `multi_agent_coordinate`, `multi_agent_board`, `codex_cli_plan`, `codex_cli_run` | Orchestration skills should create typed task packets and review results before acting. |
| Memory and cognition | `memory_tool.py`, context engine plugin | `memory_write`, `memory_search`, `memory_summary`, `cognitive_*`, `activity_*` | Memory skills should preserve evidence, summarize experience, curate stale memory, and never store secrets. |
| Channels and messaging | `discord_tool.py`, Feishu tools, platform plugins, OpenClaw channel scripts | `channel_catalog`, `channel_manifest`, `channel_setup_status`, `channel_message_prepare`, `channel_message_send` | Channel skills should use native channel manifests, setup checks, approval policy, loop protection, and send tools. |
| Voice and speech | `transcription_tools.py`, `tts_tool.py`, `voice_mode.py`, `neutts_synth.py` | `voice_provider_status`, `voice_transcribe`, `voice_response_prepare`, `voice_speak` | Voice skills should connect wakeup, STT, response preparation, TTS, and evidence capture through voice tools. |
| Media and vision | `vision_tools.py`, `image_generation_tool.py`, `video_generation_tool.py` | `screenshot_capture`, `read_pdf`, media-oriented tools and future native adapters | Media skills should add native scripts for local metadata extraction and use provider adapters only through Humungousaur tools. |
| Security and safety | `approval.py`, `tirith_security.py`, `threat_patterns.py`, security plugins, OpenClaw guardrail scripts | approval policy, `activity_policy`, `prompt-injection-screening`, `secrets-handling` | Security scripts may use mechanical pattern matching for redaction or validation, but not semantic task routing. |
| Observability and QA | OpenClaw `check-*`, `bench-*`, `test-*`, release scripts | `system_status`, `run_shell_command`, `capability_surface`, `workflow` tools | Add smoke scripts that summarize local test readiness, command evidence, and integration gaps in bounded JSON. |
| Providers and integrations | model provider plugins, web providers, Spotify, Google Meet, Teams | `external_integrations_status`, model clients, channel/plugin manifests | Integration skills should expose setup/status/doctor flows before action tools, and credentials must stay redacted. |

## Current Script-Backed Skill Batch

- `system-health-check/scripts/check_readiness.py`: local readiness and redacted provider-key presence facts.
- `codebase-inspection/scripts/inspect_repo.py`: repository structure, manifests, and suffix inventory.
- `skill-provenance-review/scripts/inspect_skill_pack.py`: skill folder structure, frontmatter, scripts, references, and native-boundary language.
- `secrets-handling/scripts/redact_text.py`: mechanical credential and private-key redaction.
- `data-analysis-notebook/scripts/profile_csv.py`: CSV structure, sample rows, missing counts, and numeric ranges.
- `knowledge-base-builder/scripts/build_markdown_index.py`: Markdown knowledge index with titles and link counts.

## Upgrade Order For Remaining Skills

1. Add scripts to high-repeat mechanical workflows first: code review, dependency security, local service monitoring, PDF/DOCX/XLSX operations, web data extraction, and channel setup doctors.
2. Keep interactive or high-risk behavior as model-selected platform tools: browser clicks, OS actions, channel sends, payments, and credential setup.
3. For each skill, verify catalog discovery, script discovery, a dry run or safe smoke execution, and tool-surface visibility.
