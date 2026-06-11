(() => {
  "use strict";

  const api = globalThis.browser || globalThis.chrome;
  const isPromiseApi = typeof globalThis.browser !== "undefined" && globalThis.browser === api;
  const DEFAULT_ENDPOINT = "http://127.0.0.1:8765/collectors/browsers";
  const DEFAULT_HEALTH_ENDPOINT = `${DEFAULT_ENDPOINT}/health`;
  const QUEUE_KEY = "humungousaur_collector_queue_v1";
  const PROFILE_KEY = "humungousaur_profile_id_v1";
  const MAX_QUEUE_SIZE = 250;
  const FLUSH_INTERVAL_MS = 30000;
  const SOURCE_CHANNEL = "browser_extension";

  if (!api || !api.runtime) {
    return;
  }

  function manifest() {
    try {
      return api.runtime.getManifest();
    } catch (_error) {
      return {};
    }
  }

  function defaultBrowser() {
    const name = String(manifest().name || "").toLowerCase();
    if (name.includes("edge")) return "edge";
    if (name.includes("brave")) return "brave";
    if (name.includes("firefox")) return "firefox";
    if (name.includes("safari")) return "safari";
    return "chrome";
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function randomId(prefix) {
    const bytes = new Uint32Array(2);
    if (globalThis.crypto && globalThis.crypto.getRandomValues) {
      globalThis.crypto.getRandomValues(bytes);
    } else {
      bytes[0] = Math.floor(Math.random() * 0xffffffff);
      bytes[1] = Date.now();
    }
    return `${prefix}-${bytes[0].toString(16)}${bytes[1].toString(16)}`;
  }

  function runtimeLastError() {
    try {
      return api.runtime.lastError ? String(api.runtime.lastError.message || api.runtime.lastError) : "";
    } catch (_error) {
      return "";
    }
  }

  function callApi(target, method, ...args) {
    if (!target || typeof target[method] !== "function") {
      return Promise.resolve(undefined);
    }
    if (isPromiseApi) {
      try {
        return Promise.resolve(target[method](...args)).catch(() => undefined);
      } catch (_error) {
        return Promise.resolve(undefined);
      }
    }
    return new Promise((resolve) => {
      try {
        target[method](...args, (result) => {
          runtimeLastError();
          resolve(result);
        });
      } catch (_error) {
        resolve(undefined);
      }
    });
  }

  async function storageGet(defaults) {
    const result = await callApi(api.storage && api.storage.local, "get", defaults);
    return Object.assign({}, defaults, result || {});
  }

  async function storageSet(values) {
    await callApi(api.storage && api.storage.local, "set", values);
  }

  async function settings() {
    const values = await storageGet({
      browser: defaultBrowser(),
      enabled: true,
      endpoint: DEFAULT_ENDPOINT,
      healthEndpoint: DEFAULT_HEALTH_ENDPOINT,
    });
    return {
      browser: String(values.browser || defaultBrowser()).toLowerCase(),
      enabled: values.enabled !== false,
      endpoint: String(values.endpoint || DEFAULT_ENDPOINT),
      healthEndpoint: String(values.healthEndpoint || DEFAULT_HEALTH_ENDPOINT),
    };
  }

  async function profileId() {
    const values = await storageGet({ [PROFILE_KEY]: "" });
    if (values[PROFILE_KEY]) {
      return String(values[PROFILE_KEY]);
    }
    const id = randomId("profile");
    await storageSet({ [PROFILE_KEY]: id });
    return id;
  }

  function safeScalar(value) {
    if (typeof value === "boolean" || typeof value === "number") return value;
    if (value === null || value === undefined) return undefined;
    return String(value).slice(0, 160);
  }

  function cleanEvent(event) {
    const clean = {};
    const allowed = [
      "event_type",
      "source_event",
      "provider_event_id",
      "occurred_at",
      "browser",
      "source_channel",
      "extension_version",
      "browser_version",
      "tab_id",
      "window_id",
      "profile_id",
      "group_id",
      "extension_id",
      "web_app_id",
      "download_id",
      "form_id",
      "frame_id",
      "url",
      "document_url",
      "target_url",
      "referrer_url",
      "download_url",
      "incognito",
      "is_private",
      "is_pinned",
      "muted",
      "active",
      "audible",
      "window_type",
      "tab_count",
      "error_code",
      "http_status",
      "zoom_level",
      "download_state",
      "file_size_bytes",
      "uploaded_file_count",
      "form_field_count",
      "extension_permission_count",
    ];
    for (const key of allowed) {
      if (Object.prototype.hasOwnProperty.call(event, key)) {
        const value = safeScalar(event[key]);
        if (value !== undefined) clean[key] = value;
      }
    }
    if (event.metadata && typeof event.metadata === "object") {
      const metadata = {};
      for (const [key, value] of Object.entries(event.metadata)) {
        const safeValue = safeScalar(value);
        if (safeValue !== undefined) metadata[key] = safeValue;
      }
      clean.metadata = metadata;
    }
    return clean;
  }

  async function tabContext(tabId) {
    if (tabId === undefined || tabId === null || tabId < 0) return {};
    const tab = await callApi(api.tabs, "get", tabId);
    if (!tab) return { tab_id: tabId };
    return {
      tab_id: tab.id,
      window_id: tab.windowId,
      group_id: tab.groupId >= 0 ? tab.groupId : undefined,
      url: tab.url,
      document_url: tab.url,
      incognito: Boolean(tab.incognito),
      is_pinned: Boolean(tab.pinned),
      active: Boolean(tab.active),
      audible: Boolean(tab.audible),
      muted: Boolean(tab.mutedInfo && tab.mutedInfo.muted),
    };
  }

  async function baseEvent(eventType, extra) {
    const cfg = await settings();
    return cleanEvent({
      event_type: eventType,
      provider_event_id: randomId(eventType),
      occurred_at: nowIso(),
      browser: cfg.browser,
      source_channel: SOURCE_CHANNEL,
      extension_version: manifest().version || "0.1.0",
      profile_id: await profileId(),
      ...extra,
    });
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(`Humungousaur collector returned ${response.status}`);
    }
    return response;
  }

  async function enqueue(event) {
    const values = await storageGet({ [QUEUE_KEY]: [] });
    const queue = Array.isArray(values[QUEUE_KEY]) ? values[QUEUE_KEY] : [];
    queue.push(event);
    while (queue.length > MAX_QUEUE_SIZE) queue.shift();
    await storageSet({ [QUEUE_KEY]: queue });
  }

  async function emit(eventType, extra = {}) {
    const cfg = await settings();
    if (!cfg.enabled) return;
    const event = await baseEvent(eventType, extra);
    try {
      await postJson(cfg.endpoint, event);
      await flushQueue();
    } catch (_error) {
      await enqueue(event);
    }
  }

  async function flushQueue() {
    const cfg = await settings();
    if (!cfg.enabled) return;
    const values = await storageGet({ [QUEUE_KEY]: [] });
    const queue = Array.isArray(values[QUEUE_KEY]) ? values[QUEUE_KEY] : [];
    if (!queue.length) return;
    const remaining = [];
    for (const event of queue) {
      try {
        await postJson(cfg.endpoint, event);
      } catch (_error) {
        remaining.push(event);
      }
    }
    await storageSet({ [QUEUE_KEY]: remaining.slice(-MAX_QUEUE_SIZE) });
  }

  async function health(status, message, metadata = {}) {
    const cfg = await settings();
    if (!cfg.enabled) return;
    const queued = await storageGet({ [QUEUE_KEY]: [] });
    const queuedEventCount = Array.isArray(queued[QUEUE_KEY]) ? queued[QUEUE_KEY].length : 0;
    try {
      await postJson(cfg.healthEndpoint, {
        browser: cfg.browser,
        status,
        permission_state: status,
        source_channel: SOURCE_CHANNEL,
        message,
        metadata: {
          extension_version: manifest().version || "0.1.0",
          queued_event_count: queuedEventCount,
          ...metadata,
        },
      });
    } catch (_error) {
      // Health should never interrupt collection.
    }
  }

  function addListener(area, eventName, listener) {
    try {
      if (area && area[eventName] && typeof area[eventName].addListener === "function") {
        area[eventName].addListener(listener);
      }
    } catch (_error) {
      // Unsupported browser API on this engine.
    }
  }

  addListener(api.runtime, "onInstalled", (details) => {
    const reason = details && details.reason === "update" ? "extension_enabled" : "extension_installed";
    emit(reason, { extension_id: api.runtime.id, metadata: { install_reason: details && details.reason } });
    emit("profile_switched", { metadata: { profile_context_activated: true } });
    health("running", "Humungousaur browser collector installed.");
  });

  addListener(api.runtime, "onStartup", () => {
    emit("profile_switched", { metadata: { profile_context_activated: true } });
    flushQueue();
    health("running", "Humungousaur browser collector started.");
  });

  addListener(api.tabs, "onCreated", (tab) => {
    emit("tab_opened", {
      tab_id: tab.id,
      window_id: tab.windowId,
      group_id: tab.groupId >= 0 ? tab.groupId : undefined,
      url: tab.url,
      document_url: tab.url,
      incognito: Boolean(tab.incognito),
      is_pinned: Boolean(tab.pinned),
      active: Boolean(tab.active),
      audible: Boolean(tab.audible),
    });
  });

  addListener(api.tabs, "onRemoved", (tabId, removeInfo) => {
    emit("tab_closed", {
      tab_id: tabId,
      window_id: removeInfo && removeInfo.windowId,
      metadata: { window_closing: Boolean(removeInfo && removeInfo.isWindowClosing) },
    });
  });

  addListener(api.tabs, "onActivated", async (activeInfo) => {
    emit("tab_switched", await tabContext(activeInfo.tabId));
  });

  addListener(api.tabs, "onUpdated", async (tabId, changeInfo, tab) => {
    const context = {
      ...(await tabContext(tabId)),
      window_id: tab && tab.windowId,
      incognito: Boolean(tab && tab.incognito),
      is_pinned: Boolean(tab && tab.pinned),
      active: Boolean(tab && tab.active),
      audible: Boolean(tab && tab.audible),
    };
    if (changeInfo.url) {
      emit("url_changed", { ...context, url: changeInfo.url, document_url: changeInfo.url });
    }
    if (changeInfo.title) {
      emit("title_changed", context);
    }
    if (Object.prototype.hasOwnProperty.call(changeInfo, "mutedInfo")) {
      const muted = Boolean(changeInfo.mutedInfo && changeInfo.mutedInfo.muted);
      emit(muted ? "page_muted" : "page_unmuted", { ...context, muted });
    }
    if (Object.prototype.hasOwnProperty.call(changeInfo, "groupId")) {
      emit(changeInfo.groupId >= 0 ? "tab_moved_to_group" : "tab_removed_from_group", {
        ...context,
        group_id: changeInfo.groupId,
      });
    }
  });

  addListener(api.tabs, "onZoomChange", (info) => {
    emit("zoom_changed", {
      tab_id: info.tabId,
      zoom_level: info.newZoomFactor,
      metadata: { old_zoom_level: info.oldZoomFactor },
    });
  });

  addListener(api.windows, "onCreated", (window) => {
    emit(window.incognito ? "private_window_opened" : "window_opened", {
      window_id: window.id,
      incognito: Boolean(window.incognito),
      is_private: Boolean(window.incognito),
      window_type: window.type,
      tab_count: Array.isArray(window.tabs) ? window.tabs.length : undefined,
    });
  });

  addListener(api.windows, "onRemoved", (windowId) => {
    emit("window_closed", { window_id: windowId });
  });

  addListener(api.windows, "onFocusChanged", (windowId) => {
    const noneWindow = api.windows.WINDOW_ID_NONE === undefined ? -1 : api.windows.WINDOW_ID_NONE;
    if (windowId !== noneWindow) {
      emit("window_focused", { window_id: windowId });
    }
  });

  addListener(api.webNavigation, "onCommitted", (details) => {
    if (details.frameId === 0) {
      emit("navigation_committed", {
        tab_id: details.tabId,
        frame_id: details.frameId,
        url: details.url,
        document_url: details.url,
        metadata: { transition_type: details.transitionType },
      });
    }
  });

  addListener(api.webNavigation, "onHistoryStateUpdated", (details) => {
    if (details.frameId === 0) {
      emit("history_state_updated", {
        tab_id: details.tabId,
        frame_id: details.frameId,
        url: details.url,
        document_url: details.url,
      });
    }
  });

  addListener(api.webNavigation, "onErrorOccurred", (details) => {
    emit("page_error", {
      tab_id: details.tabId,
      frame_id: details.frameId,
      url: details.url,
      document_url: details.url,
      error_code: details.error,
    });
  });

  addListener(api.downloads, "onCreated", (item) => {
    emit("download_started", {
      download_id: item.id,
      download_url: item.finalUrl || item.url,
      download_state: item.state || "in_progress",
      file_size_bytes: item.totalBytes,
    });
  });

  addListener(api.downloads, "onChanged", (delta) => {
    if (delta.state && delta.state.current) {
      emit(delta.state.current === "complete" ? "download_completed" : "page_error", {
        download_id: delta.id,
        download_state: delta.state.current,
        error_code: delta.error && delta.error.current,
      });
    }
  });

  addListener(api.action || api.browserAction, "onClicked", async (tab) => {
    emit("extension_clicked", {
      ...(await tabContext(tab && tab.id)),
      extension_id: api.runtime.id,
    });
  });

  addListener(api.commands, "onCommand", async (command) => {
    const tabs = await callApi(api.tabs, "query", { active: true, currentWindow: true });
    const current = Array.isArray(tabs) && tabs.length ? await tabContext(tabs[0].id) : {};
    const mapping = {
      "reader-mode-enabled": "reader_mode_enabled",
      "reader-mode-disabled": "reader_mode_disabled",
      "find-in-page": "find_in_page",
      "zoom-changed": "zoom_changed",
      "page-muted": "page_muted",
      "page-unmuted": "page_unmuted",
      "picture-in-picture-started": "picture_in_picture_started",
      "picture-in-picture-stopped": "picture_in_picture_stopped",
      "translation-offered": "translation_offered",
      "translation-accepted": "translation_accepted",
    };
    if (mapping[command]) {
      emit(mapping[command], { ...current, metadata: { command } });
    }
  });

  addListener(api.tabGroups, "onCreated", (group) => {
    emit("tab_group_created", { group_id: group.id, window_id: group.windowId, metadata: { color: group.color } });
  });

  addListener(api.tabGroups, "onUpdated", (group) => {
    emit(group.collapsed ? "tab_group_collapsed" : "tab_group_expanded", {
      group_id: group.id,
      window_id: group.windowId,
      metadata: { color: group.color },
    });
    emit("tab_group_renamed", { group_id: group.id, window_id: group.windowId });
    emit("tab_group_color_changed", { group_id: group.id, window_id: group.windowId, metadata: { color: group.color } });
  });

  addListener(api.tabGroups, "onRemoved", (group) => {
    emit("saved_tab_group_changed", { group_id: group.id, window_id: group.windowId });
  });

  addListener(api.runtime, "onMessage", (message, sender) => {
    if (!message || message.source !== "humungousaur_content_collector" || !message.event_type) {
      return undefined;
    }
    const tab = sender && sender.tab ? sender.tab : {};
    emit(message.event_type, {
      tab_id: tab.id,
      window_id: tab.windowId,
      frame_id: sender && sender.frameId,
      url: message.url || tab.url,
      document_url: message.document_url || tab.url,
      target_url: message.target_url,
      referrer_url: message.referrer_url,
      form_id: message.form_id,
      uploaded_file_count: message.uploaded_file_count,
      form_field_count: message.form_field_count,
      error_code: message.error_code,
      http_status: message.http_status,
      web_app_id: message.web_app_id,
      metadata: message.metadata || {},
    });
    return undefined;
  });

  flushQueue();
  health("running", "Humungousaur browser collector ready.");
  globalThis.setInterval(flushQueue, FLUSH_INTERVAL_MS);
})();
