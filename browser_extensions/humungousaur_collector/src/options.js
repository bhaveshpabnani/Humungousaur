(() => {
  "use strict";

  const api = globalThis.browser || globalThis.chrome;
  const DEFAULT_ENDPOINT = "http://127.0.0.1:8765/collectors/browsers";
  const DEFAULT_HEALTH_ENDPOINT = `${DEFAULT_ENDPOINT}/health`;
  const isPromiseApi = typeof globalThis.browser !== "undefined" && globalThis.browser === api;

  function callStorage(method, values) {
    if (isPromiseApi) {
      return api.storage.local[method](values);
    }
    return new Promise((resolve) => api.storage.local[method](values, resolve));
  }

  function inferredBrowser() {
    const name = String(api.runtime.getManifest().name || "").toLowerCase();
    if (name.includes("edge")) return "edge";
    if (name.includes("brave")) return "brave";
    if (name.includes("firefox")) return "firefox";
    if (name.includes("safari")) return "safari";
    return "chrome";
  }

  async function load() {
    const values = await callStorage("get", {
      browser: inferredBrowser(),
      endpoint: DEFAULT_ENDPOINT,
      healthEndpoint: DEFAULT_HEALTH_ENDPOINT,
      enabled: true,
    });
    document.querySelector("#browser").value = values.browser || inferredBrowser();
    document.querySelector("#endpoint").value = values.endpoint || DEFAULT_ENDPOINT;
    document.querySelector("#enabled").checked = values.enabled !== false;
  }

  async function save() {
    const endpoint = document.querySelector("#endpoint").value.trim() || DEFAULT_ENDPOINT;
    await callStorage("set", {
      browser: document.querySelector("#browser").value,
      endpoint,
      healthEndpoint: `${endpoint.replace(/\/$/, "")}/health`,
      enabled: document.querySelector("#enabled").checked,
    });
    document.querySelector("#status").textContent = "Saved.";
  }

  async function health() {
    const endpoint = document.querySelector("#endpoint").value.trim() || DEFAULT_ENDPOINT;
    const response = await fetch(`${endpoint.replace(/\/$/, "")}/health`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        browser: document.querySelector("#browser").value,
        status: "running",
        source_channel: "browser_extension",
        message: "Manual browser collector health check.",
        metadata: { extension_version: api.runtime.getManifest().version },
      }),
    });
    document.querySelector("#status").textContent = response.ok ? "Health check sent." : `Health failed: ${response.status}`;
  }

  document.querySelector("#save").addEventListener("click", () => save().catch((error) => {
    document.querySelector("#status").textContent = String(error && error.message ? error.message : error);
  }));
  document.querySelector("#health").addEventListener("click", () => health().catch((error) => {
    document.querySelector("#status").textContent = String(error && error.message ? error.message : error);
  }));

  load().catch((error) => {
    document.querySelector("#status").textContent = String(error && error.message ? error.message : error);
  });
})();
