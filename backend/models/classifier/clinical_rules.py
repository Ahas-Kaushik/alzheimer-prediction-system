"""Rule-based clinical biomarker override for the Alzheimer's classifier.

The trained MLP is driven mostly by MRI/PET structural features and can be
insensitive to blood / CSF biomarker panels — so a patient with an
unambiguously AD-positive lab report could still be scored MCI just because the
MRI looked mild or the cognitive test was gamed.

This module adds a transparent, clinically-grounded scoring layer on top of the
model. When the biomarker evidence is strongly consistent with AD (the ATN
framework: low amyloid-β42 + high tau/p-tau, supported by APOE4 status, low
MMSE/MoCA, high CDR and hippocampal atrophy), the stage is escalated to AD
*regardless* of what the MRI or cognitive test alone suggested.

Design goals:
  * Deterministic and explainable (every point is attributed to a named marker).
  * Accepts BOTH canonical field names (from the OCR report parser) and the
    shorter aliases emitted by the clinical data form.
  * Never *downgrades* a prediction — it only escalates severity.

Reference thresholds are approximate clinical cut-points (ADNI / ATN literature)
and are intended for this educational project, not real diagnosis.
"""
from __future__ import annotations

from typing import Optional

# Decision thresholds on the accumulated biomarker point total.
AD_THRESHOLD = 6.0
MCI_THRESHOLD = 3.0

_STAGE_SEVERITY = {"Normal": 0, "MCI": 1, "AD": 2}


def _num(clinical: dict, *keys) -> Optional[float]:
    """Return the first numeric value found under any of the given aliases."""
    for k in keys:
        if k in clinical and clinical[k] not in (None, "", "null"):
            try:
                return float(clinical[k])
            except (TypeError, ValueError):
                continue
    return None


def _truthy(clinical: dict, *keys) -> bool:
    """Return True if any alias holds a positive/true value (handles bool + text)."""
    for k in keys:
        if k in clinical:
            v = clinical[k]
            if isinstance(v, bool):
                if v:
                    return True
            elif v not in (None, "", "null"):
                if str(v).strip().lower() in ("true", "yes", "1", "positive", "carrier"):
                    return True
    return False


def assess_clinical_ad_risk(clinical: dict, cognitive_scores: Optional[dict] = None) -> dict:
    """Score AD biomarker burden from a clinical feature dict.

    Args:
        clinical: Merged clinical features (OCR-parsed and/or form-entered).
        cognitive_scores: Optional Agent-3 scores (used only as a weak fallback
            when no clinical MMSE was supplied).

    Returns:
        Dict with:
            ad_points:      float total burden score.
            override_stage: "AD" | "MCI" | None  (None ⇒ defer to the model).
            confidence:     suggested confidence for the override stage.
            probabilities:  suggested {Normal, MCI, AD} distribution.
            reasons:        human-readable list of the abnormal markers.
    """
    clinical = clinical or {}
    cognitive_scores = cognitive_scores or {}
    points = 0.0
    reasons: list[str] = []

    def add(pts: float, reason: str) -> None:
        nonlocal points
        points += pts
        reasons.append(reason)

    # ── CSF / plasma biomarkers (the strongest, ATN-framework evidence) ─────────
    amyloid = _num(clinical, "amyloid_beta_42", "amyloid_level", "amyloid")
    if amyloid is not None:
        if amyloid < 550:
            add(2.0, f"Amyloid-β42 critically low ({amyloid:.0f} pg/mL)")
        elif amyloid < 700:
            add(1.0, f"Amyloid-β42 reduced ({amyloid:.0f} pg/mL)")

    tau = _num(clinical, "tau_protein", "tau_level", "tau")
    if tau is not None:
        if tau > 500:
            add(2.0, f"Total tau markedly elevated ({tau:.0f} pg/mL)")
        elif tau > 350:
            add(1.0, f"Total tau elevated ({tau:.0f} pg/mL)")

    ptau = _num(clinical, "p_tau_181", "ptau_level", "ptau", "p_tau")
    if ptau is not None:
        if ptau > 45:
            add(2.0, f"p-Tau181 markedly elevated ({ptau:.0f} pg/mL)")
        elif ptau > 27:
            add(1.0, f"p-Tau181 elevated ({ptau:.0f} pg/mL)")

    if _truthy(clinical, "apoe4_status", "apoe4"):
        add(1.0, "APOE4 carrier")

    # ── Cognitive / staging scales ──────────────────────────────────────────────
    mmse = _num(clinical, "mmse_score", "mmse")
    if mmse is None and cognitive_scores.get("derived_mmse") is not None:
        try:
            mmse = float(cognitive_scores["derived_mmse"])
        except (TypeError, ValueError):
            mmse = None
    if mmse is not None:
        if mmse < 20:
            add(2.0, f"MMSE in dementia range ({mmse:.0f}/30)")
        elif mmse <= 24:
            add(1.0, f"MMSE below normal ({mmse:.0f}/30)")

    moca = _num(clinical, "moca_score", "moca")
    if moca is not None:
        if moca < 18:
            add(1.0, f"MoCA in impaired range ({moca:.0f}/30)")

    cdr = _num(clinical, "cdr_score", "cdr")
    if cdr is not None:
        if cdr >= 1:
            add(2.0, f"CDR consistent with dementia ({cdr:g})")
        elif cdr >= 0.5:
            add(1.0, f"CDR questionable ({cdr:g})")

    # ── Structural volumetrics (from report / form, not the raw MRI image) ──────
    hippo = _num(clinical, "hippocampal_volume", "hippocampal")
    if hippo is not None:
        if hippo < 2700:
            add(2.0, f"Severe hippocampal atrophy ({hippo:.0f} mm³)")
        elif hippo < 3100:
            add(1.0, f"Hippocampal atrophy ({hippo:.0f} mm³)")

    cortical = _num(clinical, "cortical_thickness", "cortical")
    if cortical is not None:
        if cortical < 2.2:
            add(1.0, f"Cortical thinning ({cortical:.2f} mm)")

    # ── Metabolic / vascular co-factors (weak supportive evidence, capped) ──────
    support = 0.0
    glucose = _num(clinical, "glucose_fasting", "glucose")
    if glucose is not None and glucose > 130:
        support += 0.5
    ldl = _num(clinical, "ldl")
    if ldl is not None and ldl > 160:
        support += 0.5
    b12 = _num(clinical, "vitamin_b12", "vit_b12")
    if b12 is not None and b12 < 200:
        support += 0.5
    if _truthy(clinical, "diabetes"):
        support += 0.5
    if support > 0:
        capped = min(support, 1.5)
        add(capped, "Vascular/metabolic risk factors present")

    # ── Decide ──────────────────────────────────────────────────────────────────
    override_stage: Optional[str] = None
    if points >= AD_THRESHOLD:
        override_stage = "AD"
    elif points >= MCI_THRESHOLD:
        override_stage = "MCI"

    confidence, probabilities = _stage_confidence(override_stage, points)

    return {
        "ad_points": round(points, 2),
        "override_stage": override_stage,
        "confidence": confidence,
        "probabilities": probabilities,
        "reasons": reasons,
    }


def _stage_confidence(stage: Optional[str], points: float) -> tuple[float, dict]:
    if stage == "AD":
        conf = min(0.97, 0.70 + 0.025 * (points - AD_THRESHOLD))
        rest = 1.0 - conf
        return conf, {"Normal": rest * 0.25, "MCI": rest * 0.75, "AD": conf}
    if stage == "MCI":
        conf = min(0.90, 0.60 + 0.04 * (points - MCI_THRESHOLD))
        rest = 1.0 - conf
        return conf, {"Normal": rest * 0.5, "MCI": conf, "AD": rest * 0.5}
    return 0.0, {}


def apply_override(model_result: dict, clinical: dict, cognitive_scores: Optional[dict] = None) -> dict:
    """Blend the model prediction with the biomarker rule layer.

    The rule layer can only *escalate* severity (Normal→MCI→AD). If it agrees
    with or is milder than the model, the model result is kept unchanged (but the
    biomarker reasons are still surfaced as contributing factors when present).

    Returns a new result dict with possibly-updated stage / confidence /
    probabilities and an added ``override_applied`` flag + ``biomarker_reasons``.
    """
    assessment = assess_clinical_ad_risk(clinical, cognitive_scores)
    override_stage = assessment["override_stage"]
    reasons = assessment["reasons"]

    result = dict(model_result)
    result["biomarker_reasons"] = reasons
    result["ad_points"] = assessment["ad_points"]
    result["override_applied"] = False

    if not override_stage:
        return result

    model_sev = _STAGE_SEVERITY.get(model_result.get("stage", "Normal"), 0)
    override_sev = _STAGE_SEVERITY.get(override_stage, 0)

    if override_sev > model_sev:
        result["stage"] = override_stage
        result["confidence"] = assessment["confidence"]
        result["probabilities"] = assessment["probabilities"]
        result["override_applied"] = True

    return result
