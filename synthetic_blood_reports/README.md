# Synthetic Blood / Clinical Reports (OCR test fixtures)

These images are **fake lab reports** for testing the Blood Reports OCR pipeline
(`PaddleOCR → report_parser.py`). Upload them on a patient's **Blood Reports** page
(`/patient/<id>/reports` → "Extract Fields with OCR") to confirm the system reads
and structures the values correctly.

## Files

| File | Profile | Expected stage signal |
|------|---------|-----------------------|
| `report_normal_healthy.png` | Healthy 68 y/o female | Normal biomarkers, MMSE 29 |
| `report_mci_borderline.png` | 74 y/o male, APOE4+ | Borderline / MCI, MMSE 24 |
| `report_ad_advanced.png` | 81 y/o female | AD pattern, MMSE 17, high tau |

Regenerate any time with:

```bash
python synthetic_blood_reports/generate_reports.py
```

## Expected extraction (verified end-to-end)

`report_normal_healthy.png` → 20 fields, e.g.:

```json
{"hemoglobin": 14.2, "glucose_fasting": 92, "cholesterol_total": 185,
 "hdl": 62, "ldl": 104, "triglycerides": 110, "vitamin_b12": 480,
 "thyroid_tsh": 2.1, "mmse_score": 29, "moca_score": 28, "cdr_score": 0,
 "apoe4_status": "Negative", "amyloid_beta_42": 1150, "tau_protein": 210,
 "p_tau_181": 18, "hippocampal_volume": 3550, "cortical_thickness": 2.7}
```

`report_ad_advanced.png` → 21 fields (hemoglobin 11.8, tau 620, mmse 17,
diabetes/hypertension/depression/family-history flags true), etc.

## How the layout is OCR-friendly

Each measurement is rendered on **one line** as `Label: value unit (Ref: range)`
so PaddleOCR emits a single text block (`Hemoglobin: 14.2 g/dL`). The parser's
regex `label[:\s]+(number)` then captures the value. Wide multi-column tables
would split label and value into separate OCR lines and defeat parsing.

## Notes / caveats

- OCR runs with oneDNN/MKLDNN **disabled** (`FLAGS_use_mkldnn=0`); some CPUs
  crash inside Paddle's oneDNN kernels otherwise. Handled in `ocr_engine.py`.
- The parser understands simple **negation** ("No diabetes" → not flagged).
- These are for software testing only — not real patients or medical advice.
