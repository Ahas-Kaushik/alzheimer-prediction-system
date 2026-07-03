"""Curated clinical knowledge chunks embedded into the Neo4j vector index.

These documents are the retrieval corpus for GraphRAG. Sources are summarised
from public clinical guidelines (NICE NG97, Alzheimer's Association, FDA labels,
ADNI). They are educational summaries, not medical advice.
"""
from __future__ import annotations

KNOWLEDGE_CHUNKS: list[dict] = [
    {
        "id": "kb-stage-normal",
        "title": "Cognitively Normal (CN)",
        "category": "staging",
        "text": "Cognitively Normal means no significant impairment on cognitive testing "
                "(MMSE typically 27-30, CDR 0). Biomarkers such as amyloid-beta 42, tau and "
                "p-tau are within normal limits and hippocampal volume is preserved. Management "
                "focuses on risk reduction: cardiovascular control, exercise, diet and cognitive "
                "engagement.",
    },
    {
        "id": "kb-stage-mci",
        "title": "Mild Cognitive Impairment (MCI)",
        "category": "staging",
        "text": "MCI is a transitional stage between normal ageing and dementia. MMSE is often "
                "24-27 and CDR 0.5. There is measurable cognitive decline greater than expected for "
                "age but daily function is largely preserved. Amnestic MCI with APOE4 positivity, "
                "low amyloid-beta 42 or elevated p-tau carries higher risk of progression to "
                "Alzheimer's disease. Early intervention can slow progression.",
    },
    {
        "id": "kb-stage-ad",
        "title": "Alzheimer's Disease (AD)",
        "category": "staging",
        "text": "Alzheimer's disease is characterised by progressive memory loss and functional "
                "decline. MMSE below 24 indicates dementia (20-23 mild, 10-19 moderate, below 10 "
                "severe). Hallmarks include low CSF amyloid-beta 42, elevated total tau and p-tau-181, "
                "hippocampal atrophy and cortical thinning. Management combines cholinesterase "
                "inhibitors, memantine, and where amyloid is confirmed, anti-amyloid antibodies.",
    },
    {
        "id": "kb-biomarker-amyloid",
        "title": "Amyloid-beta 42 biomarker",
        "category": "biomarker",
        "text": "Amyloid-beta 42 (Abeta42) is a core Alzheimer's biomarker. LOW CSF/plasma "
                "Abeta42 (roughly below 1000 pg/mL on many assays) reflects amyloid plaque "
                "deposition in the brain and supports an Alzheimer's pathology. Confirmed amyloid "
                "positivity is required before starting anti-amyloid therapy such as lecanemab.",
    },
    {
        "id": "kb-biomarker-tau",
        "title": "Tau and p-tau-181 biomarkers",
        "category": "biomarker",
        "text": "Total tau reflects neurodegeneration and p-tau-181 reflects tau tangle pathology "
                "specific to Alzheimer's disease. Elevated tau (above ~300 pg/mL) and p-tau-181 "
                "(above ~24 pg/mL) increase the likelihood of AD and predict faster decline. The "
                "amyloid/tau (A/T) profile is central to modern biological staging of AD.",
    },
    {
        "id": "kb-cognitive-mmse",
        "title": "MMSE and MoCA cognitive scales",
        "category": "cognitive",
        "text": "The Mini-Mental State Examination (MMSE, 0-30) and Montreal Cognitive Assessment "
                "(MoCA, 0-30) screen global cognition. MMSE 24-30 is broadly normal, 18-23 mild "
                "impairment, below 18 moderate-severe. MoCA is more sensitive to MCI; a score below "
                "26 is abnormal. Serial scores track progression over visits.",
    },
    {
        "id": "kb-med-donepezil",
        "title": "Cholinesterase inhibitors (donepezil, rivastigmine, galantamine)",
        "category": "medication",
        "text": "Cholinesterase inhibitors are first-line for mild-to-moderate Alzheimer's disease. "
                "Donepezil starts 5 mg/day then 10 mg/day; rivastigmine is available as a patch for "
                "poor GI tolerance; galantamine ER is dosed once daily. Monitor heart rate, GI "
                "symptoms and weight. Contraindicated in sick sinus syndrome and active GI bleeding.",
    },
    {
        "id": "kb-med-memantine",
        "title": "Memantine (NMDA antagonist)",
        "category": "medication",
        "text": "Memantine is an NMDA receptor antagonist used in moderate-to-severe Alzheimer's "
                "disease, often combined with a cholinesterase inhibitor (e.g. Namzaric). Titrate "
                "from 5 mg/day to 10 mg twice daily. Reduce dose in severe renal impairment.",
    },
    {
        "id": "kb-med-lecanemab",
        "title": "Lecanemab (anti-amyloid antibody)",
        "category": "medication",
        "text": "Lecanemab is an anti-amyloid monoclonal antibody approved for early Alzheimer's "
                "disease (MCI or mild AD) with CONFIRMED amyloid pathology. Dose 10 mg/kg IV every "
                "two weeks. Requires MRI monitoring every three months for amyloid-related imaging "
                "abnormalities (ARIA). Caution with anticoagulation.",
    },
    {
        "id": "kb-risk-modifiable",
        "title": "Modifiable dementia risk factors",
        "category": "risk",
        "text": "Modifiable risk factors for cognitive decline include hypertension, diabetes, "
                "high LDL cholesterol, smoking, physical inactivity, obesity, depression, hearing "
                "loss and low cognitive engagement. Controlling blood pressure (<130/80), managing "
                "diabetes, statins for high LDL, smoking cessation and 150 minutes/week of aerobic "
                "exercise reduce risk. Vitamin B12 deficiency is a reversible cause of cognitive "
                "impairment.",
    },
    {
        "id": "kb-apoe4",
        "title": "APOE4 genetic risk",
        "category": "risk",
        "text": "The APOE4 allele is the strongest common genetic risk factor for late-onset "
                "Alzheimer's disease. One copy raises risk roughly 3-fold and two copies far more. "
                "APOE4 carriers have higher rates of amyloid deposition and a higher ARIA risk on "
                "anti-amyloid therapy, so carrier status informs both prognosis and treatment.",
    },
    {
        "id": "kb-lifestyle",
        "title": "Lifestyle and multidomain intervention",
        "category": "lifestyle",
        "text": "The MAPT and FINGER trials support multidomain lifestyle intervention "
                "(aerobic exercise, Mediterranean-style diet, cognitive training, vascular risk "
                "management) to slow cognitive decline in at-risk older adults. Omega-3 DHA, vitamin "
                "D and correcting vitamin B12 deficiency are commonly recommended adjuncts.",
    },
    {
        "id": "kb-system-pipeline",
        "title": "How the NeuroScan AI pipeline works",
        "category": "system",
        "text": "The system ingests a brain MRI, synthesises a PET-like image with a GAN, runs a "
                "foil-gated cognitive test, extracts ResNet image features, fuses them with clinical "
                "blood-report and cognitive data, and classifies the Alzheimer stage (Normal, MCI, "
                "AD) with an MLP. Results, a Grad-CAM heatmap and a digital brain twin are stored in "
                "a Neo4j knowledge graph and explained with retrieval-augmented generation.",
    },
    {
        "id": "kb-digital-twin",
        "title": "Digital brain twin and longitudinal tracking",
        "category": "system",
        "text": "The digital twin models regional severity and neuron connectivity for a patient and "
                "tracks change across visits. A cognitive-index drop of more than 15 points between "
                "assessments flags significant decline and warrants urgent clinical review.",
    },
    {
        "id": "kb-bloodwork",
        "title": "Blood panel relevance to cognition",
        "category": "biomarker",
        "text": "Routine bloods contextualise cognitive decline: low haemoglobin (anaemia), low "
                "vitamin B12 (below 200 pg/mL), abnormal thyroid TSH, poorly controlled fasting "
                "glucose and an adverse lipid profile (high LDL, low HDL) all contribute to or mimic "
                "cognitive impairment and are potentially reversible when treated.",
    },
]
