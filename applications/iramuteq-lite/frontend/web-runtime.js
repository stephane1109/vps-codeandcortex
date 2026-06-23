(function bootstrapWebRuntime() {
  const existingCore = window.__TAURI__?.core;
  if (existingCore && typeof existingCore.invoke === "function") {
    return;
  }

  function normaliseFilename(name, fallback) {
    const cleaned = String(name || "")
      .trim()
      .replace(/[\\/:*?"<>|]+/g, "-")
      .replace(/\s+/g, "_");
    return cleaned || fallback;
  }

  function decodeBase64ToBytes(value) {
    const binary = window.atob(String(value || ""));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  function triggerBrowserDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function callBackend(command, payload = {}) {
    const response = await fetch(`/api/tauri/${encodeURIComponent(command)}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload || {})
    });

    const contentType = response.headers.get("content-type") || "";
    const hasJson = contentType.includes("application/json");
    const responseBody = hasJson ? await response.json() : await response.text();

    if (!response.ok) {
      const detail = hasJson && responseBody && typeof responseBody === "object"
        ? responseBody.detail
        : responseBody;
      throw new Error(detail || `Erreur HTTP ${response.status}`);
    }

    return responseBody;
  }

  const browserOnlyHandlers = {
    async open_external_url(payload = {}) {
      const safeUrl = String(payload.url || "").trim();
      if (safeUrl.startsWith("https://") || safeUrl.startsWith("http://")) {
        window.open(safeUrl, "_blank", "noopener,noreferrer");
      }
      return null;
    },

    async reveal_in_file_manager() {
      return null;
    },

    async save_results_archive(payload = {}) {
      const archive = await callBackend("download_results_archive", payload);
      const filename = normaliseFilename(archive.filename, "iramuteq-resultats.zip");
      const bytes = decodeBase64ToBytes(archive.data);
      triggerBrowserDownload(
        new Blob([bytes], { type: archive.mimeType || "application/zip" }),
        filename
      );
      return {
        filename,
        savedPath: `Téléchargement navigateur : ${filename}`
      };
    },

    async save_text_export(payload = {}) {
      const filename = normaliseFilename(payload.filename, "sous-corpus.txt");
      triggerBrowserDownload(
        new Blob([String(payload.content || "")], { type: "text/plain;charset=utf-8" }),
        filename
      );
      return {
        filename,
        savedPath: `Téléchargement navigateur : ${filename}`
      };
    },

    async save_png_export(payload = {}) {
      const filename = normaliseFilename(payload.filename, "chi2-classes.png");
      const bytes = decodeBase64ToBytes(payload.data);
      triggerBrowserDownload(new Blob([bytes], { type: "image/png" }), filename);
      return {
        filename,
        savedPath: `Téléchargement navigateur : ${filename}`
      };
    },

    async save_annotation_dictionary_export(payload = {}) {
      const filename = normaliseFilename(payload.filename, "add_expression_fr.csv");
      triggerBrowserDownload(
        new Blob([String(payload.content || "")], { type: "text/csv;charset=utf-8" }),
        filename
      );
      return {
        filename,
        savedPath: `Téléchargement navigateur : ${filename}`
      };
    }
  };

  async function invoke(command, payload = {}) {
    const handler = browserOnlyHandlers[command];
    if (handler) {
      return handler(payload || {});
    }
    return callBackend(command, payload || {});
  }

  function convertFileSrc(path) {
    const safePath = String(path || "").trim();
    if (!safePath) return "";
    return `/api/local-file?path=${encodeURIComponent(safePath)}`;
  }

  window.__TAURI__ = {
    ...(window.__TAURI__ || {}),
    isWebRuntime: true,
    core: {
      ...(window.__TAURI__?.core || {}),
      invoke,
      convertFileSrc
    }
  };
})();
