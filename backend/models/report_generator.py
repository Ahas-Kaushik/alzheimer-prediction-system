"""Generate downloadable medical PDF reports using ReportLab.

Creates a fully-formatted clinical report including:
- Patient demographics
- Alzheimer's stage + confidence
- Digital twin brain region image (embedded as PNG)
- Prescribed medication table (from medication_mapper)
- Key clinical markers summary

Usage:
    from backend.models.report_generator import generate_pdf
    pdf_bytes = generate_pdf(patient, prediction, twin_data, medications)
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Color palette (matches Tailwind theme)
# ---------------------------------------------------------------------------
_DARK_BG = colors.HexColor("#0a0f1e")
_SURFACE = colors.HexColor("#111827")
_PRIMARY = colors.HexColor("#6366f1")
_SUCCESS = colors.HexColor("#22c55e")
_WARNING = colors.HexColor("#f59e0b")
_DANGER = colors.HexColor("#ef4444")
_WHITE = colors.white
_MUTED = colors.HexColor("#9ca3af")
_BORDER = colors.HexColor("#1f2937")

_STAGE_COLORS = {
    "Normal": _SUCCESS,
    "MCI": _WARNING,
    "AD": _DANGER,
}

_STAGE_LABELS = {
    "Normal": "Normal Cognition",
    "MCI": "Mild Cognitive Impairment (MCI)",
    "AD": "Alzheimer's Disease (AD)",
}


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _styles():
    base = getSampleStyleSheet()
    normal = base["Normal"]

    h1 = ParagraphStyle(
        "ReportH1",
        parent=normal,
        fontSize=20,
        leading=24,
        textColor=_WHITE,
        spaceAfter=4,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    h2 = ParagraphStyle(
        "ReportH2",
        parent=normal,
        fontSize=13,
        leading=16,
        textColor=_PRIMARY,
        spaceBefore=14,
        spaceAfter=4,
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
    )
    body = ParagraphStyle(
        "ReportBody",
        parent=normal,
        fontSize=9,
        leading=13,
        textColor=_WHITE,
        fontName="Helvetica",
    )
    muted = ParagraphStyle(
        "ReportMuted",
        parent=normal,
        fontSize=8,
        leading=11,
        textColor=_MUTED,
        fontName="Helvetica",
    )
    stage_normal = ParagraphStyle(
        "StageNormal",
        parent=normal,
        fontSize=16,
        leading=20,
        textColor=_SUCCESS,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    stage_mci = ParagraphStyle(
        "StageMCI",
        parent=normal,
        fontSize=16,
        leading=20,
        textColor=_WARNING,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    stage_ad = ParagraphStyle(
        "StageAD",
        parent=normal,
        fontSize=16,
        leading=20,
        textColor=_DANGER,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    disclaimer = ParagraphStyle(
        "Disclaimer",
        parent=normal,
        fontSize=7,
        leading=10,
        textColor=_MUTED,
        fontName="Helvetica-Oblique",
        alignment=TA_CENTER,
    )
    return {
        "h1": h1, "h2": h2, "body": body, "muted": muted,
        "stage_Normal": stage_normal, "stage_MCI": stage_mci, "stage_AD": stage_ad,
        "disclaimer": disclaimer,
    }


def _hr():
    return HRFlowable(width="100%", thickness=1, color=_BORDER, spaceAfter=6, spaceBefore=6)


def _stage_style_name(stage: str) -> str:
    return f"stage_{stage}" if stage in _STAGE_COLORS else "stage_AD"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _to_float(val) -> float | None:
    """Convert value to float; return None for empty / null / non-numeric."""
    if val is None:
        return None
    try:
        s = str(val).strip()
        return float(s) if s and s.lower() not in ("none", "null", "") else None
    except (ValueError, TypeError):
        return None


def _coerce_dict(val) -> dict:
    """Coerce a value that may be a dict OR a JSON / python-literal string into a dict.

    The CSV store persists `probabilities` as a JSON string, so when a prediction
    is loaded back it arrives here as ``str``. Calling ``.items()`` on that string
    used to raise ``AttributeError`` and crash PDF generation with a 500. This
    helper makes the report generator tolerant of both shapes.
    """
    if isinstance(val, dict):
        return val
    if not val or not isinstance(val, str):
        return {}
    s = val.strip()
    if not s or s.lower() in ("none", "null"):
        return {}
    import json as _json
    try:
        parsed = _json.loads(s)
    except Exception:
        try:
            import ast as _ast
            parsed = _ast.literal_eval(s)
        except Exception:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _coerce_list(val) -> list:
    """Coerce a value that may be a list OR a JSON / python-literal string into a list."""
    if isinstance(val, list):
        return val
    if isinstance(val, tuple):
        return list(val)
    if not val or not isinstance(val, str):
        return []
    s = val.strip()
    if not s or s.lower() in ("none", "null"):
        return []
    import json as _json
    try:
        parsed = _json.loads(s)
    except Exception:
        try:
            import ast as _ast
            parsed = _ast.literal_eval(s)
        except Exception:
            return []
    if isinstance(parsed, (list, tuple)):
        return list(parsed)
    return []


def _build_reasoning(stage: str, factors: list, cognitive_index=None, ssim_score=None) -> str:
    context = {
        "Normal": (
            "No significant biomarker abnormalities or structural changes were identified. "
            "Brain metabolism, volume, and cognitive performance all fall within normal limits "
            "for the patient's age group. Continued lifestyle-based prevention is recommended."
        ),
        "MCI": (
            "Mild but measurable changes in cognitive biomarkers and/or neuroimaging suggest "
            "early-stage neurodegeneration. This is a transitional state — intervention at this "
            "point can meaningfully slow progression. Close monitoring every 6 months is advised."
        ),
        "AD": (
            "Multiple convergent indicators — including neuroimaging atrophy patterns, amyloid/"
            "tau burden, and cognitive deficits — are consistent with established Alzheimer's "
            "Disease pathology. A multidisciplinary care plan including pharmacological and "
            "non-pharmacological interventions is recommended."
        ),
    }
    base = context.get(stage, "Stage assessment performed by multimodal AI pipeline.")
    factor_line = (
        f" Primary model-identified factors: {', '.join(factors)}."
        if factors else ""
    )
    cog_f = _to_float(cognitive_index)
    cog_line = f" Cognitive assessment composite score: {cog_f:.1f}/100." if cog_f is not None else ""

    pet_line = (
        " Note: PET was synthesized via physics-based tissue classification from the MRI structure. "
        "The classifier (MLP) was trained on OASIS data which contains no PET scans, so PET features "
        "carry near-zero weight in the prediction. The diagnosis is driven by MRI features, "
        "clinical biomarkers, and cognitive assessment scores."
    )
    return f"{base}{factor_line}{cog_line}{pet_line}"


def generate_pdf(
    patient: dict,
    prediction: dict,
    twin_data: Optional[dict] = None,
    medications: Optional[list[dict]] = None,
    twin_image_path: Optional[str] = None,
    pet_image_path: Optional[str] = None,
    gradcam_image_path: Optional[str] = None,
) -> bytes:
    """Generate a PDF medical report and return raw bytes.

    Args:
        patient: Dict with keys: name, dob, gender, patient_id.
        prediction: Dict with stage, confidence, probabilities, contributing_factors,
                    cognitive_index, ssim_score.
        twin_data: Optional digital twin payload with regions list.
        medications: Optional list of medication dicts from medication_mapper.
        twin_image_path: Optional path to a pre-rendered twin PNG image to embed.

    Returns:
        PDF as raw bytes.
    """
    buf = io.BytesIO()

    def _dark_bg_canvas(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(_DARK_BG)
        canvas.rect(0, 0, *A4, fill=1, stroke=0)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    S = _styles()
    W, H = A4
    content_w = W - 4 * cm
    story = []

    # -- Header --
    story.append(Paragraph("NeuroScan AI", S["h1"]))
    story.append(Paragraph("Alzheimer's Prediction Medical Report", S["muted"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_hr())

    # -- Report metadata --
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    meta_data = [
        ["Report Date:", now, "Patient ID:", patient.get("patient_id", "—")],
        ["Generated by:", "NeuroScan AI v1.0", "Confidential:", "Yes — For clinical use only"],
    ]
    meta_table = Table(meta_data, colWidths=[3 * cm, 6 * cm, 3 * cm, 5.5 * cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), _MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), _WHITE),
        ("TEXTCOLOR", (3, 0), (3, -1), _WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.4 * cm))

    # -- Patient demographics --
    story.append(Paragraph("Patient Information", S["h2"]))
    story.append(_hr())

    age = _calc_age(patient.get("dob"))
    demo_data = [
        ["Full Name", patient.get("name", "Unknown"), "Date of Birth", patient.get("dob", "—")],
        ["Age", f"{age} years" if age else "—", "Gender", patient.get("gender", "—").title()],
    ]
    demo_table = Table(demo_data, colWidths=[3.5 * cm, 7 * cm, 3.5 * cm, 4.5 * cm])
    demo_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), _MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), _WHITE),
        ("TEXTCOLOR", (3, 0), (3, -1), _WHITE),
        ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (1, 0), (1, 0), 11),
        ("BACKGROUND", (0, 0), (-1, -1), _SURFACE),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_SURFACE, _DARK_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(demo_table)
    story.append(Spacer(1, 0.5 * cm))

    # -- Diagnosis --
    story.append(Paragraph("Alzheimer's Stage Prediction", S["h2"]))
    story.append(_hr())

    stage = prediction.get("stage", "Unknown")
    confidence = _to_float(prediction.get("confidence")) or 0.0
    stage_label = _STAGE_LABELS.get(stage, stage)
    stage_color = _STAGE_COLORS.get(stage, _WHITE)

    stage_data = [
        [
            Paragraph(stage_label, S[_stage_style_name(stage)]),
            Paragraph(f"Confidence: {confidence * 100:.1f}%", S["body"]),
        ]
    ]
    stage_table = Table(stage_data, colWidths=[12 * cm, 5.5 * cm])
    stage_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _SURFACE),
        ("GRID", (0, 0), (-1, -1), 1, stage_color),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(stage_table)
    story.append(Spacer(1, 0.3 * cm))

    # Probability breakdown
    # `probabilities` may arrive as a dict (fresh from the pipeline) or as a JSON
    # string (loaded back from the CSV store) — coerce so .items() never crashes.
    probs = _coerce_dict(prediction.get("probabilities", {}))
    if probs:
        prob_rows = [["Stage", "Probability"]]
        for s_name, p_val in probs.items():
            p_f = _to_float(p_val)
            prob_rows.append([s_name, f"{p_f * 100:.1f}%" if p_f is not None else "—"])
        prob_table = Table(prob_rows, colWidths=[6 * cm, 4 * cm])
        prob_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _BORDER),
            ("TEXTCOLOR", (0, 0), (-1, 0), _MUTED),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 1), (-1, -1), _WHITE),
            ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(prob_table)

    # Contributing factors — stored as list or as JSON / Python repr string
    factors = _coerce_list(prediction.get("contributing_factors", []))
    if not factors:
        _raw_factor = prediction.get("contributing_factors")
        if isinstance(_raw_factor, str) and _raw_factor.strip() and _raw_factor.strip().lower() not in ("none", "null", "[]"):
            factors = [_raw_factor.strip()]

    if factors:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            f"<b>Key Contributing Factors:</b> {', '.join(str(f) for f in factors)}",
            S["body"],
        ))

    cog_index_f = _to_float(prediction.get("cognitive_index"))
    if cog_index_f is not None:
        story.append(Paragraph(
            f"<b>Cognitive Test Index:</b> {cog_index_f:.1f} / 100",
            S["body"],
        ))

    story.append(Spacer(1, 0.5 * cm))

    # -- Clinical Reasoning --
    story.append(Paragraph("Clinical Reasoning", S["h2"]))
    story.append(_hr())
    reasoning_text = _build_reasoning(
        stage=stage,
        factors=[str(f) for f in factors],  # factors already parsed to list above
        cognitive_index=prediction.get("cognitive_index"),
        ssim_score=prediction.get("ssim_score"),
    )
    story.append(Paragraph(reasoning_text, S["body"]))
    story.append(Spacer(1, 0.5 * cm))

    # -- Synthesized PET Scan image --
    if pet_image_path and os.path.isfile(pet_image_path):
        story.append(Paragraph("Synthesized PET Scan", S["h2"]))
        story.append(_hr())
        story.append(Paragraph(
            "Visualization only. Tissue uptake map colored from the MRI "
            "(cortex bright, white matter lower, ventricles and background dark). "
            "This is not a scanner FDG-PET and is not a diagnosis. "
            "The same map is the PET input to the stage model.",
            S["muted"],
        ))
        story.append(Spacer(1, 0.2 * cm))
        try:
            pet_img = Image(pet_image_path, width=7 * cm, height=7 * cm)
            story.append(pet_img)
            story.append(Spacer(1, 0.3 * cm))
        except Exception as exc:
            logger.warning(f"Could not embed PET image: {exc}")

    # -- Grad-CAM overlay --
    if gradcam_image_path and os.path.isfile(gradcam_image_path):
        story.append(Paragraph("Grad-CAM: Brain Regions Driving Prediction", S["h2"]))
        story.append(_hr())
        story.append(Paragraph(
            "Gradient-weighted Class Activation Mapping (Grad-CAM) highlights which spatial "
            "regions of the MRI most influenced the AI's prediction. Warm (red/yellow) regions "
            "contributed most strongly; cool/dark regions had minimal influence.",
            S["muted"],
        ))
        story.append(Spacer(1, 0.2 * cm))
        try:
            gc_img = Image(gradcam_image_path, width=7 * cm, height=7 * cm)
            story.append(gc_img)
            story.append(Spacer(1, 0.3 * cm))
        except Exception as exc:
            logger.warning(f"Could not embed Grad-CAM image: {exc}")

    # -- Digital Twin brain image --
    if twin_image_path and os.path.isfile(twin_image_path):
        story.append(Paragraph("Digital Brain Twin", S["h2"]))
        story.append(_hr())
        try:
            img = Image(twin_image_path, width=8 * cm, height=8 * cm)
            story.append(img)
            story.append(Spacer(1, 0.3 * cm))
        except Exception as exc:
            logger.warning(f"Could not embed twin image: {exc}")

    # Brain region severity table from twin_data.
    # The CSV store persists regions under `regions_json` as a stringified list,
    # while a fresh twin payload uses `regions` — support both.
    twin_regions = []
    if twin_data:
        twin_regions = _coerce_list(twin_data.get("regions") or twin_data.get("regions_json"))
    if twin_regions:
        story.append(Paragraph("Brain Region Severity", S["h2"]))
        story.append(_hr())
        region_rows = [["Brain Region", "Status", "Severity"]]
        for r in twin_regions:
            if not isinstance(r, dict):
                continue
            _sev = _to_float(r.get("severity")) or 0.0
            region_rows.append([
                r.get("name", "—"),
                r.get("status", "—"),
                f"{_sev * 100:.0f}%",
            ])
        region_table = Table(region_rows, colWidths=[6 * cm, 4 * cm, 3 * cm])
        region_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _BORDER),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), _MUTED),
            ("TEXTCOLOR", (0, 1), (-1, -1), _WHITE),
            ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_SURFACE, _DARK_BG]),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(region_table)
        story.append(Spacer(1, 0.5 * cm))

    # -- Medications --
    if medications:
        story.append(Paragraph("Prescribed Medications", S["h2"]))
        story.append(_hr())
        story.append(Paragraph(
            "Based on stage, clinical markers, and patient risk factors. "
            "Final prescription must be confirmed by a licensed physician.",
            S["muted"],
        ))
        story.append(Spacer(1, 0.3 * cm))

        for i, med in enumerate(medications):
            med_data = [
                [Paragraph(f"<b>{med['name']}</b>", S["body"]),
                 Paragraph(f"<i>{med['drug_class']}</i>", S["muted"])],
                [Paragraph(f"Dosage: {med['dosage']}", S["body"]), ""],
                [Paragraph(f"Indication: {med['indication']}", S["body"]), ""],
            ]
            if med.get("notes"):
                med_data.append([Paragraph(f"Notes: {med['notes']}", S["muted"]), ""])
            if med.get("contraindications"):
                med_data.append([
                    Paragraph(
                        f"Contraindications: {', '.join(med['contraindications'])}",
                        S["muted"],
                    ), ""
                ])
            if med.get("monitoring"):
                med_data.append([
                    Paragraph(
                        f"Monitoring: {', '.join(med['monitoring'])}",
                        S["muted"],
                    ), ""
                ])

            # Only SPAN rows that actually exist (row 0 is header with 2 cols)
            span_cmds = [("SPAN", (0, r), (-1, r)) for r in range(1, len(med_data))]
            med_table = Table(med_data, colWidths=[10 * cm, 7.5 * cm])
            med_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), _SURFACE),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
                *span_cmds,
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(med_table)
            story.append(Spacer(1, 0.3 * cm))

    # -- Clinical Evidence Base / Knowledge Graph Sources --
    story.append(Paragraph("Clinical Evidence Base", S["h2"]))
    story.append(_hr())
    story.append(Paragraph(
        "Medication recommendations are derived from a structured clinical knowledge graph "
        "built on the following peer-reviewed guidelines and regulatory sources:",
        S["body"],
    ))
    story.append(Spacer(1, 0.25 * cm))

    from backend.knowledge_graph.medication_mapper import EVIDENCE_SOURCES
    src_rows = [["Source", "Type", "Year"]]
    for src in EVIDENCE_SOURCES:
        # Use a Table cell with two stacked paragraphs instead of inline font tags
        name_para = Paragraph(f"<b>{src['name']}</b>", S["body"])
        desc_para = Paragraph(src["description"], S["muted"])
        src_rows.append([
            [name_para, desc_para],
            Paragraph(src["type"], S["muted"]),
            Paragraph(src["year"], S["muted"]),
        ])
    src_table = Table(src_rows, colWidths=[10.5 * cm, 4 * cm, 3 * cm])
    src_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _BORDER),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), _MUTED),
        ("TEXTCOLOR", (0, 1), (-1, -1), _WHITE),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_SURFACE, _DARK_BG]),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(src_table)
    story.append(Spacer(1, 0.5 * cm))

    # -- Disclaimer --
    story.append(Spacer(1, 0.5 * cm))
    story.append(_hr())
    story.append(Paragraph(
        "DISCLAIMER: This report is generated by an AI-assisted system for research and educational purposes only. "
        "It does not constitute medical advice. Diagnosis, treatment, and prescription decisions must be made by a "
        "qualified healthcare professional. The AI predictions carry inherent uncertainty and must be interpreted "
        "alongside full clinical evaluation.",
        S["disclaimer"],
    ))

    doc.build(story, onFirstPage=_dark_bg_canvas, onLaterPages=_dark_bg_canvas)
    return buf.getvalue()


def _calc_age(dob_str: Optional[str]) -> Optional[int]:
    if not dob_str:
        return None
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d")
        today = datetime.utcnow()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None
