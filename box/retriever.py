"""
Graph Retriever -> 관련 Subgraph 생성 노드.
Personal Graph + Medical Graph 결과를 Vector 검색으로 보강하는 하이브리드 리트리버.
"""
from box.schemas import ExtractionResult, Citation
from box.personal_graph_db import PersonalGraphDB
from box.medical_graph_db import MedicalGraphDB
from box.vector_db import VectorDB


class HybridRetriever:
    def __init__(self, patient_id: str = "patient_001"):
        self.personal_db = PersonalGraphDB(patient_id=patient_id)
        self.medical_db = MedicalGraphDB()
        self.vector_db = VectorDB()

    def retrieve(self, user_input: str, extraction: ExtractionResult):
        entity_names = [e.name for e in extraction.entities]

        personal_subgraph = self.personal_db.get_patient_subgraph(entity_names)
        medical_subgraph = self.medical_db.get_drug_subgraph(entity_names)
        vector_hits = self.vector_db.search(user_input, top_k=3)

        context_text, citations = self._merge_to_context(personal_subgraph, medical_subgraph, vector_hits)
        return personal_subgraph, medical_subgraph, context_text, citations

    def _merge_to_context(
        self,
        personal_subgraph: dict,
        medical_subgraph: dict,
        vector_hits: list[dict],
        side_effect_matches: list[dict] | None = None,
    ):
        lines = []
        citations: list[Citation] = []

        if side_effect_matches:
            lines.append("[⚠️ 증상-부작용 매칭 - 복용 중인 약의 알려진 부작용과 일치]")
            for m in side_effect_matches:
                lines.append(
                    f"- 보고하신 '{m['symptom']}' 증상은 현재 복용 중인 '{m['drug']}'의 "
                    f"알려진 부작용 '{m['side_effect']}'(빈도: {m.get('frequency','-')})과 일치할 수 있습니다."
                )
                citations.append(
                    Citation(
                        source_graph="medical",
                        node_or_doc=f"{m['drug']} → {m['side_effect']}",
                        snippet=f"보고 증상 '{m['symptom']}'과 매칭",
                    )
                )

        if personal_subgraph:
            lines.append("[개인 그래프(PGHD) - 환자 복약/증상 이력]")
            for d in personal_subgraph.get("drugs", []):
                lines.append(f"- 복용 중: {d['name']} ({d.get('dose','-')}, {d.get('since','-')} 부터)")
                citations.append(Citation(source_graph="personal", node_or_doc=d["name"]))
            for s in personal_subgraph.get("symptoms", []):
                lines.append(f"- 보고 증상: {s['name']} ({s.get('date','-')}, 심각도 {s.get('severity','-')})")
                citations.append(Citation(source_graph="personal", node_or_doc=s["name"]))
            for se in personal_subgraph.get("side_effects_reported", []):
                lines.append(f"- 보고 부작용: {se['name']} (관련 약물: {se.get('drug','-')})")
                citations.append(Citation(source_graph="personal", node_or_doc=se["name"]))

        if medical_subgraph:
            lines.append("\n[의학 그래프 - 약물/질병/논문 근거]")
            for drug_name, info in medical_subgraph.items():
                lines.append(f"- {drug_name} ({info.get('class','-')}): 치료 대상 = {', '.join(info.get('treats', []))}")
                for se in info.get("side_effects", []):
                    lines.append(f"  · 부작용: {se['name']} ({se.get('frequency','-')})")
                for inter in info.get("interacts_with", []):
                    lines.append(f"  · 상호작용: {inter['drug']} (심각도 {inter.get('severity','-')}) - {inter.get('note','')}")
                for p in info.get("papers", []):
                    lines.append(f"  · 근거 논문: {p.get('title')} ({p.get('year')})")
                    citations.append(Citation(source_graph="medical", node_or_doc=p.get("title", drug_name)))

        if vector_hits:
            lines.append("\n[Vector 검색 - 관련 문헌 스니펫]")
            for hit in vector_hits:
                lines.append(f"- ({hit['source']}) {hit['text']}")
                citations.append(Citation(source_graph="vector", node_or_doc=hit["source"], snippet=hit["text"]))

        return "\n".join(lines), citations

    def close(self):
        self.personal_db.close()
        self.medical_db.close()
