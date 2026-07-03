"""GraphRAG: ground answers in Neo4j patient facts + vector-retrieved knowledge.

Flow:  question ─▶ vector search over clinical knowledge (Neo4j vector index)
                └▶ structured patient facts from the knowledge graph
        ──▶ build grounded prompt ──▶ Gemini (or templated fallback)
"""
from __future__ import annotations

import json
from typing import Optional

from backend.knowledge_graph import patient_store
from backend.llm import gemini_client
from backend.rag import vector_store
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ── patient facts from the knowledge graph ──────────────────────────────────────

def gather_patient_facts(patient_id: str) -> dict:
    """Collect a compact factual snapshot of the patient from the graph."""
    facts: dict = {}
    patient = patient_store.get_patient(patient_id)
    if patient:
        facts["name"] = patient.get("name")
        facts["gender"] = patient.get("gender")
        facts["dob"] = patient.get("dob")

    latest = patient_store.get_latest_prediction(patient_id)
    if latest:
        facts["stage"] = latest.get("stage")
        facts["confidence"] = latest.get("confidence")
        facts["cognitive_index"] = latest.get("cognitive_index")
        facts["contributing_factors"] = latest.get("contributing_factors")

    history = patient_store.get_predictions(patient_id)
    facts["num_predictions"] = len(history)

    reports = patient_store.get_reports(patient_id)
    if reports:
        raw = reports[-1].get("extracted_fields_json") or reports[-1].get("extracted_fields")
        if isinstance(raw, str):
            try:
                facts["clinical"] = json.loads(raw)
            except Exception:
                pass
        elif isinstance(raw, dict):
            facts["clinical"] = raw
    return facts


def _facts_to_text(facts: dict) -> str:
    if not facts:
        return "No records found for this patient."
    lines = []
    if facts.get("name"):
        lines.append(f"Patient: {facts['name']} ({facts.get('gender', '?')})")
    if facts.get("stage"):
        conf = facts.get("confidence")
        lines.append(f"Latest predicted stage: {facts['stage']}"
                     + (f" (confidence {conf})" if conf else ""))
    if facts.get("cognitive_index"):
        lines.append(f"Cognitive index: {facts['cognitive_index']}/100")
    if facts.get("contributing_factors"):
        lines.append(f"Top contributing factors: {facts['contributing_factors']}")
    clinical = facts.get("clinical") or {}
    if clinical:
        kv = ", ".join(f"{k}={v}" for k, v in clinical.items() if v not in ("", None))
        if kv:
            lines.append(f"Clinical/blood data: {kv}")
    lines.append(f"Prediction history entries: {facts.get('num_predictions', 0)}")
    return "\n".join(lines)


# ── public API ──────────────────────────────────────────────────────────────────

def answer_question(patient_id: str, question: str) -> dict:
    """Answer a free-text question about a patient using GraphRAG."""
    facts = gather_patient_facts(patient_id)
    facts_text = _facts_to_text(facts)
    chunks = vector_store.search(question)
    context = "\n\n".join(f"[{c['title']}] {c['text']}" for c in chunks)

    prompt = (
        f"PATIENT KNOWLEDGE-GRAPH FACTS:\n{facts_text}\n\n"
        f"RETRIEVED CLINICAL KNOWLEDGE:\n{context or '(none)'}\n\n"
        f"QUESTION: {question}\n\n"
        "Answer using ONLY the facts and knowledge above. Be concise (3-6 sentences). "
        "If the data is insufficient, say so."
    )

    llm_text = gemini_client.complete(prompt)
    if llm_text:
        answer, used_llm = llm_text, True
    else:
        answer, used_llm = _templated_answer(question, facts, chunks), False

    return {
        "answer": answer,
        "used_llm": used_llm,
        "sources": [{"title": c["title"], "category": c.get("category"),
                     "score": round(float(c["score"]), 3)} for c in chunks],
        "patient_facts": facts,
    }


def explain_prediction(patient_id: str) -> dict:
    """Produce a grounded clinical explanation of the patient's latest stage."""
    facts = gather_patient_facts(patient_id)
    stage = facts.get("stage") or "Unknown"
    question = (
        f"Explain why this patient's screening indicates the {stage} stage, what the key "
        f"biomarkers and risk factors mean, and what monitoring or management is appropriate."
    )
    return answer_question(patient_id, question)


# ── deterministic fallback (no LLM / offline) ───────────────────────────────────

def _templated_answer(question: str, facts: dict, chunks: list[dict]) -> str:
    stage = facts.get("stage")
    parts: list[str] = []
    if stage:
        parts.append(
            f"Based on the knowledge graph, the patient's latest screening indicates the "
            f"{stage} stage."
        )
        if facts.get("cognitive_index"):
            parts.append(f"The cognitive index is {facts['cognitive_index']}/100.")
        if facts.get("contributing_factors"):
            parts.append(f"Key contributing factors: {facts['contributing_factors']}.")
    else:
        parts.append("No prediction is on record for this patient yet, so a stage cannot be given.")

    if chunks:
        top = chunks[0]
        parts.append(f"Relevant clinical guidance ({top['title']}): {top['text']}")
    parts.append("Note: this is automated decision support, not a diagnosis; confirm with a clinician.")
    return " ".join(parts)
