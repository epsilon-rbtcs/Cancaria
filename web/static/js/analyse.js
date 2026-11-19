/* ------------------------------------------------------------------
   Cancaria — scan analysis workspace
   ------------------------------------------------------------------ */

const ALLOWED_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const ALLOWED_EXT = new Set(["png", "jpg", "jpeg", "webp"]);
const MAX_BYTES_DEFAULT = 10 * 1024 * 1024;

const els = {
  input: document.querySelector('[data-stage="input"]'),
  ready: document.querySelector('[data-stage="ready"]'),
  result: document.querySelector('[data-stage="result"]'),
  panel: document.querySelector(".workspace-panel"),
  fileInput: document.querySelector("[data-file-input]"),
  choose: document.querySelector("[data-choose-file]"),
  dropzone: document.querySelector(".dropzone"),
  samples: Array.from(document.querySelectorAll("[data-sample]")),
  preview: document.querySelector("[data-preview]"),
  selectedFrame: document.querySelector("[data-selected-frame]"),
  selectedState: document.querySelector("[data-selected-state]"),
  source: document.querySelector("[data-source]"),
  filename: document.querySelector("[data-filename]"),
  dimensions: document.querySelector("[data-dimensions]"),
  filesize: document.querySelector("[data-filesize]"),
  filetype: document.querySelector("[data-filetype]"),
  analyse: document.querySelector("[data-analyse]"),
  clear: document.querySelector("[data-clear]"),
  replace: document.querySelector("[data-replace]"),
  progress: document.querySelector("[data-progress]"),
  progressText: document.querySelector("[data-progress-text]"),
  errorInput: document.querySelector('[data-stage="input"] [data-error]'),
  errorReady: document.querySelector("[data-error-ready]"),
  steps: Array.from(document.querySelectorAll("[data-step]")),
  resultClass: document.querySelector("[data-result-class]"),
  resultConf: document.querySelector("[data-result-conf]"),
  resultReport: Array.from(document.querySelectorAll("[data-result-report]")),
  resultTime: document.querySelector("[data-result-time]"),
  resultImage: document.querySelector("[data-result-image]"),
  resultCaption: document.querySelector("[data-result-caption]"),
  scores: document.querySelector("[data-scores]"),
  reportLink: document.querySelector("[data-report-link]"),
  pdfLink: document.querySelector("[data-pdf-link]"),
  reset: document.querySelector("[data-reset]"),
};

const state = {
  file: null,
  url: null,
  width: 0,
  height: 0,
  sourceLabel: "",
  analysing: false,
  busy: false,
  maxBytes: MAX_BYTES_DEFAULT,
  reportId: null,
  slowTimer: 0,
};

/* Helpers ------------------------------------------------------- */

const formatBytes = (bytes) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return "—";
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
};

const formatMs = (ms) => {
  const value = Number(ms);
  if (!Number.isFinite(value)) return "—";
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${Math.round(value)} ms`;
};

const revokePreview = () => {
  if (state.url) URL.revokeObjectURL(state.url);
  state.url = null;
};

function setSteps(activeName, done = []) {
  els.steps.forEach((step) => {
    const name = step.dataset.step;
    const isActive = name === activeName;
    step.classList.toggle("is-active", isActive);
    step.classList.toggle("is-done", done.includes(name) && !isActive);
    if (isActive) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  });
}

function showStage(name) {
  els.input.hidden = name !== "input";
  els.ready.hidden = name !== "ready";
  els.result.hidden = name !== "result";
}

function setSamples(selectedNumber) {
  els.samples.forEach((button) => {
    const selected = button.dataset.sample === selectedNumber;
    button.setAttribute("aria-pressed", String(selected));
    const action = button.querySelector("[data-sample-action]");
    if (action) action.textContent = selected ? "Selected" : "Select";
  });
}

/* Errors -------------------------------------------------------- */

function hideError(container) {
  if (!container) return;
  container.hidden = true;
  container.classList.remove("is-visible");
}

function activeError() {
  return els.ready && !els.ready.hidden ? els.errorReady : els.errorInput;
}

function showError(container, { title, body, retry = null }) {
  if (!container) return;
  hideError(els.errorInput);
  hideError(els.errorReady);

  const titleEl = container.querySelector("[data-error-title]");
  const bodyEl = container.querySelector("[data-error-body]");
  const retryButton = container.querySelector("[data-error-retry]");

  if (titleEl) titleEl.textContent = title;
  if (bodyEl) bodyEl.textContent = body;

  if (retryButton) {
    retryButton.hidden = typeof retry !== "function";
    retryButton.onclick = typeof retry === "function" ? retry : null;
  }

  container.hidden = false;
  window.requestAnimationFrame(() => container.focus({ preventScroll: false }));
}

document.querySelectorAll("[data-error-dismiss]").forEach((button) => {
  button.addEventListener("click", () => hideError(button.closest(".notice")));
});

/* Config -------------------------------------------------------- */

fetch("/api/config", { headers: { Accept: "application/json" }, cache: "no-store" })
  .then((response) => (response.ok ? response.json() : null))
  .then((config) => {
    if (!config) return;
    if (Number(config.max_upload_mb) > 0) {
      state.maxBytes = Number(config.max_upload_mb) * 1024 * 1024;
      document.querySelectorAll("[data-max-size]").forEach((node) => {
        node.textContent = String(config.max_upload_mb);
      });
    }
    if (Number(config.report_ttl_minutes) > 0) {
      document.querySelectorAll("[data-report-ttl]").forEach((node) => {
        node.textContent = String(config.report_ttl_minutes);
      });
    }
  })
  .catch(() => {});

/* Selecting a file --------------------------------------------- */

const GENERIC_TYPES = new Set(["", "application/octet-stream", "binary/octet-stream"]);

function acceptedType(file) {
  const type = (file.type || "").toLowerCase();
  if (ALLOWED_TYPES.has(type)) return true;
  if (!GENERIC_TYPES.has(type)) return false;
  const ext = (file.name.split(".").pop() || "").toLowerCase();
  return ALLOWED_EXT.has(ext);
}

function decodeImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      if (!image.naturalWidth || !image.naturalHeight) {
        URL.revokeObjectURL(url);
        reject(new Error("decode"));
        return;
      }
      resolve({
        url,
        width: image.naturalWidth,
        height: image.naturalHeight,
      });
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("decode"));
    };
    image.src = url;
  });
}

async function acceptFile(file, sourceLabel, sampleButton = null) {
  if (!file || state.busy || state.analysing) return;
  hideError(els.errorInput);
  hideError(els.errorReady);

  if (!acceptedType(file)) {
    showError(activeError(), {
      title: "That file type is not supported.",
      body: "Use a PNG, JPEG, or WebP image. DICOM series and PDF files are not accepted.",
    });
    return;
  }

  if (file.size > state.maxBytes) {
    showError(activeError(), {
      title: "That image is too large.",
      body: `This file is ${formatBytes(file.size)}. The limit is ${formatBytes(
        state.maxBytes
      )}. Reduce the file size and try again.`,
    });
    return;
  }

  state.busy = true;
  if (sampleButton) sampleButton.setAttribute("aria-busy", "true");

  try {
    const decoded = await decodeImage(file);
    revokePreview();

    state.file = file;
    state.url = decoded.url;
    state.width = decoded.width;
    state.height = decoded.height;
    state.sourceLabel = sourceLabel;
    state.reportId = null;

    els.preview.src = decoded.url;
    els.preview.alt = `Preview of ${sourceLabel.toLowerCase()} (${decoded.width} by ${decoded.height} pixels)`;
    els.source.textContent = sourceLabel;
    els.filename.textContent = file.name || "Selected image";
    els.dimensions.textContent = `${decoded.width} × ${decoded.height} px`;
    els.filesize.textContent = formatBytes(file.size);
    const ext = (file.name.split(".").pop() || file.type.split("/").pop() || "image").toUpperCase();
    els.filetype.textContent = ext === "JPG" ? "JPEG" : ext;
    els.selectedState.textContent = "Ready";
    els.selectedFrame.classList.remove("is-scanning");

    setSamples(sampleButton ? sampleButton.dataset.sample : null);
    setSteps("image");
    showStage("ready");
    els.errorReady.hidden = true;
    els.result.hidden = true;

    window.requestAnimationFrame(() => els.filename.focus({ preventScroll: false }));
  } catch {
    showError(activeError(), {
      title: "That image could not be read.",
      body: "The file is not a valid PNG, JPEG, or WebP image. Try another file or one of the samples.",
    });
  } finally {
    state.busy = false;
    if (sampleButton) sampleButton.removeAttribute("aria-busy");
  }
}

els.choose?.addEventListener("click", () => els.fileInput.click());

els.fileInput?.addEventListener("change", () => {
  const file = els.fileInput.files && els.fileInput.files[0];
  els.fileInput.value = "";
  if (file) acceptFile(file, "File upload");
});

els.samples.forEach((button) => {
  button.addEventListener("click", async () => {
    if (state.busy || state.analysing) return;
    const number = button.dataset.sample;
    const image = button.querySelector("img");
    if (!image) return;

    state.busy = true;
    button.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(image.src, { cache: "force-cache" });
      if (!response.ok) throw new Error("sample");
      const blob = await response.blob();
      const type = ALLOWED_TYPES.has(blob.type) ? blob.type : "image/webp";
      const file = new File([blob], `sample-${number}.webp`, { type });
      state.busy = false;
      button.removeAttribute("aria-busy");
      await acceptFile(file, `Sample ${number}`, button);
    } catch {
      showError(activeError(), {
        title: "That sample could not be loaded.",
        body: "The sample image did not arrive. Check the connection, then choose a file or try again.",
      });
    } finally {
      state.busy = false;
      button.removeAttribute("aria-busy");
    }
  });
});

/* Drag and drop ------------------------------------------------ */

if (els.dropzone) {
  listDragEvents(els.dropzone);

  els.dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    els.dropzone.classList.remove("is-dragging");
    const file = event.dataTransfer?.files?.[0];
    if (file) acceptFile(file, "File upload");
  });
}

function listDragEvents(target) {
  ["dragenter", "dragover"].forEach((type) => {
    target.addEventListener(type, (event) => {
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
      els.dropzone.classList.add("is-dragging");
    });
  });
  ["dragleave", "dragend"].forEach((type) => {
    target.addEventListener(type, () => {
      els.dropzone.classList.remove("is-dragging");
    });
  });
}

window.addEventListener("dragover", (event) => {
  if (Array.from(event.dataTransfer?.types || []).includes("Files")) {
    event.preventDefault();
  }
});

window.addEventListener("drop", (event) => {
  if (Array.from(event.dataTransfer?.types || []).includes("Files")) {
    event.preventDefault();
  }
});

/* Analysing ----------------------------------------------------- */

function setAnalysing(on) {
  state.analysing = on;
  els.ready.classList.toggle("is-analysing", on);
  els.ready.setAttribute("aria-busy", String(on));
  els.progress.hidden = !on;
  els.selectedState.textContent = on ? "Analysing" : "Ready";
  els.analyse.disabled = on;
  els.clear.disabled = on;
  els.replace.disabled = on;
  els.analyse.textContent = on ? "Analysing…" : "Analyse scan";
  if (on) {
    setSteps("inference", ["image"]);
    els.progressText.textContent =
      "Sending the frame to ResNet-18 and reading the four class scores.";
    window.clearTimeout(state.slowTimer);
    state.slowTimer = window.setTimeout(() => {
      if (state.analysing) {
        els.progressText.textContent =
          "Still working. CPU inference can take a few seconds, especially on the first run.";
      }
    }, 4500);
  } else {
    window.clearTimeout(state.slowTimer);
  }
}

function buildScoreRow(label, score, rank, isTop) {
  const li = document.createElement("li");
  li.className = `score-row${isTop ? " is-top" : ""}`;

  const rankEl = document.createElement("span");
  rankEl.className = "score-rank";
  rankEl.textContent = String(rank).padStart(2, "0");

  const name = document.createElement("span");
  name.className = "score-name";
  name.textContent = label;

  const track = document.createElement("span");
  track.className = "score-track";
  track.setAttribute("aria-hidden", "true");
  const fill = document.createElement("span");
  fill.className = "score-fill";
  track.appendChild(fill);

  const value = document.createElement("span");
  value.className = "score-value";
  value.textContent = `${Number(score).toFixed(2)}%`;

  li.append(rankEl, name, track, value);

  window.requestAnimationFrame(() => {
    fill.style.width = `${Math.max(0, Math.min(100, Number(score)))}%`;
  });

  return li;
}

function renderResult(data) {
  const confidence = Number(data.confidence);
  const reportId = data.report_id || data.analysis_id || "";

  state.reportId = reportId;

  els.resultClass.textContent = data.prediction || "Unlabelled output";
  els.resultConf.textContent = Number.isFinite(confidence)
    ? `${confidence.toFixed(2)}%`
    : "—";
  els.resultTime.textContent = formatMs(data.inference_ms);
  els.resultReport.forEach((node) => {
    node.textContent = reportId || "—";
  });

  els.resultImage.src = state.url || "";
  els.resultImage.alt = `The analysed frame: ${
    data.image?.filename || state.file?.name || "CT image"
  }`;
  els.resultCaption.textContent = `${data.image?.filename || state.file?.name || "Analysed frame"} · ${
    state.width
  } × ${state.height} px`;

  const entries = Object.entries(data.scores || {})
    .map(([label, score]) => ({ label, score: Number(score) }))
    .filter((item) => Number.isFinite(item.score))
    .sort((a, b) => b.score - a.score);

  els.scores.replaceChildren();
  entries.forEach((item, index) => {
    els.scores.appendChild(buildScoreRow(item.label, item.score, index + 1, index === 0));
  });

  if (reportId) {
    els.reportLink.href = `/report?id=${encodeURIComponent(reportId)}`;
    els.pdfLink.href = `/api/report/${encodeURIComponent(reportId)}/pdf`;
    els.pdfLink.hidden = false;
  } else {
    els.reportLink.href = "/analyse";
    els.pdfLink.hidden = true;
  }

  showStage("result");
  setSteps("report", ["image", "inference"]);
  els.ready.classList.remove("is-analysing");
  window.requestAnimationFrame(() => {
    els.resultClass.focus({ preventScroll: false });
    els.result.scrollIntoView({ block: "start", behavior: "smooth" });
  });
}

function handleAnalysisError(error) {
  if (error && error.name === "AbortError") {
    showError(els.errorReady, {
      title: "The classifier took too long.",
      body: "The request timed out. The server may be busy; try again with the same image.",
      retry: analyse,
    });
    return;
  }

  if (error && error.kind === "http") {
    const status = error.status;
    if (status === 413) {
      showError(els.errorReady, {
        title: "That image is too large for the server.",
        body: `Uploads are limited to ${formatBytes(state.maxBytes)}. Choose a smaller image.`,
      });
      return;
    }
    if (status === 415) {
      showError(els.errorReady, {
        title: "The server rejected that file type.",
        body: "Use a PNG, JPEG, or WebP image.",
      });
      return;
    }
    if (status === 400) {
      showError(els.errorReady, {
        title: "The image could not be processed.",
        body:
          typeof error.detail === "string" && error.detail.length < 180
            ? error.detail
            : "The server could not read this image. Try another file.",
      });
      return;
    }
    if (status >= 500) {
      showError(els.errorReady, {
        title: "The model did not return a result.",
        body: "Inference failed on the server. Retry, or try a different frame.",
        retry: analyse,
      });
      return;
    }
    showError(els.errorReady, {
      title: "The classifier rejected the request.",
      body: "Retry the analysis. If the problem continues, try another image.",
      retry: analyse,
    });
    return;
  }

  if (error && error.kind === "incomplete") {
    showError(els.errorReady, {
      title: "The result was incomplete.",
      body: "The server responded without a prediction or scores. Retry the analysis.",
      retry: analyse,
    });
    return;
  }

  showError(els.errorReady, {
    title: "The classifier is unreachable.",
    body: "The request did not reach the inference server. Check that the FastAPI service is running, then retry.",
    retry: analyse,
  });
}

async function analyse() {
  if (!state.file || state.analysing) return;

  hideError(els.errorReady);
  setAnalysing(true);

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 120000);

  try {
    const form = new FormData();
    form.append("file", state.file, state.file.name || "scan.png");

    const response = await fetch("/predict", {
      method: "POST",
      body: form,
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok) {
      const error = new Error("request failed");
      error.kind = "http";
      error.status = response.status;
      error.detail = payload && payload.detail;
      throw error;
    }

    if (!payload || !payload.prediction || !payload.scores) {
      const error = new Error("incomplete");
      error.kind = "incomplete";
      throw error;
    }

    renderResult(payload);
  } catch (error) {
    handleAnalysisError(error);
  } finally {
    window.clearTimeout(timeout);
    setAnalysing(false);
  }
}

els.analyse?.addEventListener("click", analyse);

/* Reset --------------------------------------------------------- */

function resetWorkspace() {
  if (state.analysing) return;
  revokePreview();
  state.file = null;
  state.width = 0;
  state.height = 0;
  state.reportId = null;
  state.sourceLabel = "";
  els.preview.removeAttribute("src");
  els.resultImage.removeAttribute("src");
  els.fileInput.value = "";
  els.scores.replaceChildren();
  hideError(els.errorInput);
  hideError(els.errorReady);
  setSamples(null);
  setSteps("image");
  showStage("input");
  els.selectedState.textContent = "Ready";
  els.progress.hidden = true;
  window.requestAnimationFrame(() => {
    els.choose.focus({ preventScroll: false });
    els.panel.scrollIntoView({ block: "start", behavior: "smooth" });
  });
}

els.reset?.addEventListener("click", resetWorkspace);
els.clear?.addEventListener("click", resetWorkspace);
els.replace?.addEventListener("click", () => els.fileInput.click());
