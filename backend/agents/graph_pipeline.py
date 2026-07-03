"""LangGraph orchestration of the Alzheimer prediction pipeline.

The four agents are wired as nodes of a `StateGraph`:

    START ─▶ validate ──(has scan?)──▶ predict ─▶ reason ─▶ END
                     └────(no scan)────────────────────────▶ END(error)

* ``validate`` — guard: ensure the patient has an MRI scan.
* ``predict``  — runs the existing Agent-2/3/1 pipeline (GAN → cognitive →
  fuse+classify) via ``agent4_orchestrator.run_pipeline``.
* ``reason``   — GraphRAG node: grounds a clinical explanation in the Neo4j
  knowledge graph + vector-retrieved guidelines (Gemini or templated).

This preserves all working ML logic while giving the project a real
agentic LangGraph architecture on top of the knowledge graph + RAG.
"""
from __future__ import annotations

from typing import Optional, TypedDict

from backend.agents import agent4_orchestrator
from backend.config import settings
from backend.knowledge_graph import patient_store
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PipelineState(TypedDict, total=False):
    patient_id: str
    scan_id: Optional[str]
    clinical_features: Optional[dict]
    cognitive_session_id: Optional[str]
    skip_cognitive_test: bool
    result: dict
    explanation: dict
    error: str


# ── nodes ────────────────────────────────────────────────────────────────────────

def _validate(state: PipelineState) -> PipelineState:
    scans = patient_store.get_all_scans(state["patient_id"])
    if not scans:
        return {"error": f"No MRI scan found for patient {state['patient_id']}"}
    return {}


def _route_after_validate(state: PipelineState) -> str:
    return "end" if state.get("error") else "predict"


def _predict(state: PipelineState) -> PipelineState:
    result = agent4_orchestrator.run_pipeline(
        patient_id=state["patient_id"],
        scan_id=state.get("scan_id"),
        clinical_features=state.get("clinical_features") or {},
        cognitive_session_id=state.get("cognitive_session_id"),
        skip_cognitive_test=state.get("skip_cognitive_test", False),
    )
    return {"result": result}


def _reason(state: PipelineState) -> PipelineState:
    if not settings.enable_rag:
        return {}
    try:
        from backend.rag import graph_rag
        explanation = graph_rag.explain_prediction(state["patient_id"])
        return {"explanation": explanation}
    except Exception as e:  # noqa: BLE001 — reasoning is best-effort
        logger.warning(f"RAG reason node skipped: {e}")
        return {}


# ── graph construction (compiled once) ──────────────────────────────────────────

_compiled = None


def _build():
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(PipelineState)
    g.add_node("validate", _validate)
    g.add_node("predict", _predict)
    g.add_node("reason", _reason)
    g.add_edge(START, "validate")
    g.add_conditional_edges("validate", _route_after_validate, {"predict": "predict", "end": END})
    g.add_edge("predict", "reason")
    g.add_edge("reason", END)
    return g.compile()


def get_pipeline():
    global _compiled
    if _compiled is None:
        _compiled = _build()
    return _compiled


def run_graph_pipeline(
    patient_id: str,
    scan_id: Optional[str] = None,
    clinical_features: Optional[dict] = None,
    cognitive_session_id: Optional[str] = None,
    skip_cognitive_test: bool = False,
) -> dict:
    """Invoke the LangGraph pipeline; returns the prediction result dict.

    Raises ValueError if validation fails (mirrors the orchestrator contract).
    """
    state: PipelineState = {
        "patient_id": patient_id,
        "scan_id": scan_id,
        "clinical_features": clinical_features or {},
        "cognitive_session_id": cognitive_session_id,
        "skip_cognitive_test": skip_cognitive_test,
    }
    final = get_pipeline().invoke(state)
    if final.get("error"):
        raise ValueError(final["error"])
    result = dict(final["result"])
    if final.get("explanation"):
        result["rag_explanation"] = final["explanation"]
    return result
