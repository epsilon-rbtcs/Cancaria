/* ------------------------------------------------------------------
   Cancaria — classification report viewer
   ------------------------------------------------------------------ */

const REPORT_PATTERN = /^CNC-[A-Z0-9]{4}-[A-Z0-9]{4}$/;

const params = new URLSearchParams(window.location.search);
const reportId = (params.get("id") || "").trim().toUpperCase();

const el = {
  loading: document.querySelector("[data-report-loading]"),
  error: document.querySelector("[data-report-error]"),
  errorKicker: document.querySelector("[data-report-error-kicker]"),
  errorTitle: document.querySelector("[data-report-error-title]"),
  errorBody: document.querySelector("[data-report-error-body]"),
  retry: document.querySelector("[data-report-retry]"),
  layout: document.querySelector("[data-report-layout]"),
  pdf: document.querySelector("[data-report-pdf]"),
  print: document.querySelector("[data-report-print]"),
  copy: document.querySelector("[data-copy-id]"),
  copyStatus: document.querySelector("[data-copy-status]"),
  ids: Array.from(document.querySelectorAll("[data-report-id], [data-doc-id]")),
  dates: Array.from(document.querySelectorAll("[data-report-date], [data-doc-date]")),
  providers: Array.from(document.querySelectorAll("[data-report-provider]")),
  ttls: Array.from(document.querySelectorAll("[data-report-ttl]")),
  docCheckpoint: document.querySelector("[data-doc-checkpoint]"),
  docRuntime: document.querySelector("[data-doc-runtime]"),
  docClass: document.querySelector("[data-doc-class]"),
  docConf: document.querySelector("[data-doc-conf]"),
  docImage: document.querySelector("[data-doc-image]"),
  docFilename: document.querySelector("[data-doc-filename]"),
  docDimensions: document.querySelector("[data-doc-dimensions]"),
  docScores: document.querySelector("[data-doc-scores]"),
  narrative: document.querySelector("[data-doc-narrative]"),
  limits: document.querySelector("[data-doc-limits]"),
  record: document.querySelector("[data-doc-record]"),
  disclaimer: document.querySelector("[data-doc-disclaimer]"),
  retention: document.querySelector("[data-doc-retention]"),
  providerFooter: document.querySelector("[data-doc-provider]"),
};

const dateFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return `${dateFormatter.format(date)} UTC`;
}

function formatMs(value) {
  const ms = Number(value);
  if (!Number.isFinite(ms) || ms < 0) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`;
}

function formatPercent(value) {
  const score = Number(value);
  return Number.isFinite(score) ? `${score.toFixed(2)}%` : "—";
}

function showError({ kicker, title, body, retry = true }) {
  if (el.loading) el.loading.hidden = true;
  if (el.layout) el.layout.hidden = true;
  if (!el.error) return;

  if (el.errorKicker) el.errorKicker.textContent = kicker;
  if (el.errorTitle) el.errorTitle.textContent = title;
  if (el.errorBody) el.errorBody.textContent = body;
  if (el.retry) el.retry.hidden = !retry;

  el.error.hidden = false;
  window.requestAnimationFrame(() => {
    el.error.focus({ preventScroll: false });
    el.error.scrollIntoView({ block: "center", behavior: "smooth" });
  });
}

function showReport() {
  if (el.loading) el.loading.hidden = true;
  if (el.error) el.error.hidden = true;
  if (el.layout) el.layout.hidden = false;
  if (el.pdf) el.pdf.hidden = false;
  if (el.print) el.print.hidden = false;
}

function textFor(key, fallback = "—") {
  const value = key === undefined || key === null ? "" : String(key);
  return value || fallback;
}

function addRecordRow(term, value) {
  if (!el.record) return;
  const row = document.createElement("div");
  const dt = document.createElement("dt");
  const dd = document.createElement("dd");
  dt.textContent = term;
  dd.textContent = value;
  row.append(dt, dd);
  el.record.appendChild(row);
}

function renderScores(scores) {
  if (!el.docScores) return;
  el.docScores.replaceChildren();

  const ranked = (Array.isArray(scores) ? scores : [])
    .map((item) => ({
      label: textFor(item && item.label, "Unlabelled class"),
      score: Number(item && item.score),
      predicted: Boolean(item && item.predicted),
    }))
    .filter((item) => Number.isFinite(item.score))
    .sort((a, b) => b.score - a.score);

  ranked.forEach((item, index) => {
    const tr = document.createElement("tr");
    if (item.predicted || index === 0) tr.classList.add("is-top");

    const rank = document.createElement("td");
    rank.className = "doc-rank";
    rank.textContent = String(index + 1).padStart(2, "0");

    const label = document.createElement("th");
    label.scope = "row";
    label.textContent = item.label;

    const barCell = document.createElement("td");
    barCell.className = "doc-bar-cell";
    const bar = document.createElement("span");
    bar.className = "doc-bar";
    bar.setAttribute("aria-hidden", "true");
    const fill = document.createElement("span");
    fill.style.setProperty("--bar", `${Math.max(0, Math.min(100, item.score))}%`);
    bar.appendChild(fill);
    barCell.appendChild(bar);

    const value = document.createElement("td");
    value.className = "doc-score";
    value.textContent = formatPercent(item.score);

    tr.append(rank, label, barCell, value);
    el.docScores.appendChild(tr);
  });

  if (!ranked.length) {
    const tr = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No class scores were returned for this report.";
    tr.appendChild(cell);
    el.docScores.appendChild(tr);
  }
}

function renderNarrative(narrative) {
  if (!el.narrative) return;
  el.narrative.replaceChildren();

  const sections = Array.isArray(narrative && narrative.sections)
    ? narrative.sections
    : [];

  sections.forEach((section) => {
    const heading = document.createElement("h3");
    heading.textContent = textFor(section.title, "Interpretation");
    el.narrative.appendChild(heading);

    const paragraphs = Array.isArray(section.paragraphs) ? section.paragraphs : [];
    paragraphs.forEach((paragraph) => {
      const p = document.createElement("p");
      p.textContent = textFor(paragraph, "");
      if (p.textContent) el.narrative.appendChild(p);
    });
  });

  if (!sections.length) {
    const p = document.createElement("p");
    p.textContent = "No narrative was supplied with this record.";
    el.narrative.appendChild(p);
  }
}

function renderLimitations(items) {
  if (!el.limits) return;
  el.limits.replaceChildren();
  (Array.isArray(items) ? items : []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = textFor(item, "");
    if (li.textContent) el.limits.appendChild(li);
  });
}

function render(report) {
  const analysis = report.analysis || {};
  const model = report.model || {};
  const narrative = report.narrative || {};
  const provider = narrative.provider || {};
  const image = analysis.image || {};
  const id = textFor(report.report_id || reportId);

  el.ids.forEach((node) => {
    node.textContent = id;
  });

  const date = formatDate(report.generated_at);
  el.dates.forEach((node) => {
    node.textContent = date;
  });

  const providerLabel = textFor(provider.label, "Deterministic template");
  const providerId = textFor(provider.id, "template");
  const providerText = `${providerLabel} (${providerId})`;
  el.providers.forEach((node) => {
    node.textContent = providerText;
  });

  if (el.docCheckpoint) el.docCheckpoint.textContent = textFor(model.checkpoint);
  if (el.docRuntime) el.docRuntime.textContent = textFor(model.runtime, "—").toUpperCase();
  if (el.docClass) el.docClass.textContent = textFor(analysis.prediction);
  if (el.docConf) el.docConf.textContent = formatPercent(analysis.confidence);

  if (el.docImage) {
    el.docImage.src = image.preview_url || "";
    el.docImage.alt = image.filename
      ? `The analysed CT frame: ${image.filename}`
      : "The CT frame that was classified";
  }
  if (el.docFilename) el.docFilename.textContent = textFor(image.filename);
  if (el.docDimensions) {
    const width = Number(image.width);
    const height = Number(image.height);
    el.docDimensions.textContent =
      Number.isFinite(width) && Number.isFinite(height)
        ? `${width} × ${height} px · inference ${formatMs(analysis.inference_ms)}`
        : "Dimensions not recorded";
  }

  renderScores(analysis.scores);
  renderNarrative(narrative);
  renderLimitations(report.limitations);

  if (el.record) {
    el.record.replaceChildren();
    addRecordRow("Architecture", textFor(model.architecture));
    addRecordRow("Checkpoint", textFor(model.checkpoint));
    addRecordRow("Input", textFor(model.input));
    addRecordRow(
      "Classes",
      Array.isArray(model.classes) && model.classes.length
        ? model.classes.join(" / ")
        : "—"
    );
    addRecordRow("Transform", textFor(model.transform));
    addRecordRow("Runtime", textFor(model.runtime, "—").toUpperCase());
    addRecordRow(
      "Validation macro-F1",
      Number.isFinite(Number(model.validation_macro_f1))
        ? `${Number(model.validation_macro_f1).toFixed(4)} (training run)`
        : "not recorded"
    );
    addRecordRow("Validation note", textFor(model.validation_note));
  }

  if (el.disclaimer) el.disclaimer.textContent = textFor(report.disclaimer);
  if (el.retention) el.retention.textContent = textFor(report.image_retention);
  if (el.providerFooter) {
    el.providerFooter.textContent = `Narrative: ${providerText}. ${
      provider.is_llm
        ? "Prose generated by a configured language model; the analysed image was not sent to it."
        : "No language model was used for this report."
    }`;
  }

  if (el.pdf && id !== "—") {
    el.pdf.href = `/api/report/${encodeURIComponent(id)}/pdf`;
    el.pdf.setAttribute("download", `cancaria-report-${id}.pdf`);
    el.pdf.hidden = false;
  }

  if (el.copy) el.copy.disabled = id === "—";

  document.title = `${textFor(analysis.prediction, "Classification")} — report — Cancaria`;
  showReport();
}

async function loadReport() {
  if (el.error) el.error.hidden = true;
  if (el.loading) el.loading.hidden = false;
  if (el.layout) el.layout.hidden = true;
  if (el.pdf) el.pdf.hidden = true;
  if (el.print) el.print.hidden = true;

  if (!reportId) {
    showError({
      kicker: "No report selected",
      title: "This page needs a report identifier.",
      body: "Open a detailed report from the analysis workspace after a classification run. Each report link includes the identifier it needs.",
      retry: false,
    });
    return;
  }

  if (!REPORT_PATTERN.test(reportId)) {
    showError({
      kicker: "Invalid identifier",
      title: "That report identifier is not valid.",
      body: `The identifier “${reportId}” does not match the Cancaria report format (CNC-XXXX-XXXX). Check the link and try again.`,
      retry: false,
    });
    return;
  }

  try {
    const response = await fetch(`/api/report/${encodeURIComponent(reportId)}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok) {
      if (response.status === 404) {
        showError({
          kicker: "Report unavailable",
          title: "That report is no longer available.",
          body:
            payload && typeof payload.detail === "string"
              ? payload.detail
              : "Reports are held in server memory for a limited time. Run the analysis again to create a new one.",
          retry: false,
        });
        return;
      }

      showError({
        kicker: "Report unavailable",
        title: "The server could not return this report.",
        body:
          payload && typeof payload.detail === "string"
            ? payload.detail
            : "Retry in a moment. If the problem continues, run a new analysis.",
        retry: true,
      });
      return;
    }

    if (!payload || !payload.analysis || !payload.report_id) {
      showError({
        kicker: "Incomplete record",
        title: "The report arrived without its analysis data.",
        body: "The server response was incomplete. Retry the request, or run a new analysis.",
        retry: true,
      });
      return;
    }

    render(payload);
  } catch {
    showError({
      kicker: "Report unreachable",
      title: "This report could not be reached.",
      body: "The request did not reach the Cancaria server. Check that the service is running, then retry.",
      retry: true,
    });
  }
}

/* Actions ------------------------------------------------------- */

el.retry?.addEventListener("click", loadReport);

el.print?.addEventListener("click", () => {
  window.print();
});

el.copy?.addEventListener("click", async () => {
  if (!reportId) return;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(reportId);
    } else {
      const area = document.createElement("textarea");
      area.value = reportId;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.top = "-1000px";
      document.body.appendChild(area);
      area.select();
      const copied = document.execCommand("copy");
      area.remove();
      if (!copied) throw new Error("copy");
    }
    if (el.copyStatus) el.copyStatus.textContent = "Copied to clipboard";
    window.setTimeout(() => {
      if (el.copyStatus) el.copyStatus.textContent = "";
    }, 3200);
  } catch {
    if (el.copyStatus) el.copyStatus.textContent = `Copy failed. Select ${reportId} manually.`;
  }
});

/* Public config, used only to keep the retention copy accurate. */

fetch("/api/config", { headers: { Accept: "application/json" }, cache: "no-store" })
  .then((response) => (response.ok ? response.json() : null))
  .then((config) => {
    const minutes = Number(config && config.report_ttl_minutes);
    if (!Number.isFinite(minutes) || minutes <= 0) return;
    el.ttls.forEach((node) => {
      node.textContent = String(minutes);
    });
  })
  .catch(() => {});

loadReport();
