"""
Medical Graph (Drug-Disease-Paper) 커넥터.

권장 Neo4j 스키마 예시:
  (:Drug {name, class})
  (:Disease {name})
  (:SideEffect {name})
  (:Symptom {name, category})
  (:Paper {title, doi, year})

  (Drug)-[:TREATS]->(Disease)
  (Drug)-[:CAUSES_SIDE_EFFECT {frequency}]->(SideEffect)
  (Drug)-[:INTERACTS_WITH {severity}]->(Drug)
  (Drug)-[:REPORTED_IN]->(Paper)
  (SideEffect)-[:PRESENTS_AS]->(Symptom)
    # 부작용이 임상적으로 어떤 증상 형태로 나타나는지 매핑.
    # 환자가 보고한 증상(personal graph의 Symptom)과 복용 중인 약의 부작용을
    # 대조하기 위한 핵심 관계 (match_symptom_to_side_effect() 참고).

실제 DB 연결 방법:
  1. .env 에서 USE_MOCK_DB=false 로 변경
  2. MEDICAL_GRAPH_URI / USER / PASSWORD / DATABASE 값을 채움
  3. _run_real_query() 의 Cypher를 본인 스키마에 맞게 수정
  (참고: 개인 그래프와 동일 Neo4j 인스턴스를 쓰되 DATABASE만 분리해도 되고,
   완전히 별도의 Neo4j 인스턴스를 사용해도 됩니다.)
"""
from config import settings

# ---------------------------------------------------------------
# 목업 데이터
# ---------------------------------------------------------------
_MOCK_MEDICAL_GRAPH = {
    "에스시탈로프람": {
        "class": "SSRI",
        "treats": ["우울증", "범불안장애"],
        "side_effects": [
            {"name": "메스꺼움", "frequency": "흔함(10명 중 1명 이상)"},
            {"name": "두통", "frequency": "흔함"},
            {"name": "성기능장애", "frequency": "흔함"},
        ],
        "interacts_with": [
            {"drug": "졸피뎀", "severity": "낮음", "note": "중추신경계 억제 작용 중복 가능, 졸림 증가 주의"},
        ],
        "papers": [
            {"title": "SSRI 병용 시 수면제 상호작용에 대한 메타분석", "year": 2023},
        ],
    },
    "졸피뎀": {
        "class": "비벤조디아제핀계 수면제",
        "treats": ["불면증"],
        "side_effects": [
            {"name": "어지러움", "frequency": "흔함"},
            {"name": "몽유병 유사 행동", "frequency": "드묾"},
        ],
        "interacts_with": [
            {"drug": "에스시탈로프람", "severity": "낮음", "note": "졸림 증가 가능"},
        ],
        "papers": [
            {"title": "졸피뎀 장기 복용과 인지기능 변화 연구", "year": 2022},
        ],
    },
}


class MedicalGraphDB:
    def __init__(self):
        self.use_mock = settings.USE_MOCK_DB
        self._driver = None
        if not self.use_mock:
            self._connect_real()

    # ---------------- 실제 DB 연결부 ----------------
    def _connect_real(self):
        from neo4j import GraphDatabase
        self._driver = GraphDatabase.driver(
            settings.MEDICAL_GRAPH_URI,
            auth=(settings.MEDICAL_GRAPH_USER, settings.MEDICAL_GRAPH_PASSWORD),
        )

    def _run_real_query(self, entity_names: list[str]) -> dict:
        # TODO: 실제 스키마에 맞게 Cypher 수정
        cypher = """
        MATCH (d:Drug)
        WHERE any(name IN $names WHERE toLower(d.name) CONTAINS toLower(name))
        OPTIONAL MATCH (d)-[:TREATS]->(dis:Disease)
        OPTIONAL MATCH (d)-[:CAUSES_SIDE_EFFECT]->(se:SideEffect)
        OPTIONAL MATCH (d)-[:INTERACTS_WITH]->(d2:Drug)
        OPTIONAL MATCH (d)-[:REPORTED_IN]->(p:Paper)
        RETURN d.name AS drug, collect(DISTINCT dis.name) AS diseases,
               collect(DISTINCT se.name) AS side_effects,
               collect(DISTINCT d2.name) AS interactions,
               collect(DISTINCT p.title) AS papers
        LIMIT 50
        """
        with self._driver.session(database=settings.MEDICAL_GRAPH_DATABASE) as session:
            records = session.run(cypher, names=entity_names)
            return {"records": [r.data() for r in records]}

    def _run_symptom_match_query(self, drug_names: list[str], symptom_names: list[str]) -> list[dict]:
        # (:Drug)-[:CAUSES_SIDE_EFFECT]->(:SideEffect)-[:PRESENTS_AS]->(:Symptom)
        # 환자가 지금 먹는 약의 부작용이, 환자가 보고한 증상과 실제로 일치하는지 매칭
        cypher = """
        MATCH (d:Drug)-[ce:CAUSES_SIDE_EFFECT]->(se:SideEffect)-[:PRESENTS_AS]->(sym:Symptom)
        WHERE any(dn IN $drug_names WHERE toLower(d.name) CONTAINS toLower(dn))
          AND any(sn IN $symptom_names WHERE toLower(sym.name) CONTAINS toLower(sn)
                  OR toLower(sn) CONTAINS toLower(sym.name))
        RETURN d.name AS drug, se.name AS side_effect, ce.frequency AS frequency, sym.name AS symptom
        LIMIT 20
        """
        with self._driver.session(database=settings.MEDICAL_GRAPH_DATABASE) as session:
            records = session.run(cypher, drug_names=drug_names, symptom_names=symptom_names)
            return [r.data() for r in records]

    # ---------------- 공개 API ----------------
    def get_drug_subgraph(self, entity_names: list[str]) -> dict:
        if self.use_mock:
            return self._mock_query(entity_names)
        return self._run_real_query(entity_names)

    def match_symptom_to_side_effect(self, drug_names: list[str], symptom_names: list[str]) -> list[dict]:
        """환자가 복용 중인 약(drug_names)의 부작용 중, 환자가 보고한 증상(symptom_names)과
        일치하는 항목을 반환. 결과 각 항목: {drug, side_effect, frequency, symptom}"""
        if not drug_names or not symptom_names:
            return []
        if self.use_mock:
            return self._mock_symptom_match(drug_names, symptom_names)
        return self._run_symptom_match_query(drug_names, symptom_names)

    def _mock_symptom_match(self, drug_names: list[str], symptom_names: list[str]) -> list[dict]:
        lowered_symptoms = [s.lower() for s in symptom_names]
        matches = []
        for drug_name, info in _MOCK_MEDICAL_GRAPH.items():
            if not any(dn.lower() in drug_name.lower() or drug_name.lower() in dn.lower() for dn in drug_names):
                continue
            for se in info.get("side_effects", []):
                se_name = se["name"].lower()
                if any(se_name in sym or sym in se_name for sym in lowered_symptoms):
                    matches.append({
                        "drug": drug_name,
                        "side_effect": se["name"],
                        "frequency": se.get("frequency", "-"),
                        "symptom": se["name"],
                    })
        return matches

    def _mock_query(self, entity_names: list[str]) -> dict:
        result = {}
        for name in entity_names:
            for drug_name, info in _MOCK_MEDICAL_GRAPH.items():
                if name.lower() in drug_name.lower() or drug_name.lower() in name.lower():
                    result[drug_name] = info
        if not result and not entity_names:
            result = _MOCK_MEDICAL_GRAPH
        return result

    def close(self):
        if self._driver:
            self._driver.close()
