# Cancaria

Cancaria is an experimental, four-class lung CT image classifier built for
research and education. This repository adds a production-style web interface
around the existing ResNet-18 checkpoint: a landing page, a scan-analysis
workspace, a structured report, and a genuine PDF export.

It reads a single CT frame and reports the model's four softmax scores. It does
not detect, stage, or rule out disease, and it is not a medical device.

## What is in this build

- **Landing page** — a visual opener, an explanation of what the model sees, a
  four-step workflow, and a clearly labelled demonstration-video placeholder.
- **Analysis workspace** — drag-and-drop or file picker, neutral sample frames,
  client and server validation, explicit loading/error/success states, and the
  complete four-class distribution returned by the real model.
- **Report** — an on-screen document with an ID, timestamp, analysed image,
  architecture and checkpoint metadata, ranked scores, generated interpretation,
  limitations, disclaimer, and a real ReportLab PDF.
- **In-memory analysis store** — uploaded images live only in server memory for
  30 minutes (configurable). Nothing is written to disk.
- **Provider-agnostic narrative layer** — the shipped narrative is a
  deterministic template. The interface is ready for a Gemini or other LLM
  provider later, but no LLM is integrated and no image is sent anywhere.

The original `/predict` contract is preserved. Report fields are additive.

## Requirements

- Python 3.11+
- The trained checkpoint at `models/cancaria_resnet18_final.pth`
- Optional: a CUDA-capable GPU for faster inference (CPU works)
- `Data/` is only needed if you want to regenerate the static sample frames; it
  is not read by the running application

Install the dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` pins the versions used during verification. If you need a
specific CUDA build of PyTorch, install `torch` and `torchvision` from the
matching PyTorch index first, then install the rest.

## Run it

From the project root:

```powershell
.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Add `--reload` while editing server code. The
checkpoint is loaded once at import time, so restart the process after changing
backend code.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Landing page |
| `GET` | `/analyse` | Analysis workspace |
| `GET` | `/report?id=CNC-XXXX-XXXX` | Report viewer |
| `GET` | `/api` | Legacy service check (`{"message": ...}`) |
| `GET` | `/api/health` | Model, device, classes, limits, video availability |
| `GET` | `/api/config` | Public client limits and report TTL |
| `POST` | `/predict` | Multipart image classification |
| `GET` | `/api/report/{id}` | Structured report JSON |
| `GET` | `/api/report/{id}/image` | JPEG preview of the analysed frame |
| `GET` | `/api/report/{id}/pdf` | ReportLab PDF download |
| `GET` | `/static/...` | CSS, ES modules, fonts, images, optional video |

Reports are addressed by an unguessable ID such as `CNC-BRXK-2V2S`. They expire
with the in-memory record (30 minutes by default).

## Upload rules

- PNG, JPEG, or WebP
- 10 MB maximum
- At least 32 × 32 px and at most 40 megapixels
- One still frame; DICOM series and PDFs are rejected

Validation happens in the browser for fast feedback and again on the server.
Generic upload MIME types are accepted only when the filename has an allowed
image suffix, and the decoded image format is checked independently.

The sample buttons fetch the local WebP files, wrap them in a `File`, and send
them through exactly the same `/predict` path as an upload. Their labels are
neutral (`Sample 01` … `Sample 04`); no class name is shown before inference.

## Demonstration video

The landing page placeholder is intentional. To publish a recording, add:

```text
web/static/media/cancaria-demo.mp4
web/static/media/cancaria-demo.en.vtt   # optional captions
```

Reload the landing page. `/api/health` reports `demo_video` and `demo_captions`
by checking for those files, and the page mounts the video only when
`demo_video` is true. No server restart is required. If the files are removed,
the poster placeholder and its "Recording pending" label return.

The player uses native controls plus a large play/pause target that fades out
during playback. It keeps the poster available as a fallback if the video fails
to load. Replace `web/static/assets/img/demo-poster.webp` if you want a
different still.

## Narrative provider

`src/report.py` defines the `NarrativeProvider` protocol:

```python
class NarrativeProvider(Protocol):
    provider_id: str
    provider_label: str
    is_llm: bool

    def compose(self, context: ReportContext) -> list[dict[str, Any]]: ...
```

`ReportContext` contains only report ID, timestamp, prediction, confidence,
ranked scores, and model metadata. It deliberately excludes the image, filename,
and any patient or scanner data. `TemplateNarrativeProvider` is the only
implementation shipped. `CANCARIA_NARRATIVE_PROVIDER` exists as the selection
point; `get_narrative_provider()` currently falls back to the template for every
value so an unknown setting cannot break a report.

A future Gemini provider can implement `compose()` and be returned from
`get_narrative_provider()`. The report JSON, HTML, and PDF already render
whatever sections it returns, and the provider's `id`, `label`, and `is_llm`
flag appear in the report. This build makes no network calls to any language
model.

## Privacy and retention

- Images are decoded in memory, a JPEG preview is generated in memory, and both
  the record and preview are held in a thread-safe TTL cache.
- Nothing is written to disk for an analysis.
- The store holds at most 48 records; the oldest expire first.
- Default TTL is 30 minutes. Set `CANCARIA_ANALYSIS_TTL_SECONDS` to change it.
  The client reads the effective value from `/api/config`.
- Only `/static` is mounted; `Data/`, `models/`, and `reports/` are not exposed.
- The browser talks to the same origin with relative URLs. There is no external
  AI provider call in the request path.

## Project layout

```text
api/main.py              FastAPI app, routes, validation, MIME types
src/predict.py           Existing ResNet-18 inference + MODEL_INFO
src/analysis_store.py    TTL, in-memory analysis records
src/report.py            Report payload, narrative protocol, PDF renderer
web/templates/           Jinja2 pages and shared nav/footer partials
web/static/css/          Design tokens, landing, workspace, report, print CSS
web/static/js/           ES modules for nav, video, workspace, report
web/static/assets/       Fonts, UI/report TTFs, dataset frames, poster
models/                  Checkpoint (not served, not committed)
Data/                    Source dataset (not served, not committed)
reports/                 Pre-existing training reports (not served)
```

The report PDF embeds the brand fonts from
`web/static/assets/reportfonts/`, generated from the same woff2 families used by
the site.

## Verification performed

The interface was exercised against the real checkpoint, not mocked responses:

- Sample 01 → Normal 92.53% (`CNC-BRXK-2V2S`)
- Sample 02 → Squamous Cell Carcinoma 56.54% (`CNC-QX4T-C75B`)
- Sample 03 → Adenocarcinoma 36.78% (`CNC-79E5-C5C6`)
- Sample 04 → Squamous Cell Carcinoma 50.32%
- PDF download produced a valid 3-page document; print-to-PDF also completed
- Server validation returned the expected 400/413/415/404 responses for tiny,
  fake, oversized, wrong-MIME, and missing-report requests
- Playwright runs reported no console or page errors; the in-page axe-core audit
  reported no WCAG 2.1 A/AA or best-practice violations on the landing page,
  workspace states, report, and mobile menu
- Keyboard navigation, the mobile menu focus trap/Escape handling, copy-report-ID,
  and the print stylesheet were tested

These checks describe the interface, not clinical validity. The checkpoint was
trained on the project's own split and has not been externally validated.

## Limitations

- One 224 × 224 centre crop of one frame is the only input. Lesion size,
  location, and multi-slice context are not modelled.
- The four classes are fixed by the checkpoint.
- Softmax scores are not calibrated disease probabilities and have no clinical
  decision threshold.
- There is no segmentation, staging, risk prediction, or treatment guidance.
- DICOM series, scanner metadata, and patient history are not read.

**This output comes from an experimental image classifier. It is not a
diagnosis, a clinical opinion, or a substitute for review by a qualified
clinician. Do not use it to guide screening, treatment, or any decision about a
person's health.**

## License

See `LICENSE`.
