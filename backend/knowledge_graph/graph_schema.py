"""Neo4j node labels, relationship types, and constraint setup queries."""

NODE_LABELS = {
    "Patient": "Patient",
    "Visit": "Visit",
    "MRIScan": "MRIScan",
    "SyntheticPET": "SyntheticPET",
    "ClinicalReport": "ClinicalReport",
    "BloodReport": "BloodReport",
    "ClinicalFeatures": "ClinicalFeatures",
    "CognitiveTest": "CognitiveTest",
    "Prediction": "Prediction",
    "DigitalTwin": "DigitalTwin",
}

RELATIONSHIPS = {
    "HAS_VISIT": "HAS_VISIT",
    "HAS_MRI": "HAS_MRI",
    "HAS_SYNTHETIC_PET": "HAS_SYNTHETIC_PET",
    "HAS_CLINICAL_REPORT": "HAS_CLINICAL_REPORT",
    "HAS_BLOOD_REPORT": "HAS_BLOOD_REPORT",
    "HAS_FEATURES": "HAS_FEATURES",
    "HAS_COGNITIVE_TEST": "HAS_COGNITIVE_TEST",
    "HAS_PREDICTION": "HAS_PREDICTION",
    "HAS_TWIN": "HAS_TWIN",
    "SYNTHESIZED_TO": "SYNTHESIZED_TO",
}

# Cypher queries to create uniqueness constraints (run once on DB init)
CONSTRAINT_QUERIES = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Patient) REQUIRE p.patient_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Visit) REQUIRE v.visit_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:MRIScan) REQUIRE s.scan_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (pet:SyntheticPET) REQUIRE pet.pet_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (pred:Prediction) REQUIRE pred.pred_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:DigitalTwin) REQUIRE t.twin_id IS UNIQUE",
]
