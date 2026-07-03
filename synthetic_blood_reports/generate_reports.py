"""Generate synthetic blood / clinical report images for testing OCR parsing.

The text labels are deliberately formatted to match the regex patterns in
`backend/models/ocr/report_parser.py` so that uploading these images through the
Blood Reports page exercises the full OCR → parse → clinical-features pipeline.

Run:  python synthetic_blood_reports/generate_reports.py
Output: PNG images in this folder (one per patient profile).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent


# ── Font loading (fall back to PIL default if system font missing) ──────────────

def _font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ── Report profiles ─────────────────────────────────────────────────────────────
# Each row: (Label, value, unit, reference-range). Labels are chosen so the
# parser's regexes capture the number after the label cleanly.

PROFILES = {
    "report_normal_healthy": {
        "patient": ("Margaret Doe", "Female", "68"),
        "verdict": "Cognitively Normal profile",
        "panels": {
            "Complete Blood Count": [
                ("Hemoglobin", "14.2", "g/dL", "12.0-15.5"),
            ],
            "Metabolic / Lipid Panel": [
                ("Fasting Glucose", "92", "mg/dL", "70-100"),
                ("Total Cholesterol", "185", "mg/dL", "<200"),
                ("HDL", "62", "mg/dL", ">50"),
                ("LDL", "104", "mg/dL", "<130"),
                ("Triglycerides", "110", "mg/dL", "<150"),
                ("Vitamin B12", "480", "pg/mL", "200-900"),
                ("TSH", "2.1", "mIU/L", "0.4-4.0"),
            ],
            "Cognitive Assessment": [
                ("MMSE", "29", "/30", "24-30 normal"),
                ("MoCA", "28", "/30", ">=26 normal"),
                ("CDR", "0", "", "0 = none"),
            ],
            "CSF / Plasma Biomarkers": [
                ("Amyloid-Beta 42", "1150", "pg/mL", ">1000"),
                ("Tau", "210", "pg/mL", "<300"),
                ("p-Tau 181", "18", "pg/mL", "<24"),
                ("APOE4", "Negative", "", "carrier status"),
            ],
            "MRI Volumetrics": [
                ("Hippocampal Volume", "3550", "mm3", ">3300"),
                ("Cortical Thickness", "2.7", "mm", ">2.5"),
            ],
        },
        "history": "Risk factors: no smoking history. No diabetes. No hypertension.",
    },
    "report_mci_borderline": {
        "patient": ("Robert Smith", "Male", "74"),
        "verdict": "Mild Cognitive Impairment (MCI) profile",
        "panels": {
            "Complete Blood Count": [
                ("Hemoglobin", "13.1", "g/dL", "13.0-17.0"),
            ],
            "Metabolic / Lipid Panel": [
                ("Fasting Glucose", "118", "mg/dL", "70-100"),
                ("Total Cholesterol", "224", "mg/dL", "<200"),
                ("HDL", "44", "mg/dL", ">40"),
                ("LDL", "148", "mg/dL", "<130"),
                ("Triglycerides", "180", "mg/dL", "<150"),
                ("Vitamin B12", "190", "pg/mL", "200-900"),
                ("TSH", "3.4", "mIU/L", "0.4-4.0"),
            ],
            "Cognitive Assessment": [
                ("MMSE", "24", "/30", "24-30 normal"),
                ("MoCA", "21", "/30", ">=26 normal"),
                ("CDR", "0.5", "", "0.5 = questionable"),
            ],
            "CSF / Plasma Biomarkers": [
                ("Amyloid-Beta 42", "820", "pg/mL", ">1000"),
                ("Tau", "340", "pg/mL", "<300"),
                ("p-Tau 181", "28", "pg/mL", "<24"),
                ("APOE4", "Positive", "", "carrier status"),
            ],
            "MRI Volumetrics": [
                ("Hippocampal Volume", "3050", "mm3", ">3300"),
                ("Cortical Thickness", "2.4", "mm", ">2.5"),
            ],
        },
        "history": "Risk factors: former smoker (smoking history). Hypertension present. "
                   "Family history of Alzheimer's disease noted.",
    },
    "report_ad_advanced": {
        "patient": ("Eleanor Vance", "Female", "81"),
        "verdict": "Alzheimer's Disease (AD) profile",
        "panels": {
            "Complete Blood Count": [
                ("Hemoglobin", "11.8", "g/dL", "12.0-15.5"),
            ],
            "Metabolic / Lipid Panel": [
                ("Fasting Glucose", "141", "mg/dL", "70-100"),
                ("Total Cholesterol", "252", "mg/dL", "<200"),
                ("HDL", "38", "mg/dL", ">50"),
                ("LDL", "172", "mg/dL", "<130"),
                ("Triglycerides", "210", "mg/dL", "<150"),
                ("Vitamin B12", "160", "pg/mL", "200-900"),
                ("TSH", "5.2", "mIU/L", "0.4-4.0"),
            ],
            "Cognitive Assessment": [
                ("MMSE", "17", "/30", "24-30 normal"),
                ("MoCA", "14", "/30", ">=26 normal"),
                ("CDR", "2", "", "2 = moderate"),
            ],
            "CSF / Plasma Biomarkers": [
                ("Amyloid-Beta 42", "540", "pg/mL", ">1000"),
                ("Tau", "620", "pg/mL", "<300"),
                ("p-Tau 181", "58", "pg/mL", "<24"),
                ("APOE4", "Positive", "", "carrier status"),
            ],
            "MRI Volumetrics": [
                ("Hippocampal Volume", "2450", "mm3", ">3300"),
                ("Cortical Thickness", "2.0", "mm", ">2.5"),
            ],
        },
        "history": "Risk factors: diabetes (type 2). Hypertension present. "
                   "Depression history documented. Family history of Alzheimer's disease.",
    },
}


# ── Rendering ────────────────────────────────────────────────────────────────────

W = 1000
MARGIN = 50
LINE_H = 34


def render(name: str, data: dict) -> Path:
    # Estimate height
    rows = sum(len(v) for v in data["panels"].values())
    panels = len(data["panels"])
    height = (
        MARGIN * 2 + 190                      # header + patient block
        + panels * (LINE_H + 14)              # panel titles
        + rows * LINE_H                       # rows
        + 90                                  # history/footer
    )
    img = Image.new("RGB", (W, height), "white")
    d = ImageDraw.Draw(img)

    f_title = _font(34, bold=True)
    f_sub = _font(18)
    f_panel = _font(22, bold=True)
    f_row = _font(22)
    f_small = _font(16)

    y = MARGIN
    # Lab header
    d.text((MARGIN, y), "NEUROCARE DIAGNOSTIC LABORATORY", font=f_title, fill=(20, 40, 90))
    y += 42
    d.text((MARGIN, y), "Clinical Biochemistry & Neurology Panel  |  CLIA #99D-SYNTH", font=f_small, fill=(90, 90, 90))
    y += 30
    d.line([(MARGIN, y), (W - MARGIN, y)], fill=(20, 40, 90), width=3)
    y += 20

    # Patient block
    pname, psex, page = data["patient"]
    d.text((MARGIN, y), f"Patient: {pname}", font=f_sub, fill=(0, 0, 0))
    d.text((MARGIN + 460, y), f"Sex: {psex}", font=f_sub, fill=(0, 0, 0))
    d.text((MARGIN + 640, y), f"Age: {page}", font=f_sub, fill=(0, 0, 0))
    y += 28
    d.text((MARGIN, y), f"Report: {name}   |   Interpretation: {data['verdict']}", font=f_small, fill=(90, 90, 90))
    y += 34

    # Panels
    for panel_title, panel_rows in data["panels"].items():
        d.text((MARGIN, y), panel_title, font=f_panel, fill=(20, 40, 90))
        y += LINE_H + 6
        d.line([(MARGIN + 20, y), (W - MARGIN, y)], fill=(200, 200, 200), width=1)
        y += 8
        for label, value, unit, ref in panel_rows:
            # CRITICAL FOR OCR: keep "Label: value" on ONE line with no large
            # horizontal gap so PaddleOCR emits a single text block like
            # "Hemoglobin: 14.2 g/dL" that the parser's `label[:\s]+(num)` regex
            # can match. Wide column gaps split label/value into separate OCR
            # lines and break parsing.
            unit_part = f" {unit}" if unit else ""
            ref_part = f"   (Ref: {ref})" if ref else ""
            line = f"{label}: {value}{unit_part}{ref_part}"
            d.text((MARGIN + 20, y), line, font=f_row, fill=(0, 0, 0))
            y += LINE_H
        y += 12

    # History / risk factors (drives the boolean keyword extraction)
    d.line([(MARGIN, y), (W - MARGIN, y)], fill=(200, 200, 200), width=1)
    y += 14
    d.text((MARGIN, y), data["history"], font=f_small, fill=(0, 0, 0))
    y += 30
    d.text((MARGIN, y), "* Synthetic report generated for software testing only — not a real patient.",
           font=f_small, fill=(150, 150, 150))

    out = OUT_DIR / f"{name}.png"
    img.save(out, "PNG")
    return out


if __name__ == "__main__":
    for name, data in PROFILES.items():
        p = render(name, data)
        print(f"Wrote {p}")
    print("\nDone. Upload these PNGs on the Blood Reports page to test OCR parsing.")
