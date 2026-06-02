const state = {
  lastRunId: null,
  timelineTimer: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function escapeText(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function setItems(containerId, items, render, emptyText) {
  const container = $(containerId);
  if (!items.length) {
    container.innerHTML = `<div class="item meta">${emptyText}</div>`;
    return;
  }
  container.innerHTML = items.map(render).join("");
}

async function refreshAll() {
  const [health, runs, approvals, plans, memory, memorySummary, memoryProfile, permissions, browserSessions, screenCaptures] = await Promise.all([
    api("/health"),
    api("/runs?limit=6"),
    api("/approvals?limit=8"),
    api("/plans?limit=6"),
    api("/memory?limit=6"),
    api("/memory/summary?period=today&limit=100"),
    api("/memory/profile?limit=100"),
    api("/permissions"),
    api("/browser/sessions?limit=6"),
    api("/screen/captures?limit=6"),
  ]);
  const systemState = health.system ? health.system.overall_status : "unknown";
  $("health").textContent = `Runtime ready - ${health.workspace} - ${systemState}`;
  $("runCount").textContent = runs.length;
  $("approvalCount").textContent = approvals.length;
  $("planCount").textContent = plans.length;
  $("browserCount").textContent = browserSessions.length;
  $("screenCaptureCount").textContent = screenCaptures.captures.length;
  $("permissionCount").textContent = permissions.tools.length;
  setItems("runs", runs, renderRun, "No runs yet.");
  setItems("approvals", approvals, renderApproval, "No pending approvals.");
  setItems("plans", plans, renderPlan, "No plan traces yet.");
  setItems("memory", memory, renderMemory, "No memory events yet.");
  renderMemorySummary(memorySummary);
  renderMemoryProfile(memoryProfile);
  setItems("browserSessions", browserSessions, renderBrowserSession, "No browser sessions yet.");
  setItems("screenCaptures", screenCaptures.captures, renderScreenCapture, "No approved screenshot captures yet.");
  renderPermissions(permissions);
  renderSystemStatus(health.system);
  if (state.lastRunId) {
    await refreshTimeline(state.lastRunId);
  }
}

function renderSystemStatus(system) {
  if (!system) {
    return;
  }
  const warnings = system.warnings || [];
  const text = [
    `Status: ${system.overall_status}`,
    `Workspace: ${system.workspace}`,
    `Data: ${system.data_dir}`,
    ...(system.storage || []).map((item) => `${item.label}: ${item.status} - ${item.free_bytes} bytes free (${item.free_percent}%)`),
  ].join("\n");
  if (!warnings.length && system.overall_status === "ok") {
    return;
  }
  $("responseBox").textContent = `${text}${warnings.length ? `\n\n${warnings.join("\n")}` : ""}`;
}

function renderRun(run) {
  return `
    <div class="item">
      <div class="itemTitle">${escapeText(run.request)}</div>
      <div class="meta">${escapeText(run.status)} - ${escapeText(run.started_at || "")}</div>
      <pre>${escapeText(run.final_response || "")}</pre>
    </div>
  `;
}

function renderApproval(approval) {
  const preview = renderApprovalPreview(approval);
  return `
    <div class="item">
      <div class="itemTitle">${escapeText(approval.tool_name)} <span class="warning">${escapeText(approval.risk_level)}</span></div>
      <div class="meta">${escapeText(approval.request)}</div>
      ${preview}
      <pre>${escapeText(JSON.stringify(approval.tool_input, null, 2))}</pre>
      <div class="actions">
        <button class="secondary" data-edit-approval="${escapeText(approval.approval_token)}">Edit JSON</button>
        <button data-approve="${escapeText(approval.approval_token)}">Approve</button>
        <button class="danger" data-reject="${escapeText(approval.approval_token)}">Reject</button>
      </div>
    </div>
  `;
}

function renderApprovalPreview(approval) {
  if (approval.tool_name !== "browser_submit_form") {
    return "";
  }
  const input = approval.tool_input || {};
  return `
    <div class="notice">
      Submit browser form ${escapeText(input.form_index ?? 0)} in session ${escapeText(input.session_id || "")}.
      Review the Browser panel before approving.
    </div>
  `;
}

function renderPlan(plan) {
  const stepText = (plan.steps || []).map((step) => `${step.tool_name}: ${step.reason}`).join("\n");
  return `
    <div class="item">
      <div class="itemTitle">${escapeText(plan.used_provider)}${plan.fallback_used ? " - fallback" : ""}</div>
      <div class="meta">${escapeText(plan.run_id)} - ${escapeText(plan.duration_ms)} ms</div>
      <pre>${escapeText(stepText || plan.error || "")}</pre>
    </div>
  `;
}

function renderMemory(event) {
  return `
    <div class="item">
      <div class="itemTitle">${escapeText(event.event_type)}</div>
      <div class="meta">${escapeText(event.created_at)}</div>
      <pre>${escapeText(JSON.stringify(event.payload, null, 2))}</pre>
    </div>
  `;
}

function renderMemorySummary(summary) {
  $("memorySummary").textContent = summary.summary || "No memory recap yet.";
}

function renderMemoryProfile(profile) {
  $("memoryProfile").textContent = profile.summary || "No profile memories yet.";
}

function renderTimelineEvent(event) {
  return `
    <div class="item">
      <div class="itemTitle">${escapeText(event.event_type)}</div>
      <div class="meta">${escapeText(event.created_at)}</div>
      <div>${escapeText(event.message)}</div>
      <pre>${escapeText(JSON.stringify(event.payload, null, 2))}</pre>
    </div>
  `;
}

function renderBrowserSession(session) {
  const links = (session.links || []).slice(0, 8).map((link) => {
    const label = link.text || link.href;
    return `[${link.index}] ${label} -> ${link.href}`;
  }).join("\n");
  const forms = (session.forms || []).map((form) => {
    const fields = (form.fields || []).join(", ") || "none";
    const draft = form.draft && Object.keys(form.draft).length
      ? JSON.stringify(form.draft, null, 2)
      : "none";
    return `Form ${form.index} ${String(form.method || "get").toUpperCase()} ${form.action || session.current_url}\nFields: ${fields}\nDraft: ${draft}`;
  }).join("\n\n");
  const commandHints = [
    `open browser ${session.current_url}`,
    links ? `click link 0 in session ${session.session_id}` : "",
    session.can_go_back ? `go back in browser session ${session.session_id}` : "",
    forms ? `fill form 0 in session ${session.session_id} field=value` : "",
    forms ? `submit form 0 in session ${session.session_id}` : "",
  ].filter(Boolean).join("\n");
  const forgetCommand = `Forget browser session ${session.session_id} because I no longer need this local page state.`;
  return `
    <div class="item">
      <div class="itemTitle">${escapeText(session.title || "Untitled page")}</div>
      <div class="meta">${escapeText(session.current_url)} - ${escapeText(session.updated_at || "")}</div>
      <pre>${escapeText(session.summary || "")}</pre>
      ${links ? `<pre>${escapeText(links)}</pre>` : ""}
      ${forms ? `<pre>${escapeText(forms)}</pre>` : ""}
      <div class="actions">
        <button data-copy-command="${escapeText(commandHints)}">Use commands</button>
        <button class="danger" data-copy-command="${escapeText(forgetCommand)}">Forget</button>
      </div>
    </div>
  `;
}

function renderScreenCapture(capture) {
  return `
    <div class="item">
      <div class="itemTitle">${escapeText(capture.filename || "Screenshot")}</div>
      <div class="meta">${escapeText(capture.created_at || "")} - ${escapeText(capture.width || "?")}x${escapeText(capture.height || "?")} - ${escapeText(capture.size_bytes || 0)} bytes</div>
      <pre>${escapeText(capture.reason || "No reason recorded.")}</pre>
      <div class="meta">Image bytes are not served by the dashboard API.</div>
    </div>
  `;
}

function renderPermissions(permissions) {
  const indexState = permissions.index
    ? (permissions.index.stale ? "stale" : (permissions.index.usable ? "usable" : "not usable"))
    : "not usable";
  const rootSummary = [
    `Workspace: ${permissions.workspace}`,
    `Data: ${permissions.data_dir}`,
    `Read: ${permissions.allowed_read_roots.join(", ")}`,
    `Extra read: ${(permissions.extra_read_roots || []).join(", ") || "none"}`,
    `Write: ${permissions.allowed_write_roots.join(", ")}`,
    `Shell: ${permissions.shell.allowed_commands.join(", ")} (${permissions.shell.timeout_seconds}s, profiles: ${permissions.shell.command_profiles.join(", ")})`,
    `Plugins: ${permissions.plugins.manifest_count} manifest(s), ${permissions.plugins.declared_tool_count} declared tool(s), ${permissions.plugins.invalid_manifest_count} invalid`,
    `Index: ${indexState} (${permissions.index ? permissions.index.indexed_files : 0} files)`,
  ].join("\n");
  const extraRoots = (permissions.extra_read_roots || []).map(renderExtraReadRoot).join("");
  const groups = (permissions.capability_groups || []).map(renderCapabilityGroup).join("");
  const tools = permissions.tools.map(renderPermissionTool).join("");
  $("permissions").innerHTML = `
    <div class="item">
      <div class="itemTitle">Scopes</div>
      <pre>${escapeText(rootSummary)}</pre>
      <div class="actions">
        <button data-rebuild-index="true">Rebuild index</button>
      </div>
    </div>
    ${extraRoots}
    ${groups}
    ${tools}
  `;
}

function renderCapabilityGroup(group) {
  return `
    <div class="item">
      <div class="itemTitle">Group: ${escapeText(group.name)} <span class="risk ${escapeText(group.highest_risk)}">${escapeText(group.highest_risk)}</span></div>
      <div class="meta">
        ${escapeText(group.tools)} tools - ${escapeText(group.requires_approval)} approval-gated - ${escapeText(group.allowed_without_approval)} allowed directly
      </div>
    </div>
  `;
}

function renderExtraReadRoot(path) {
  return `
    <div class="item">
      <div class="itemTitle">Extra read root</div>
      <div class="meta">${escapeText(path)}</div>
      <div class="actions">
        <button class="danger" data-remove-read-root="${escapeText(path)}">Remove</button>
      </div>
    </div>
  `;
}

function renderPermissionTool(tool) {
  const state = tool.allowed_without_approval ? "allowed" : (tool.requires_approval ? "approval" : "blocked");
  const required = (tool.input_schema && tool.input_schema.required || []).join(", ") || "none";
  return `
    <div class="item">
      <div class="itemTitle">${escapeText(tool.name)} <span class="risk ${escapeText(tool.risk_level)}">${escapeText(tool.risk_level)}</span></div>
      <div class="meta">${escapeText(tool.capability_group || "core")} - ${escapeText(state)} - ${escapeText(tool.policy_reason)}</div>
      <pre>${escapeText(tool.description)}</pre>
      <div class="meta">Required input: ${escapeText(required)}</div>
    </div>
  `;
}

async function runCommand(event) {
  event.preventDefault();
  const request = $("commandInput").value.trim();
  if (!request) {
    return;
  }
  $("responseBox").textContent = "Queueing run...";
  const payload = {
    request,
    planner: $("plannerSelect").value,
    model_provider: $("modelProviderSelect").value,
    model: $("modelNameInput").value.trim() || "gpt-5-mini",
    dry_run: $("dryRunToggle").checked,
  };
  const modelBaseUrl = $("modelBaseUrlInput").value.trim();
  const modelApiKeyEnv = $("modelApiKeyEnvInput").value.trim();
  if (modelBaseUrl) {
    payload.model_base_url = modelBaseUrl;
  }
  if (modelApiKeyEnv) {
    payload.model_api_key_env = modelApiKeyEnv;
  }
  const run = await api("/runs/async", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.lastRunId = run.run_id;
  $("responseBox").textContent = `Queued run ${run.run_id}\nPlanner: ${payload.planner}\nProvider: ${payload.model_provider}\nModel: ${payload.model}\nDry run: ${payload.dry_run}`;
  setCancelAvailability(true);
  await refreshTimeline(run.run_id);
  startTimelinePolling(run.run_id);
  await refreshAll();
}

async function refreshTimeline(runId) {
  const events = await api(`/runs/${encodeURIComponent(runId)}/timeline?limit=100`);
  $("timelineCount").textContent = events.length;
  setItems("timeline", events, renderTimelineEvent, "No timeline events yet.");
  return events;
}

function startTimelinePolling(runId) {
  if (state.timelineTimer) {
    clearInterval(state.timelineTimer);
  }
  state.timelineTimer = setInterval(async () => {
    try {
      await refreshTimeline(runId);
      const run = await api(`/runs/${encodeURIComponent(runId)}`);
      if (run.status === "needs_approval") {
        clearInterval(state.timelineTimer);
        state.timelineTimer = null;
        setCancelAvailability(true);
        $("responseBox").textContent = run.final_response || "Waiting for approval.";
        await refreshAll();
        return;
      }
      if (run.finished_at) {
        clearInterval(state.timelineTimer);
        state.timelineTimer = null;
        setCancelAvailability(false);
        $("responseBox").textContent = run.final_response || JSON.stringify(run, null, 2);
        await refreshAll();
      }
    } catch (error) {
      showError(error);
    }
  }, 750);
}

async function cancelCurrentRun() {
  if (!state.lastRunId) {
    return;
  }
  setCancelAvailability(false);
  const run = await api(`/runs/${encodeURIComponent(state.lastRunId)}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason: "Cancelled from dashboard." }),
  });
  $("responseBox").textContent = run.finished_at ? (run.final_response || "Run stopped.") : "Cancellation requested.";
  await refreshTimeline(state.lastRunId);
  await refreshAll();
}

function setCancelAvailability(enabled) {
  $("cancelRunBtn").disabled = !enabled;
}

async function searchMemory(event) {
  event.preventDefault();
  const query = $("memoryQuery").value.trim();
  const memory = query ? await api(`/memory/search?q=${encodeURIComponent(query)}&limit=10`) : await api("/memory?limit=6");
  setItems("memory", memory, renderMemory, "No matching memory events.");
}

async function loadMemorySummary() {
  const period = $("memoryPeriod").value;
  const query = $("memoryQuery").value.trim();
  const summary = await api(`/memory/summary?period=${encodeURIComponent(period)}&q=${encodeURIComponent(query)}&limit=100`);
  renderMemorySummary(summary);
}

async function addReadRoot(event) {
  event.preventDefault();
  const path = $("readRootInput").value.trim();
  if (!path) {
    return;
  }
  await api("/permissions/read-roots/add", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
  $("readRootInput").value = "";
  $("responseBox").textContent = "Read root added.";
  await refreshAll();
}

async function handlePermissionClick(event) {
  if (event.target.dataset.rebuildIndex) {
    const result = await api("/index/rebuild", {
      method: "POST",
      body: JSON.stringify({}),
    });
    $("responseBox").textContent = `Indexed ${result.indexed_files} files.`;
    await refreshAll();
    return;
  }
  const path = event.target.dataset.removeReadRoot;
  if (!path) {
    return;
  }
  await api("/permissions/read-roots/remove", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
  $("responseBox").textContent = "Read root removed.";
  await refreshAll();
}

async function handleApprovalClick(event) {
  const editToken = event.target.dataset.editApproval;
  if (editToken) {
    await editApproval(editToken);
    return;
  }
  const approveToken = event.target.dataset.approve;
  const rejectToken = event.target.dataset.reject;
  if (!approveToken && !rejectToken) {
    return;
  }
  const token = approveToken || rejectToken;
  const action = approveToken ? "approve" : "reject";
  const result = await api(`/approvals/${encodeURIComponent(token)}/${action}`, {
    method: "POST",
    body: JSON.stringify({ note: `${action} from dashboard` }),
  });
  if (result.run_id) {
    state.lastRunId = result.run_id;
    await refreshTimeline(result.run_id);
  }
  $("responseBox").textContent = result.summary || JSON.stringify(result, null, 2);
  await refreshAll();
}

async function editApproval(token) {
  const approvals = await api("/approvals?status=all&limit=50");
  const approval = approvals.find((item) => item.approval_token === token);
  if (!approval) {
    throw new Error("Approval no longer exists.");
  }
  const raw = window.prompt("Edit approval tool_input JSON", JSON.stringify(approval.tool_input, null, 2));
  if (raw === null) {
    return;
  }
  let toolInput;
  try {
    toolInput = JSON.parse(raw);
  } catch (error) {
    throw new Error(`Invalid JSON: ${error.message}`);
  }
  const result = await api(`/approvals/${encodeURIComponent(token)}/edit`, {
    method: "POST",
    body: JSON.stringify({ tool_input: toolInput, note: "edited from dashboard" }),
  });
  if (result.run_id) {
    state.lastRunId = result.run_id;
    await refreshTimeline(result.run_id);
  }
  $("responseBox").textContent = result.summary || JSON.stringify(result, null, 2);
  await refreshAll();
}

function handleBrowserClick(event) {
  const command = event.target.dataset.copyCommand;
  if (!command) {
    return;
  }
  $("commandInput").value = command.split("\n").find(Boolean) || "";
  $("responseBox").textContent = command;
}

window.addEventListener("DOMContentLoaded", () => {
  $("commandForm").addEventListener("submit", (event) => runCommand(event).catch(showError));
  $("memoryForm").addEventListener("submit", (event) => searchMemory(event).catch(showError));
  $("memorySummaryBtn").addEventListener("click", () => loadMemorySummary().catch(showError));
  $("readRootForm").addEventListener("submit", (event) => addReadRoot(event).catch(showError));
  $("approvals").addEventListener("click", (event) => handleApprovalClick(event).catch(showError));
  $("browserSessions").addEventListener("click", handleBrowserClick);
  $("permissions").addEventListener("click", (event) => handlePermissionClick(event).catch(showError));
  $("cancelRunBtn").addEventListener("click", () => cancelCurrentRun().catch(showError));
  $("refreshBtn").addEventListener("click", () => refreshAll().catch(showError));
  refreshAll().catch(showError);
});

function showError(error) {
  $("responseBox").textContent = error.message || String(error);
}
