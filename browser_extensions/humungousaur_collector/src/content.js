(() => {
  "use strict";

  const api = globalThis.browser || globalThis.chrome;
  const SOURCE = "humungousaur_content_collector";
  let lastSelectionBucket = "";

  if (!api || !api.runtime || !api.runtime.sendMessage) {
    return;
  }

  function send(event) {
    try {
      api.runtime.sendMessage({
        source: SOURCE,
        occurred_at: new Date().toISOString(),
        document_url: location.href,
        url: location.href,
        ...event,
      });
    } catch (_error) {
      // Restricted pages may block extension messaging.
    }
  }

  function formStats(form) {
    const elements = form && form.elements ? Array.from(form.elements) : [];
    let uploadedFileCount = 0;
    for (const element of elements) {
      if (element && element.type === "file" && element.files) {
        uploadedFileCount += element.files.length;
      }
    }
    return {
      form_field_count: elements.length,
      uploaded_file_count: uploadedFileCount,
    };
  }

  function stableElementId(element) {
    if (!element) return "";
    if (element.id) return `id:${element.id}`;
    if (element.name) return `name:${element.name}`;
    const form = element.form;
    if (form && form.id) return `form:${form.id}`;
    return element.tagName ? element.tagName.toLowerCase() : "";
  }

  document.addEventListener(
    "submit",
    (event) => {
      const form = event.target;
      send({
        event_type: "form_submitted",
        form_id: stableElementId(form),
        ...formStats(form),
        metadata: { form_values_omitted: true },
      });
    },
    true,
  );

  document.addEventListener(
    "change",
    (event) => {
      const target = event.target;
      if (!target || !target.matches || !target.matches("input, textarea, select")) return;
      if (target.type === "file") {
        send({
          event_type: "file_uploaded",
          form_id: stableElementId(target),
          uploaded_file_count: target.files ? target.files.length : 0,
          metadata: { filenames_omitted: true },
        });
        return;
      }
      send({
        event_type: "form_changed",
        form_id: stableElementId(target),
        form_field_count: target.form && target.form.elements ? target.form.elements.length : 1,
        metadata: { form_values_omitted: true },
      });
    },
    true,
  );

  document.addEventListener(
    "click",
    (event) => {
      const link = event.target && event.target.closest ? event.target.closest("a[href]") : null;
      if (!link) return;
      send({
        event_type: "link_clicked",
        target_url: link.href,
      });
    },
    true,
  );

  window.addEventListener(
    "error",
    (event) => {
      const target = event.target;
      const targetUrl = target && (target.src || target.href) ? String(target.src || target.href) : "";
      send({
        event_type: targetUrl ? "page_error" : "console_error",
        target_url: targetUrl,
        error_code: targetUrl ? "resource_error" : "script_error",
        metadata: { error_message_omitted: true, stack_omitted: true },
      });
    },
    true,
  );

  window.addEventListener("unhandledrejection", () => {
    send({
      event_type: "console_error",
      error_code: "unhandled_rejection",
      metadata: { rejection_reason_omitted: true },
    });
  });

  document.addEventListener("selectionchange", () => {
    globalThis.clearTimeout(document.__humungousaurSelectionTimer);
    document.__humungousaurSelectionTimer = globalThis.setTimeout(() => {
      const selection = globalThis.getSelection ? globalThis.getSelection() : null;
      const length = selection ? String(selection).length : 0;
      const bucket = length === 0 ? "none" : length < 32 ? "short" : length < 256 ? "medium" : "long";
      if (bucket === lastSelectionBucket) return;
      lastSelectionBucket = bucket;
      send({
        event_type: "selected_page_text_changed",
        metadata: { selected_text_omitted: true, selected_text_length_bucket: bucket },
      });
    }, 750);
  });

  document.addEventListener(
    "enterpictureinpicture",
    () => send({ event_type: "picture_in_picture_started" }),
    true,
  );
  document.addEventListener(
    "leavepictureinpicture",
    () => send({ event_type: "picture_in_picture_stopped" }),
    true,
  );

  window.addEventListener("appinstalled", () => {
    send({
      event_type: "web_app_installed",
      web_app_id: location.origin,
    });
  });

  function standaloneMode() {
    try {
      return (
        globalThis.matchMedia("(display-mode: standalone)").matches ||
        globalThis.matchMedia("(display-mode: window-controls-overlay)").matches ||
        globalThis.navigator.standalone === true
      );
    } catch (_error) {
      return false;
    }
  }

  if (standaloneMode()) {
    send({
      event_type: "web_app_opened",
      web_app_id: location.origin,
      metadata: { display_mode: "standalone" },
    });
  }

  if (navigator.serviceWorker && navigator.serviceWorker.controller) {
    send({
      event_type: "web_app_offline_ready",
      web_app_id: location.origin,
    });
  }
})();
