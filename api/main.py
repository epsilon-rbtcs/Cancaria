"""Cancaria web application.

Serves the landing page, the scan-analysis workspace and the report viewer,
and exposes the existing ResNet-18 inference endpoint plus report routes.

Run from the project root:
    uvicorn api.main:app --reload
"""

from __future__ import annotations

import io
import logging
import mimetypes
import os
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError

sys.path.append(".")

from src.analysis_store import AnalysisRecord, AnalysisStore, new_report_id
from src.predict import MODEL_INFO, predict
from src.report import (
    TemplateNarrativeProvider,
    build_report,
    get_narrative_provider,
    render_pdf,
)

logger = logging.getLogger("cancaria")

# Windows registries do not always map modern web asset types. Register them
# before StaticFiles is mounted so browsers receive the correct MIME types.
for _type, _ext in (
    ("image/webp", ".webp"),
    ("image/svg+xml", ".svg"),
    ("font/woff2", ".woff2"),
    ("video/mp4", ".mp4"),
    ("text/vtt", ".vtt"),
):
    mimetypes.add_type(_type, _ext)

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DEMO_VIDEO = WEB / "static" / "media" / "cancaria-demo.mp4"
DEMO_CAPTIONS = WEB / "static" / "media" / "cancaria-demo.en.vtt"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
GENERIC_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
MAX_PIXELS = 40_000_000
PREVIEW_MAX = 1400
ANALYSIS_TTL = int(os.getenv("CANCARIA_ANALYSIS_TTL_SECONDS", "1800"))

app = FastAPI(
    title="Cancaria API",
    description="Experimental four-class lung CT image classifier.",
    version="0.2.0",
)

app.mount("/static", StaticFiles(directory=str(WEB / "static")), name="static")
templates = Jinja2Templates(directory=str(WEB / "templates"))

store = AnalysisStore(ttl_seconds=ANALYSIS_TTL)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return response


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"page": "home", "title": "Cancaria — experimental lung CT classification"},
    )


@app.get("/analyse", response_class=HTMLResponse)
def analyse(request: Request):
    return templates.TemplateResponse(
        request,
        "analyse.html",
        {"page": "analyse", "title": "Scan analysis — Cancaria"},
    )


@app.get("/report", response_class=HTMLResponse)
def report_page(request: Request):
    return templates.TemplateResponse(
        request,
        "report.html",
        {"page": "report", "title": "Classification report — Cancaria"},
    )


# --------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------


@app.get("/api")
def api_root():
    """Keeps the original service check available at a new path."""
    return {"message": "Cancaria API is running"}


@app.get("/api/health")
def health():
    provider = get_narrative_provider()
    return {
        "status": "ok",
        "model": MODEL_INFO["architecture"],
        "device": MODEL_INFO["device"],
        "classes": MODEL_INFO["display_names"],
        "input_size": MODEL_INFO["image_size"],
        "narrative_provider": provider.provider_id,
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "demo_video": DEMO_VIDEO.is_file(),
        "demo_captions": DEMO_CAPTIONS.is_file(),
    }


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"Image exceeds the {limit // (1024 * 1024)} MB limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_image(data: bytes) -> Image.Image:
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    try:
        image = Image.open(BytesIO(data))
        if (image.format or "").upper() not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail="This image format is not accepted. Use PNG, JPEG, or WebP.",
            )
        image.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="This file could not be read as an image.",
        )
    if image.width * image.height > MAX_PIXELS:
        raise HTTPException(
            status_code=400,
            detail="The image dimensions are too large to process.",
        )
    if image.width < 32 or image.height < 32:
        raise HTTPException(
            status_code=400,
            detail="The image is too small. Use a scan of at least 32 x 32 px.",
        )
    return image.convert("RGB")


def _preview_jpeg(image: Image.Image) -> bytes:
    preview = image.copy()
    preview.thumbnail((PREVIEW_MAX, PREVIEW_MAX))
    buffer = io.BytesIO()
    preview.save(buffer, format="JPEG", quality=88, optimize=True)
    return buffer.getvalue()


@app.post("/predict")
async def classify(file: UploadFile = File(...)):
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    suffix = Path(file.filename or "").suffix.lower()
    generic_with_suffix = content_type in GENERIC_TYPES and suffix in ALLOWED_SUFFIXES
    if content_type not in ALLOWED_TYPES and not generic_with_suffix:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a PNG, JPEG, or WebP image.",
        )

    data = await _read_limited(file, MAX_UPLOAD_BYTES)
    image = _decode_image(data)

    started = time.perf_counter()
    try:
        result = await run_in_threadpool(predict, image)
    except Exception:
        logger.exception("Prediction failed")
        raise HTTPException(
            status_code=500,
            detail="The model did not return a result.",
        )
    inference_ms = int(round((time.perf_counter() - started) * 1000))

    report_id = new_report_id()
    record = AnalysisRecord(
        report_id=report_id,
        created_at=time.time(),
        filename=(file.filename or "upload")[:160],
        width=image.width,
        height=image.height,
        inference_ms=inference_ms,
        result=result,
        image_jpeg=_preview_jpeg(image),
    )
    store.put(record)

    # Existing keys are untouched; report metadata is additive.
    return {
        **result,
        "analysis_id": report_id,
        "report_id": report_id,
        "inference_ms": inference_ms,
        "image": {
            "filename": record.filename,
            "width": record.width,
            "height": record.height,
        },
    }


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


def _get_record(report_id: str) -> AnalysisRecord:
    record = store.get(report_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "This report has expired or does not exist. Analyses are kept "
                f"in memory for {ANALYSIS_TTL // 60} minutes."
            ),
        )
    return record


@app.get("/api/report/{report_id}")
def report_json(report_id: str):
    record = _get_record(report_id)
    return JSONResponse(
        build_report(record),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/report/{report_id}/image")
def report_image(report_id: str):
    record = _get_record(report_id)
    return Response(
        content=record.image_jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/report/{report_id}/pdf")
def report_pdf(report_id: str):
    record = _get_record(report_id)
    report = build_report(record)
    try:
        pdf = render_pdf(report, record.image_jpeg)
    except Exception:
        logger.exception("PDF rendering failed")
        raise HTTPException(
            status_code=500,
            detail="The PDF could not be generated. Try again.",
        )

    filename = f"cancaria-report-{record.report_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/config")
def client_config():
    """Small, public configuration surface for the frontend."""
    return {
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "accepted_types": sorted(ALLOWED_TYPES),
        "report_ttl_minutes": ANALYSIS_TTL // 60,
        "narrative_provider": get_narrative_provider().provider_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
