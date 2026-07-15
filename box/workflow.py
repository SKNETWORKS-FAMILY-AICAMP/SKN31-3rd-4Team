"""
LangGraph 워크플로우.

아키텍처(이미지1) 그대로 구현:
사용자 자연어 건강기록 입력
   -> LLM Entity/Relation Extraction
        -> Dynamic Personal Graph(PGHD)  \
        -> Medical Graph(Drug-Disease-Paper) -> Graph Retriever -> 관련 Subgraph 생성
   -> LLM -> Explainable Personalized Answer
"""
from langgraph.graph import StateGraph, END

from box.schemas import ChatState
from box.llm_client import extract_entities, generate_answer
from box.personal_graph_db import PersonalGraphDB
from box.medical_graph_db import MedicalGraphDB
from box.vector_db import VectorDB
from box.retriever import HybridRetriever


def build_workflow(patient_id: str = "patient_001"):
    personal_db = PersonalGraphDB(patient_id=patient_id)
    medical_db = MedicalGraphDB()
    vector_db = VectorDB()
    retriever = HybridRetriever.__new__(HybridRetriever)  # 인스턴스는 db들을 재사용
    retriever.personal_db = personal_db
    retriever.medical_db = medical_db
    retriever.vector_db = vector_db

    # ---------------- 노드 정의 ----------------
    def entity_extraction_node(state: ChatState) -> dict:
        extraction = extract_entities(state.user_input, state.user_role)
        return {"extraction": extraction}

    def personal_graph_node(state: ChatState) -> dict:
        names = [e.name for e in state.extraction.entities] if state.extraction else []
        subgraph = personal_db.get_patient_subgraph(names)
        return {"personal_subgraph": subgraph}

    def medical_graph_node(state: ChatState) -> dict:
        names = [e.name for e in state.extraction.entities] if state.extraction else []
        subgraph = medical_db.get_drug_subgraph(names)
        return {"medical_subgraph": subgraph}

    def merge_subgraph_node(state: ChatState) -> dict:
        vector_hits = vector_db.search(state.user_input, top_k=3)

        # 현재 복용 중인 약(personal graph) x 이번 발화에서 새로 언급된 증상(entity extraction) 매칭
        drug_names = [d["name"] for d in state.personal_subgraph.get("drugs", [])]
        symptom_names = [
            e.name for e in (state.extraction.entities if state.extraction else [])
            if e.type == "symptom"
        ]
        side_effect_matches = medical_db.match_symptom_to_side_effect(drug_names, symptom_names)

        context_text, citations = retriever._merge_to_context(
            state.personal_subgraph, state.medical_subgraph, vector_hits, side_effect_matches
        )
        return {"merged_context": context_text, "citations": citations}

    def generate_answer_node(state: ChatState) -> dict:
        answer = generate_answer(
            user_input=state.user_input,
            user_role=state.user_role,
            context=state.merged_context,
            history=state.history,
        )
        return {"answer": answer}

    # ---------------- 그래프 구성 ----------------
    graph = StateGraph(ChatState)
    graph.add_node("entity_extraction", entity_extraction_node)
    graph.add_node("personal_graph", personal_graph_node)
    graph.add_node("medical_graph", medical_graph_node)
    graph.add_node("merge_subgraph", merge_subgraph_node)
    graph.add_node("generate_answer", generate_answer_node)

    graph.set_entry_point("entity_extraction")
    # 이미지 아키텍처대로 personal / medical 그래프를 병렬 조회 후 merge에서 합류
    graph.add_edge("entity_extraction", "personal_graph")
    graph.add_edge("entity_extraction", "medical_graph")
    graph.add_edge("personal_graph", "merge_subgraph")
    graph.add_edge("medical_graph", "merge_subgraph")
    graph.add_edge("merge_subgraph", "generate_answer")
    graph.add_edge("generate_answer", END)

    compiled = graph.compile()
    compiled._dbs = (personal_db, medical_db, vector_db)  # 종료 시 close용 참조 보관
    return compiled


def close_workflow(compiled):
    for db in getattr(compiled, "_dbs", []):
        db.close()
