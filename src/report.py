"""Structured, provider-agnostic classification reports.

The report layer deliberately keeps *model facts* separate from *narrative*.
A narrative provider receives a small, serialisable context object and returns
sections of prose. The default provider is a deterministic template; a future
LLM provider (for example Gemini) can implement the same interface without any
frontend changes and without receiving the uploaded image.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape

from src.analysis_store import AnalysisRecord
from src.predict import DISPLAY_NAMES, MODEL_INFO

DISCLAIMER = (
    "This output comes from an experimental image classifier. It is not a "
    "diagnosis, a clinical opinion, or a substitute for review by a qualified "
    "clinician. Do not use it to guide screening, treatment, or any decision "
    "about a person's health."
)

NARRATIVE_PROVIDER_ENV = "CANCARIA_NARRATIVE_PROVIDER"
CONTRACT_VERSION = "1.0"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(PROJECT_ROOT, "web", "static", "assets", "reportfonts")


@dataclass(frozen=True)
class ReportContext:
    report_id: str
    generated_at: datetime
    prediction: str
    confidence: float
    scores: tuple[tuple[str, float], ...]
    model: dict[str, Any]

    @property
    def ranked(self) -> list[tuple[str, float]]:
        return sorted(self.scores, key=lambda item: item[1], reverse=True)


class NarrativeProvider(Protocol):
    """Contract for any report narrative generator.

    Implementations receive only structured model facts. Images, filenames and
    other identifying data are intentionally excluded.
    """

    provider_id: str
    provider_label: str
    is_llm: bool

    def compose(self, context: ReportContext) -> list[dict[str, Any]]: ...


class TemplateNarrativeProvider:
    provider_id = "template"
    provider_label = "Deterministic template"
    is_llm = False

    def compose(self, context: ReportContext) -> list[dict[str, Any]]:
        ranked = context.ranked
        top_label, top_score = ranked[0]
        runner_label, runner_score = ranked[1]
        margin = max(0.0, top_score - runner_score)
        f1 = context.model.get("validation_macro_f1")

        distribution = ", ".join(
            f"{label} {score:.2f}%" for label, score in ranked
        )

        sections: list[dict[str, Any]] = [
            {
                "id": "output",
                "title": "What this output represents",
                "paragraphs": [
                    (
                        f"The model's largest softmax score was assigned to "
                        f"{context.prediction}, at {context.confidence:.2f}%. "
                        f"Across all four labels the distribution was: "
                        f"{distribution}. Because softmax normalises the four "
                        f"outputs, the scores always sum to 100%."
                    ),
                    (
                        "The score describes the shape of this four-way "
                        "distribution for one image. It is not a calibrated "
                        "probability that a person has a disease, and it has not "
                        "been validated against clinical outcomes."
                    ),
                ],
            },
            {
                "id": "reading",
                "title": "How to read the scores",
                "paragraphs": [
                    (
                        f"The runner-up label was {runner_label} at "
                        f"{runner_score:.2f}%, a margin of {margin:.2f} "
                        f"percentage points. A narrow margin means the "
                        f"classifier found the two labels comparatively close. "
                        f"A wide margin does not make the leading label "
                        f"clinically meaningful."
                    ),
                    (
                        "The predicted class is the largest value, not a "
                        "threshold-based clinical decision. No cut-off, "
                        "risk band, or action is attached to this result."
                    ),
                ],
            },
            {
                "id": "method",
                "title": "How the result was produced",
                "paragraphs": [
                    (
                        "The uploaded frame was converted to RGB, resized to "
                        "256 pixels on the short side, centre-cropped to "
                        "224 x 224, and normalised with the ImageNet mean and "
                        "standard deviation used during training. One forward "
                        "pass through the fine-tuned ResNet-18 produced four "
                        "logits, and softmax turned those logits into the "
                        "scores shown here."
                    ),
                    (
                        "Only one still frame is analysed. No patient history, "
                        "scanner metadata, neighbouring slices, or other "
                        "modality is supplied to the model."
                    ),
                ],
            },
            {
                "id": "context",
                "title": "Recorded training context",
                "paragraphs": [
                    (
                        f"The checkpoint is {context.model.get('checkpoint')}, "
                        f"a ResNet-18 fine-tuned for four labels. During "
                        f"training, the best validation macro-F1"
                        + (f" was {f1:.4f}" if isinstance(f1, (int, float)) else "")
                        + ". That figure is a measurement on the project's "
                        "validation split. It is not external validation and it "
                        "is not evidence of clinical performance."
                    )
                ],
            },
        ]
        return sections


def get_narrative_provider() -> NarrativeProvider:
    """Resolve the configured provider.

    Only the template provider ships in this phase. Unknown or future provider
    names fall back to the template so report generation never breaks; the
    returned provider is always reflected in the report payload.
    """
    requested = os.getenv(NARRATIVE_PROVIDER_ENV, "template").strip().lower()
    if requested != "template":
        # Gemini and other providers are wired later; no network calls here.
        return TemplateNarrativeProvider()
    return TemplateNarrativeProvider()


def _display_architecture(value: str) -> str:
    if value.lower() == "resnet18":
        return "ResNet-18"
    return value


def build_report(
    record: AnalysisRecord,
    provider: NarrativeProvider | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    provider = provider or get_narrative_provider()
    generated_at = generated_at or datetime.now(timezone.utc)
    raw_scores = record.result.get("scores", {})

    ordered_scores: list[dict[str, Any]] = []
    for label in DISPLAY_NAMES:
        if label in raw_scores:
            ordered_scores.append(
                {
                    "label": label,
                    "score": round(float(raw_scores[label]), 2),
                    "predicted": label == record.result["prediction"],
                }
            )

    f1 = MODEL_INFO.get("validation_macro_f1")
    model = {
        "architecture": _display_architecture(MODEL_INFO["architecture"]),
        "checkpoint": MODEL_INFO["checkpoint"],
        "input": f"{MODEL_INFO['image_size']} x {MODEL_INFO['image_size']} RGB",
        "classes": list(DISPLAY_NAMES),
        "transform": "Resize 256 / centre crop 224 / ImageNet normalisation",
        "runtime": str(MODEL_INFO.get("device", "cpu")).upper(),
        "validation_macro_f1": round(float(f1), 4) if f1 is not None else None,
        "validation_note": (
            "Best value recorded on the project validation split during "
            "training. Not external validation."
        ),
    }

    context = ReportContext(
        report_id=record.report_id,
        generated_at=generated_at,
        prediction=record.result["prediction"],
        confidence=float(record.result["confidence"]),
        scores=tuple((item["label"], item["score"]) for item in ordered_scores),
        model=model,
    )

    sections = provider.compose(context)

    return {
        "contract_version": CONTRACT_VERSION,
        "report_id": record.report_id,
        "generated_at": generated_at.isoformat(),
        "analysis": {
            "prediction": record.result["prediction"],
            "class": record.result.get("class"),
            "confidence": round(float(record.result["confidence"]), 2),
            "inference_ms": record.inference_ms,
            "scores": ordered_scores,
            "image": {
                "filename": record.filename,
                "width": record.width,
                "height": record.height,
                "preview_url": f"/api/report/{record.report_id}/image",
            },
        },
        "model": model,
        "narrative": {
            "contract_version": CONTRACT_VERSION,
            "provider": {
                "id": provider.provider_id,
                "label": provider.provider_label,
                "is_llm": provider.is_llm,
            },
            "generated_at": generated_at.isoformat(),
            "sections": sections,
        },
        "limitations": [
            "One 224 x 224 centre crop of a single frame is the only input. "
            "Lesion size, location, and multi-slice context are not modelled.",
            "The four classes are fixed by the checkpoint. Anything outside "
            "those labels cannot be expressed as an answer.",
            "Softmax scores are not calibrated disease probabilities and have "
            "no clinical decision threshold.",
            "Validation was performed on the project's own split. The "
            "checkpoint has not been externally validated.",
            "No segmentation, staging, risk prediction, or treatment guidance "
            "is implemented or implied.",
            "DICOM series, scanner metadata, and patient history are not read "
            "or sent to the model.",
        ],
        "disclaimer": DISCLAIMER,
        "image_retention": (
            "The uploaded image is held in server memory only so this report "
            "and its PDF can be generated. It is not written to disk and "
            "expires with the report."
        ),
    }


# --------------------------------------------------------------------------
# PDF rendering
# --------------------------------------------------------------------------

INK = colors.HexColor("#0A1517")
INK_SOFT = colors.HexColor("#2B3B3C")
BONE = colors.HexColor("#F4F1E8")
BONE_DEEP = colors.HexColor("#E9E3D4")
TEAL = colors.HexColor("#0C6B64")
TEAL_BRIGHT = colors.HexColor("#4FB9AE")
MUTED = colors.HexColor("#5E6C68")
RULE = colors.HexColor("#D5CFBF")
RUST = colors.HexColor("#9C4F2C")
BONE_MUTED = colors.HexColor("#A9B7B2")

_FONTS = {
    "serif": ("CancariaSerif", "newsreader-400-normal.ttf"),
    "serif-light": ("CancariaSerifLight", "newsreader-300-normal.ttf"),
    "serif-italic": ("CancariaSerifItalic", "newsreader-300-italic.ttf"),
    "sans": ("CancariaSans", "archivo-400-normal.ttf"),
    "sans-medium": ("CancariaSansMedium", "archivo-500-normal.ttf"),
    "sans-semibold": ("CancariaSansSemiBold", "archivo-600-normal.ttf"),
    "mono": ("CancariaMono", "plexmono-400-normal.ttf"),
}


def _register_fonts() -> bool:
    if "CancariaSerif" in pdfmetrics.getRegisteredFontNames():
        return True
    try:
        for name, filename in _FONTS.values():
            pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, filename)))
        return True
    except Exception:
        return False


_HAS_BRAND_FONTS = _register_fonts()


def _font(key: str, fallback: str) -> str:
    return _FONTS[key][0] if _HAS_BRAND_FONTS else fallback


SERIF = _font("serif", "Times-Roman")
SERIF_LIGHT = _font("serif-light", "Times-Roman")
SERIF_ITALIC = _font("serif-italic", "Times-Italic")
SANS = _font("sans", "Helvetica")
SANS_MEDIUM = _font("sans-medium", "Helvetica-Bold")
SANS_SEMI = _font("sans-semibold", "Helvetica-Bold")
MONO = _font("mono", "Courier")


class ScoreBars(Flowable):
    def __init__(self, scores: list[dict[str, Any]], width: float) -> None:
        super().__init__()
        self.scores = scores
        self.width = width
        self.row = 13.5 * mm
        self.height = self.row * len(scores) + 2 * mm

    def draw(self) -> None:
        canv = self.canv
        y = self.height - self.row + 2 * mm
        for item in self.scores:
            predicted = bool(item["predicted"])
            if predicted:
                canv.setFillColor(TEAL_BRIGHT)
                canv.rect(0, y + 6.6 * mm, 2.2 * mm, 2.2 * mm, fill=1, stroke=0)
            canv.setFillColor(INK if predicted else INK_SOFT)
            canv.setFont(SANS_MEDIUM if predicted else SANS, 8.6)
            canv.drawString(4.4 * mm, y + 6.2 * mm, item["label"])
            canv.setFillColor(TEAL if predicted else MUTED)
            canv.setFont(MONO, 8.6)
            canv.drawRightString(self.width, y + 6.2 * mm, f"{item['score']:.2f}%")
            canv.setFillColor(RULE)
            canv.roundRect(0, y + 1.4 * mm, self.width, 1.8 * mm, 0.9 * mm, fill=1, stroke=0)
            fill_width = max(0.8 * mm, self.width * (item["score"] / 100.0))
            canv.setFillColor(TEAL if predicted else INK_SOFT)
            canv.roundRect(0, y + 1.4 * mm, fill_width, 1.8 * mm, 0.9 * mm, fill=1, stroke=0)
            y -= self.row


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "kicker": ParagraphStyle(
            "kicker",
            fontName=MONO,
            fontSize=7.4,
            leading=10,
            textColor=TEAL,
            spaceAfter=3 * mm,
        ),
        "title": ParagraphStyle(
            "title",
            fontName=SERIF,
            fontSize=24,
            leading=27,
            textColor=INK,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=SANS,
            fontSize=9.1,
            leading=14.2,
            textColor=INK_SOFT,
            spaceAfter=2.6 * mm,
        ),
        "body_small": ParagraphStyle(
            "body_small",
            fontName=SANS,
            fontSize=8.1,
            leading=12.4,
            textColor=MUTED,
            spaceAfter=2 * mm,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName=SERIF,
            fontSize=15,
            leading=19,
            textColor=INK,
            spaceBefore=6 * mm,
            spaceAfter=2.4 * mm,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName=SANS,
            fontSize=8.6,
            leading=12.8,
            textColor=INK_SOFT,
            leftIndent=5 * mm,
            bulletIndent=0,
            spaceAfter=1.6 * mm,
        ),
        "caption": ParagraphStyle(
            "caption",
            fontName=MONO,
            fontSize=6.8,
            leading=9,
            textColor=MUTED,
        ),
        "class": ParagraphStyle(
            "class",
            fontName=SERIF,
            fontSize=26,
            leading=28,
            textColor=TEAL,
        ),
        "confidence": ParagraphStyle(
            "confidence",
            fontName=MONO,
            fontSize=17,
            leading=21,
            textColor=INK,
        ),
        "table_key": ParagraphStyle(
            "table_key",
            fontName=MONO,
            fontSize=7.2,
            leading=10,
            textColor=MUTED,
        ),
        "table_value": ParagraphStyle(
            "table_value",
            fontName=SANS,
            fontSize=8.4,
            leading=11.5,
            textColor=INK_SOFT,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer",
            fontName=SANS,
            fontSize=8.2,
            leading=12.6,
            textColor=INK_SOFT,
        ),
    }


def _format_date(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%d %B %Y, %H:%M UTC")


def _decorate_page(canvas, doc) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(BONE)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)

    band = 31 * mm
    canvas.setFillColor(INK)
    canvas.rect(0, height - band, width, band, fill=1, stroke=0)

    canvas.setFillColor(TEAL_BRIGHT)
    canvas.rect(20 * mm, height - band + 8 * mm, 7 * mm, 1.1 * mm, fill=1, stroke=0)

    canvas.setFillColor(BONE)
    canvas.setFont(SERIF, 15)
    canvas.drawString(20 * mm, height - 18.5 * mm, "Cancaria")
    canvas.setFillColor(BONE_MUTED)
    canvas.setFont(MONO, 6.6)
    canvas.drawString(20 * mm, height - 23.5 * mm, "MODEL CLASSIFICATION REPORT  /  EXPERIMENTAL")

    report_id = getattr(doc, "report_id", "")
    generated = getattr(doc, "report_date", "")
    canvas.setFillColor(BONE)
    canvas.setFont(MONO, 7.2)
    canvas.drawRightString(width - 20 * mm, height - 17 * mm, report_id)
    canvas.setFillColor(BONE_MUTED)
    canvas.setFont(MONO, 6.4)
    canvas.drawRightString(width - 20 * mm, height - 21.5 * mm, generated)

    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 15 * mm, width - 20 * mm, 15 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont(MONO, 6.2)
    canvas.drawString(
        20 * mm,
        10 * mm,
        "Cancaria  /  experimental research output  /  not a medical device",
    )
    canvas.drawRightString(width - 20 * mm, 10 * mm, f"{doc.page:02d}")

    canvas.setFillColor(TEAL)
    canvas.setFont(MONO, 6.2)
    canvas.drawString(20 * mm, height - 26.5 * mm, "")
    canvas.restoreState()


def render_pdf(report: dict[str, Any], image_jpeg: bytes) -> bytes:
    """Render a structured report payload to a designed A4 PDF."""
    styles = _styles()
    buffer = io.BytesIO()

    generated = datetime.fromisoformat(report["generated_at"])
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=44 * mm,
        bottomMargin=22 * mm,
        title=f"Cancaria classification report {report['report_id']}",
        author="Cancaria",
        subject="Experimental model output. Not a medical diagnosis.",
        creator="Cancaria report service",
    )
    doc.report_id = report["report_id"]
    doc.report_date = _format_date(generated)

    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=_decorate_page)])

    analysis = report["analysis"]
    story: list[Any] = []

    story.append(Paragraph("Class 04 / four-label image classifier", styles["kicker"]))
    story.append(Paragraph("Model classification result", styles["title"]))
    story.append(
        Paragraph(
            "A single-image output from a fine-tuned ResNet-18. Read the "
            "scores and limitations together.",
            styles["body"],
        )
    )

    pil = PILImage.open(io.BytesIO(image_jpeg)).convert("RGB")
    image_width = 55 * mm
    image_height = min(
        image_width * (pil.height / pil.width), 68 * mm
    )
    preview = Image(
        io.BytesIO(image_jpeg), width=image_width, height=image_height
    )
    preview.hAlign = "RIGHT"

    filename = analysis["image"]["filename"]
    short_name = filename if len(filename) <= 34 else filename[:31] + "..."
    caption = Paragraph(
        f"Analysed frame  /  {escape(short_name)}<br/>"
        f"{analysis['image']['width']} x {analysis['image']['height']} px  /  "
        f"inference {analysis['inference_ms']} ms",
        styles["caption"],
    )

    result_cell = [
        Paragraph("Predicted class", styles["table_key"]),
        Paragraph(escape(analysis["prediction"]), styles["class"]),
        Spacer(1, 3 * mm),
        Paragraph(f"{analysis['confidence']:.2f}%", styles["confidence"]),
        Paragraph(
            "Softmax score for the leading label. Not a disease probability.",
            styles["body_small"],
        ),
    ]

    summary = Table(
        [[result_cell, [preview, Spacer(1, 1.6 * mm), caption]]],
        colWidths=[doc.width - 60 * mm, 60 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )
    story.append(summary)
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph("Class-wise scores", styles["h2"]))
    story.append(ScoreBars(analysis["scores"], doc.width))
    story.append(
        Paragraph(
            "The four scores sum to 100%. The highlighted label is the "
            "argmax of the softmax output.",
            styles["body_small"],
        )
    )

    for section in report["narrative"]["sections"]:
        block: list[Any] = [Paragraph(escape(section["title"]), styles["h2"])]
        for paragraph in section["paragraphs"]:
            block.append(Paragraph(escape(paragraph), styles["body"]))
        story.append(KeepTogether(block))

    story.append(Paragraph("Limitations", styles["h2"]))
    for item in report["limitations"]:
        story.append(Paragraph(escape(item), styles["bullet"], bulletText="-"))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Model record", styles["h2"]))
    model = report["model"]
    f1 = model.get("validation_macro_f1")
    rows = [
        ("Architecture", model["architecture"]),
        ("Checkpoint", model["checkpoint"]),
        ("Input", model["input"]),
        ("Classes", " / ".join(model["classes"])),
        ("Transform", model["transform"]),
        ("Runtime", model["runtime"]),
        (
            "Validation macro-F1",
            f"{f1:.4f} (training run)" if isinstance(f1, (int, float)) else "not recorded",
        ),
    ]
    table_data = [
        [Paragraph(escape(key), styles["table_key"]), Paragraph(escape(value), styles["table_value"])]
        for key, value in rows
    ]
    model_table = Table(
        table_data,
        colWidths=[42 * mm, doc.width - 42 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, RULE),
            ]
        ),
    )
    story.append(model_table)

    story.append(Spacer(1, 8 * mm))
    disclaimer = Table(
        [[Paragraph(escape(report["disclaimer"]), styles["disclaimer"])]],
        colWidths=[doc.width],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BONE_DEEP),
                ("LINEBEFORE", (0, 0), (0, -1), 2.4, RUST),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        ),
    )
    story.append(disclaimer)

    provider = report["narrative"]["provider"]
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            f"Narrative provider: {escape(provider['label'])} "
            f"({escape(provider['id'])}). "
            + (
                "No language model was used for this report."
                if not provider["is_llm"]
                else "Narrative generated by a configured language model."
            ),
            styles["body_small"],
        )
    )
    story.append(
        Paragraph(
            "Report generated by Cancaria. The analysed image is held in memory "
            "only for the lifetime of this report.",
            styles["body_small"],
        )
    )

    doc.build(story)
    return buffer.getvalue()
