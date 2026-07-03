"""Builds a compact, readable snapshot of the knowledge graph for the UI.

Backend-agnostic: reads through ``patient_store`` so it works whether the active
backend is Neo4j or the CSV fallback. Child records are capped per type so the
node-link diagram stays legible (the full graph lives in the Neo4j Browser).
"""
from __future__ import annotations

from backend.knowledge_graph import patient_store

# node fill colours per type (mirrors the frontend palette)
NODE_TYPES = ["Patient", "Visit", "Prediction", "Report", "CognitiveTest", "DigitalTwin", "MRIScan"]


def get_graph_snapshot(cap: int = 3) -> dict:
    """Return {nodes, edges, counts} for the patient knowledge graph.

    Args:
        cap: max child records shown per type per patient (keeps it readable).
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    counts: dict[str, int] = {t: 0 for t in NODE_TYPES}

    def add_node(node_id: str, ntype: str, caption: str) -> None:
        nodes.append({"id": node_id, "type": ntype, "caption": caption})

    def add_edge(src: str, dst: str, rel: str) -> None:
        edges.append({"source": src, "target": dst, "type": rel})

    patients = patient_store.list_patients()
    for p in patients:
        pid = p["patient_id"]
        counts["Patient"] += 1
        add_node(pid, "Patient", p.get("name") or pid)

        # Predictions (most recent first)
        preds = patient_store.get_predictions(pid)
        counts["Prediction"] += len(preds)
        for pr in list(reversed(preds))[:cap]:
            nid = pr.get("pred_id")
            add_node(nid, "Prediction", pr.get("stage") or "?")
            add_edge(pid, nid, "HAS_PREDICTION")

        # Visits
        visits = patient_store.get_visits(pid)
        counts["Visit"] += len(visits)
        for v in list(reversed(visits))[:cap]:
            nid = v.get("visit_id")
            add_node(nid, "Visit", "Visit")
            add_edge(pid, nid, "HAS_VISIT")

        # Reports
        reports = patient_store.get_reports(pid)
        counts["Report"] += len(reports)
        for r in list(reversed(reports))[:cap]:
            nid = r.get("report_id")
            add_node(nid, "Report", r.get("source_type") or "Report")
            add_edge(pid, nid, "HAS_REPORT")

        # Cognitive tests
        cogs = patient_store.get_cognitive_tests(pid)
        counts["CognitiveTest"] += len(cogs)
        for cg in list(reversed(cogs))[:cap]:
            nid = cg.get("test_id")
            add_node(nid, "CognitiveTest", "Cognitive")
            add_edge(pid, nid, "HAS_COGNITIVE_TEST")

        # Latest digital twin
        twin = patient_store.get_digital_twin(pid)
        if twin:
            counts["DigitalTwin"] += 1
            nid = twin.get("twin_id")
            add_node(nid, "DigitalTwin", "Twin")
            add_edge(pid, nid, "HAS_TWIN")

        # Latest MRI scan
        scans = patient_store.get_all_scans(pid)
        counts["MRIScan"] += len(scans)
        for sc in list(reversed(scans))[:cap]:
            nid = sc.get("scan_id")
            add_node(nid, "MRIScan", "MRI")
            add_edge(pid, nid, "HAS_MRI")

    return {
        "nodes": nodes,
        "edges": edges,
        "counts": counts,
        "backend": patient_store.active_backend(),
        "shown_cap": cap,
    }
