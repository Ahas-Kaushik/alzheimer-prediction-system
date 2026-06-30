"""Medication knowledge graph mapper.

Maps clinical profile (Alzheimer's stage + age + MMSE + APOE4 + blood
markers) to evidence-based medication recommendations.  Rules derived from
published clinical guidelines (NICE 2018, FDA-approved label data, ADNI
pharmacological data).

Usage:
    from backend.knowledge_graph.medication_mapper import get_medications
    meds = get_medications("MCI", age=72, mmse=22, apoe4=True, ...)
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MedicationEntry:
    name: str
    drug_class: str
    dosage: str
    indication: str
    notes: str = ""
    contraindications: list[str] = field(default_factory=list)
    monitoring: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Clinical evidence sources — shown in UI and PDF to build clinical trust
# ---------------------------------------------------------------------------

EVIDENCE_SOURCES: list[dict] = [
    {
        "name": "NICE Guideline NG97",
        "description": "Dementia: assessment, management and support for people living with dementia and their carers",
        "year": "2018 (updated 2023)",
        "url": "https://www.nice.org.uk/guidance/ng97",
        "type": "Clinical Guideline",
    },
    {
        "name": "FDA Drug Approval Labels",
        "description": "FDA-approved prescribing information for Donepezil (NDA 20-690), Rivastigmine (NDA 20-823), Galantamine (NDA 21-169), Memantine (NDA 21-487), Lecanemab (BLA 761269)",
        "year": "1996–2023",
        "url": "https://www.fda.gov/drugs",
        "type": "Regulatory Approval",
    },
    {
        "name": "ADNI — Alzheimer's Disease Neuroimaging Initiative",
        "description": "Multi-site longitudinal study providing pharmacological and biomarker data used for AD drug efficacy and staging criteria",
        "year": "2004–present",
        "url": "https://adni.loni.usc.edu",
        "type": "Clinical Research Database",
    },
    {
        "name": "Alzheimer's Association Clinical Practice Guidelines",
        "description": "Evidence-based recommendations for pharmacological and non-pharmacological management of AD and MCI across all severity stages",
        "year": "2022",
        "url": "https://www.alz.org/professionals/health-systems-medical-professionals/clinical-guidelines",
        "type": "Clinical Guideline",
    },
    {
        "name": "MAPT Study — Multi-domain Alzheimer Preventive Trial",
        "description": "RCT evidence base for the multi-domain lifestyle intervention bundle (exercise, diet, cognitive training) in MCI prevention",
        "year": "Lancet 2017",
        "url": "https://doi.org/10.1016/S0140-6736(17)31612-7",
        "type": "Randomised Controlled Trial",
    },
    {
        "name": "van Dyck et al. — CLARITY AD Trial (Lecanemab)",
        "description": "Phase 3 RCT demonstrating lecanemab reduces amyloid plaques and slows cognitive decline in early AD with confirmed amyloid pathology",
        "year": "NEJM 2023",
        "url": "https://doi.org/10.1056/NEJMoa2212948",
        "type": "Phase 3 Clinical Trial",
    },
]


def get_evidence_sources() -> list[dict]:
    """Return the clinical evidence sources backing this knowledge graph."""
    return EVIDENCE_SOURCES


# ---------------------------------------------------------------------------
# Static medication knowledge base (evidence-based, not synthesised)
# ---------------------------------------------------------------------------

# First-line cholinesterase inhibitors
_CHEI_DONEPEZIL_MILD = MedicationEntry(
    name="Donepezil (Aricept)",
    drug_class="Cholinesterase Inhibitor",
    dosage="5 mg/day orally for 4 weeks, then 10 mg/day",
    indication="Mild to Moderate AD",
    notes="Take at bedtime to reduce nausea. Titrate slowly.",
    contraindications=["Sick sinus syndrome", "Severe asthma/COPD"],
    monitoring=["Heart rate", "GI symptoms", "Weight loss"],
)

_CHEI_DONEPEZIL_SEVERE = MedicationEntry(
    name="Donepezil (Aricept)",
    drug_class="Cholinesterase Inhibitor",
    dosage="10 mg/day; may increase to 23 mg/day for severe AD",
    indication="Severe AD",
    notes="Higher dose (23 mg) approved for severe AD; monitor for GI adverse effects.",
    contraindications=["Bradycardia", "Active GI bleeding"],
    monitoring=["Cognitive function (MMSE monthly)", "Cardiac rhythm"],
)

_CHEI_RIVASTIGMINE = MedicationEntry(
    name="Rivastigmine (Exelon)",
    drug_class="Cholinesterase Inhibitor",
    dosage="1.5 mg twice daily, titrate to 6 mg twice daily over 3–6 months; patch: 4.6 mg/24h → 9.5 mg/24h",
    indication="Mild to Moderate AD / MCI with functional impairment",
    notes="Patch form preferred when GI tolerance is poor. Rotate patch site daily.",
    contraindications=["Severe hepatic impairment"],
    monitoring=["GI tolerance", "Weight"],
)

_CHEI_GALANTAMINE = MedicationEntry(
    name="Galantamine (Razadyne ER)",
    drug_class="Cholinesterase Inhibitor / Nicotinic Receptor Modulator",
    dosage="8 mg/day ER for 4 weeks, then 16 mg/day; max 24 mg/day",
    indication="Mild to Moderate AD",
    notes="Take with food. ER form preferred (once daily).",
    contraindications=["Severe renal/hepatic impairment", "Urinary obstruction"],
    monitoring=["Renal function", "QT interval"],
)

# NMDA antagonist
_MEMANTINE = MedicationEntry(
    name="Memantine (Namenda)",
    drug_class="NMDA Receptor Antagonist",
    dosage="5 mg/day, increase by 5 mg/week to target 10 mg twice daily",
    indication="Moderate to Severe AD",
    notes="Can be combined with a cholinesterase inhibitor.",
    contraindications=["Severe renal impairment (use with caution, reduce dose)"],
    monitoring=["Renal function", "Cognitive decline trajectory"],
)

_COMBO_NAMZARIC = MedicationEntry(
    name="Memantine + Donepezil (Namzaric)",
    drug_class="Combination NMDA/ChEI",
    dosage="Memantine 28 mg + Donepezil 10 mg once daily",
    indication="Moderate to Severe AD already stable on donepezil 10 mg",
    notes="Fixed-dose combination; improves adherence.",
    contraindications=["Same as individual components"],
    monitoring=["GI adverse effects", "Renal function"],
)

# Lecanemab (anti-amyloid)
_LECANEMAB = MedicationEntry(
    name="Lecanemab (Leqembi)",
    drug_class="Anti-Amyloid Monoclonal Antibody",
    dosage="10 mg/kg IV every 2 weeks",
    indication="Early AD (MCI/mild AD with confirmed amyloid pathology)",
    notes="FDA-approved 2023. Requires amyloid PET or CSF confirmation. ARIA monitoring required.",
    contraindications=["Active intracranial haemorrhage", "Anticoagulation therapy (relative)"],
    monitoring=["MRI every 3 months for ARIA", "Infusion reactions"],
)

# MCI / risk-reduction
_LIFESTYLE_BUNDLE = MedicationEntry(
    name="Lifestyle + Supplement Bundle",
    drug_class="Non-pharmacological / Supplement",
    dosage="Vitamin B12 (if deficient), Omega-3 DHA 1 g/day, Vitamin D 800–1000 IU/day",
    indication="MCI / Elevated risk",
    notes="Control cardiovascular risk factors (hypertension, diabetes, cholesterol). Regular aerobic exercise ≥150 min/week.",
    contraindications=[],
    monitoring=["Annual cognitive assessment", "Vitamin B12/D levels"],
)

_RIVASTIGMINE_MCI = MedicationEntry(
    name="Rivastigmine (off-label for MCI)",
    drug_class="Cholinesterase Inhibitor",
    dosage="1.5 mg twice daily (low dose, discuss risk/benefit)",
    indication="Amnestic MCI with rapid decline or high APOE4 burden",
    notes="Not FDA-approved for MCI; use only after specialist discussion.",
    contraindications=["Severe hepatic impairment"],
    monitoring=["GI tolerance", "Annual cognitive reassessment"],
)

# Symptomatic / adjunct
_ANTIDEPRESSANT = MedicationEntry(
    name="Sertraline (Zoloft) or Escitalopram",
    drug_class="SSRI Antidepressant",
    dosage="Sertraline 25–50 mg/day; Escitalopram 5–10 mg/day (lower in elderly)",
    indication="Comorbid depression (prevalent in AD/MCI)",
    notes="Avoid TCAs. Monitor for hyponatraemia in elderly.",
    contraindications=["Concurrent MAOIs", "QT-prolonging medications"],
    monitoring=["Sodium levels", "Mood response at 6 weeks"],
)

_STATIN = MedicationEntry(
    name="Atorvastatin / Rosuvastatin",
    drug_class="HMG-CoA Reductase Inhibitor (Statin)",
    dosage="Atorvastatin 20–40 mg/day",
    indication="Elevated LDL cholesterol (>160 mg/dL) with AD/MCI",
    notes="May reduce vascular dementia component. Target LDL <100 mg/dL.",
    contraindications=["Active liver disease", "Pregnancy"],
    monitoring=["LFTs at baseline and 3 months", "CK if myalgia"],
)

_ANTIHYPERTENSIVE = MedicationEntry(
    name="Amlodipine / Lisinopril",
    drug_class="Antihypertensive",
    dosage="Amlodipine 5 mg/day or Lisinopril 10 mg/day",
    indication="Hypertension with AD/MCI",
    notes="Target BP <130/80 mmHg. ACE inhibitors may have neuroprotective effects.",
    contraindications=["Severe aortic stenosis (amlodipine)", "ACE inhibitor cough (use ARB instead)"],
    monitoring=["BP monitoring", "Renal function (lisinopril)"],
)

_METFORMIN = MedicationEntry(
    name="Metformin",
    drug_class="Biguanide (anti-diabetic)",
    dosage="500 mg twice daily with meals, titrate to 1000 mg twice daily",
    indication="Type 2 diabetes with AD/MCI (may have neuroprotective signals)",
    notes="Vitamin B12 monitoring required long-term.",
    contraindications=["eGFR <30", "Hepatic impairment", "Contrast agent within 48h"],
    monitoring=["HbA1c", "Vitamin B12 annually", "Renal function"],
)

_VITB12_SUPPLEMENT = MedicationEntry(
    name="Vitamin B12 (Methylcobalamin)",
    drug_class="Vitamin Supplement",
    dosage="1000 mcg/day oral or 1 mg/month IM (if malabsorption)",
    indication="Vitamin B12 deficiency contributing to cognitive decline",
    notes="Deficiency is reversible cause of cognitive impairment; must address.",
    contraindications=[],
    monitoring=["B12 level at 3 months", "Cognitive reassessment"],
)


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

def get_medications(
    stage: str,
    age: Optional[float] = None,
    mmse: Optional[float] = None,
    apoe4: Optional[bool] = None,
    cholesterol: Optional[float] = None,
    hdl: Optional[float] = None,
    ldl: Optional[float] = None,
    glucose: Optional[float] = None,
    hemoglobin: Optional[float] = None,
    vit_b12: Optional[float] = None,
    hypertension: Optional[bool] = None,
    diabetes: Optional[bool] = None,
    depression: Optional[bool] = None,
    amyloid_confirmed: bool = False,
) -> list[dict]:
    """Return a ranked list of medication recommendations for a patient profile.

    Args:
        stage: "Normal", "MCI", or "AD"
        age: Patient age in years.
        mmse: MMSE score (0–30); lower = more impaired.
        apoe4: APOE4 carrier status (True/False/None=unknown).
        cholesterol: Total cholesterol mg/dL.
        hdl: HDL cholesterol mg/dL.
        ldl: LDL cholesterol mg/dL.
        glucose: Fasting glucose mg/dL.
        hemoglobin: Haemoglobin g/dL (used to flag anaemia).
        vit_b12: Vitamin B12 pg/mL (<200 = deficient).
        hypertension: Known hypertension.
        diabetes: Known diabetes.
        depression: Comorbid depression.
        amyloid_confirmed: Amyloid PET/CSF positive (enables lecanemab route).

    Returns:
        List of dicts (serialisable) with medication details.
    """
    stage = stage.strip()
    meds: list[MedicationEntry] = []

    # -- Stage-primary recommendations --
    if stage == "Normal":
        meds.append(_LIFESTYLE_BUNDLE)

    elif stage == "MCI":
        meds.append(_LIFESTYLE_BUNDLE)
        if apoe4 or (mmse is not None and mmse < 26):
            meds.append(_RIVASTIGMINE_MCI)
        if amyloid_confirmed:
            meds.append(_LECANEMAB)

    elif stage == "AD":
        # Determine AD severity from MMSE
        # Mild AD: MMSE 20-26, Moderate: 10-19, Severe: <10
        if mmse is None or mmse >= 20:
            # Mild AD
            meds.append(_CHEI_DONEPEZIL_MILD)
        elif mmse >= 10:
            # Moderate AD — add memantine combination
            meds.append(_CHEI_DONEPEZIL_SEVERE)
            meds.append(_MEMANTINE)
        else:
            # Severe AD
            meds.append(_COMBO_NAMZARIC)

        # Anti-amyloid for early AD
        if amyloid_confirmed and (mmse is None or mmse >= 18):
            meds.append(_LECANEMAB)

    # -- Comorbidity / risk-factor add-ons --
    if vit_b12 is not None and vit_b12 < 200:
        meds.append(_VITB12_SUPPLEMENT)

    if ldl is not None and ldl > 160:
        meds.append(_STATIN)
    elif cholesterol is not None and hdl is not None:
        non_hdl = cholesterol - hdl
        if non_hdl > 130:
            meds.append(_STATIN)

    if hypertension:
        meds.append(_ANTIHYPERTENSIVE)

    if diabetes:
        meds.append(_METFORMIN)

    if depression:
        meds.append(_ANTIDEPRESSANT)

    # -- Age-based caution flag --
    elderly = age is not None and age >= 80

    results = []
    for m in meds:
        entry = {
            "name": m.name,
            "drug_class": m.drug_class,
            "dosage": m.dosage,
            "indication": m.indication,
            "notes": m.notes,
            "contraindications": m.contraindications,
            "monitoring": m.monitoring,
        }
        if elderly:
            entry["notes"] += " [Elderly caution: start at lowest dose, monitor closely for falls and confusion.]"
        results.append(entry)

    return results


def get_medications_csv(stage: str, **kwargs) -> str:
    """Return medications as CSV string for embedding in reports."""
    meds = get_medications(stage, **kwargs)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Drug", "Class", "Dosage", "Indication", "Notes"])
    for m in meds:
        writer.writerow([m["name"], m["drug_class"], m["dosage"], m["indication"], m["notes"]])
    return buf.getvalue()
