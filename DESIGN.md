# Cancaria design notes

## Intent

Cancaria should feel like a reading room and a printed report, not a generic
SaaS dashboard. The subject is a classifier that produces a four-way
distribution from one CT frame, so the interface is built around evidence:
the image, the full score table, the model record, and the limits.

The controlling sentence is the hero: **"A classifier, not a diagnosis."**
Every screen keeps that distinction visible. Scores are labelled as softmax
outputs, never as probabilities of disease. The report carries the same wording
through its narrative, limitations, and disclaimer.

## Art direction

The visual language borrows from a radiology lightbox and a printed clinical
document:

- **Petrol ink** surfaces (`#081416`) for the dark, lightbox side of the site.
- **Bone paper** (`#F1EEE5`) for the report and the explanatory sections.
- **Signal teal** (`#4FB9AE`, deep `#0B6159`) for the model's leading class,
  active states, and the footer lens. It is the only saturated colour used at
  scale.
- **Rust** (`#96482A`, bright `#DD8B63`) reserved for caveats, pending states,
  and validation errors.
- Hairline rules, tabular figures, small mono labels, and hard edges. Corners
  are square; the interface avoids pills and floating cards.
- Images are shown in dark frames with mono captions, like a lightbox plate.
  No stock photography, no glossy device mockups, no abstract AI gradients.

The landing page alternates ink and bone sections: dark opener, bone explanation,
dark workflow, bone demonstration, dark footer. The report page is a bone
document on an ink surround, with a sticky table of contents.

## Typography

| Role | Family | Use |
| --- | --- | --- |
| Display | Newsreader 300/400, italic | Hero, section titles, predicted class |
| Interface | Archivo 400/500/600 | Body, labels, buttons, navigation |
| Record | IBM Plex Mono 400/500 | IDs, metadata, scores, stage steps, captions |

All three families are self-hosted as woff2. The report PDF embeds matching TTFs
from `web/static/assets/reportfonts/` so the download and the screen share a
typographic system.

Type is fluid with `clamp()`; the hero runs from roughly 2.55rem on small screens
to 7.6rem on wide ones. Mono is used at small sizes with generous line height,
not as a decorative code font.

## Layout

- **Landing** — 12-column editorial grid, generous section pacing (`--section`),
  full-width rules, and deliberately asymmetric image plates. The opener pairs a
  large statement with a stack of real CT frames; the About section pairs an
  image plate with a model-record panel; the workflow section uses a numbered
  tab list beside a live panel; the demonstration uses a 16:8.5 poster stage.
- **Workspace** — a persistent three-step rail (`Image`, `Inference`, `Report`)
  on the left and a single stage panel on the right. The stage swaps between
  input, review, and result rather than stacking forms. Sample frames sit below
  the dropzone with neutral names.
- **Report** — a sticky contents rail and a document that reads like a printed
  record: masthead, generation metadata, result, ranked table, interpretation,
  limitations, model record, disclaimer, and footer. On narrow screens the rail
  disappears and the document becomes a single column.
- **Footer** — an oversized wordmark with a cursor-following radial lens, plus
  real section, workspace, and service links. The lens falls back to a static
  gradient when reduced motion is requested and is hidden from assistive tech.

## Components and states

- Buttons: primary bone-on-ink or ink-on-bone, outline, quiet, and small. Hover
  and `:focus-visible` change border and colour; no layout shift.
- Keys and chips: square status chips with a single dot, used for inference
  online/offline and video status.
- Notices: bordered alert blocks with a title, body, and dismiss/retry actions.
  Errors are focused when they appear (`role="alert"`, `tabindex="-1"`).
- Score bars: thin bone tracks with ink or teal fills. Scores always appear as
  text as well as bars, so colour is never the only carrier of meaning.
- Progress: a single moving acquisition line and a polite live region. The copy
  changes after 4.5 seconds to explain slower CPU inference.
- Video placeholder: a poster with a rust "Recording pending" badge, an explicit
  sentence that it is not playable, and a status row. When a real file exists the
  poster is replaced by a native-controls video with an optional captions track
  and a large play/pause target.

## Motion

Motion is restrained and functional: the hero acquisition sweep, the score-bar
fill, panel fades, and the footer lens. The custom play target fades out during
playback. `prefers-reduced-motion: reduce` disables the lens tracking, the hero
sweep, and smooth scrolling, and keeps the video from autoplaying. Transitions
are short (140–220 ms) and use two shared easing tokens.

## Accessibility

- Semantic landmarks, one `h1` per page, sequential headings, and a skip link.
- Visible `:focus-visible` rings on both ink and bone surfaces.
- Tabs implement the ARIA tabs pattern with arrow/Home/End keys and roving
  `tabindex`.
- The mobile menu traps focus, restores focus to the toggle, closes on Escape,
  and locks the page behind it.
- Form controls have labels; the visually hidden file input has an explicit
  label. Errors use `role="alert"` and retry actions are real buttons.
- Results and report sections are rendered as text, not colour-only bars. The
  report table uses scoped headers.
- Decorative SVG, the footer lens, and status dots are hidden from assistive
  technology.
- Reduced motion is respected throughout.
- An axe-core run covering WCAG 2.1 A/AA plus best practices reported no
  violations on the landing page (desktop and mobile), the workspace in empty
  and ready states, the report, the missing-report state, and the open mobile
  menu.

## Report and PDF

The report is rendered from a versioned JSON contract:

- Report ID (`CNC-XXXX-XXXX`) and UTC generation time.
- Analysis: prediction, confidence, inference time, ranked four-class scores,
  image filename/dimensions, and a same-origin image route.
- Model: architecture, checkpoint filename, input size, class list, transform,
  runtime, and the training-run validation macro-F1 with a note that it is not
  external validation.
- Narrative: provider metadata and sections of prose.
- Limitations, disclaimer, and retention copy.

The narrative provider receives a small `ReportContext` containing only model
facts — no image, filename, or patient metadata. The shipped provider is a
deterministic template; the protocol is ready for a future Gemini provider
without changing the report schema or frontend. The provider is always named in
the report so a reader can tell whether prose came from a template or a language
model.

The PDF is generated server-side with ReportLab, not by printing the browser.
It is A4, three pages for the sample results, uses the brand fonts, embeds the
analysed frame, and repeats the masthead and page number. The on-screen report
also has a print stylesheet: navigation, hero, actions, footer, and table of
contents are removed, the document becomes full-width, and section blocks avoid
page breaks. A `@media print` pass produced a clean three-page A4 document.

## Copy principles

- Say what the model did, not what the patient has.
- Always show all four scores; never show only the winner.
- Name the input and the transform.
- State the validation source and its limits in the same breath as the metric.
- Use "score", "distribution", and "label" rather than "probability",
  "diagnosis", or "finding".
- Explain errors in terms of the next action, not blame or stack traces.
- Keep the disclaimer visible at the point of interpretation and in the PDF.

## Technical notes

No build step, bundler, or Node dependency is required by the application.
Templates are server-rendered with Jinja2; behaviour is vanilla ES modules;
styles are hand-written CSS with tokens. The only runtime additions for this
interface are ReportLab (PDF) and Pillow/FastAPI pieces already used by the
existing service. Fonts and images are local. API calls are same-origin and
relative, and analysis images never leave server memory except as the report
preview requested by the browser.
