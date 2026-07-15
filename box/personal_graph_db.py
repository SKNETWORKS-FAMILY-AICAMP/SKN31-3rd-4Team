"""
Dynamic Personal Graph (PGHD: Patient Generated Health Data) 커넥터.

권장 Neo4j 스키마 예시:
  (:Patient {id, name})
  (:Drug {name})
  (:Symptom {name})
  (:SideEffect {name})
  (:Visit {date, note})

  (Patient)-[:TAKES {since, dose}]->(Drug)
  (Patient)-[:HAS_SYMPTOM {date, severity}]->(Symptom)
  (Patient)-[:REPORTED {date}]->(SideEffect)
  (Drug)-[:CAUSED {date}]->(SideEffect)

실제 DB 연결 방법:
  1. .env 에서 USE_MOCK_DB=false 로 변경
  2. PERSONAL_GRAPH_URI / USER / PASSWORD / DATABASE 값을 실제 Neo4j 접속 정보로 채움
  3. 아래 _run_real_query() 의 Cypher를 본인 스키마에 맞게 수정
"""
from config import settings

# ---------------------------------------------------------------
# 목업(mock) 데이터 — 실제 DB가 준비되기 전까지 데모용으로 사용
# ---------------------------------------------------------------
_MOCK_PATIENTS = {
    "patient_001": {
        "name": "김OO",
        "drugs": [
            {"name": "에스시탈로프람", "dose": "10mg", "since": "2025-03-01"},
            {"name": "졸피뎀", "dose": "5mg", "since": "2025-05-10"},
        ],
        "symptoms": [
            {"name": "불면", "date": "2025-06-01", "severity": "중등도"},
            {"name": "식욕저하", "date": "2025-06-15", "severity": "경도"},
        ],
        "side_effects_reported": [
            {"name": "메스꺼움", "date": "2025-06-03", "drug": "에스시탈로프람"},
        ],
    }
}


class PersonalGraphDB:
    def __init__(self, patient_id: str = "patient_001"):
        self.patient_id = patient_id
        self.use_mock = settings.USE_MOCK_DB
        self._driver = None
        if not self.use_mock:
            self._connect_real()

    # ---------------- 실제 DB 연결부 ----------------
    def _connect_real(self):
        from neo4j import GraphDatabase
        self._driver = GraphDatabase.driver(
            settings.PERSONAL_GRAPH_URI,
            auth=(settings.PERSONAL_GRAPH_USER, settings.PERSONAL_GRAPH_PASSWORD),
        )

    def _run_real_query(self, entity_names: list[str]) -> dict:
        # TODO: 실제 스키마에 맞게 Cypher 수정
        cypher = """
        MATCH (p:Patient {id: $patient_id})-[r]->(n)
        WHERE any(name IN $names WHERE toLower(n.name) CONTAINS toLower(name))
           OR size($names) = 0
        RETURN type(r) AS relation, n.name AS target, labels(n) AS labels, r AS rel_props
        LIMIT 50
        """
        with self._driver.session(database=settings.PERSONAL_GRAPH_DATABASE) as session:
            records = session.run(cypher, patient_id=self.patient_id, names=entity_names)
            return {"records": [r.data() for r in records]}

    # ---------------- 공개 API ----------------
    def get_patient_subgraph(self, entity_names: list[str] | None = None) -> dict:
        """엔티티 이름 리스트와 관련된 개인 그래프(PGHD) 서브그래프를 반환."""
        entity_names = entity_names or []
        if self.use_mock:
            return self._mock_query(entity_names)
        return self._run_real_query(entity_names)

    def _mock_query(self, entity_names: list[str]) -> dict:
        patient = _MOCK_PATIENTS.get(self.patient_id, {})
        if not entity_names:
            return patient
        # 간단한 부분 문자열 매칭으로 관련 항목만 필터링
        lowered = [e.lower() for e in entity_names]

        def match(name: str) -> bool:
            return any(l in name.lower() or name.lower() in l for l in lowered)

        return {
            "name": patient.get("name"),
            "drugs": [d for d in patient.get("drugs", []) if match(d["name"])] or patient.get("drugs", []),
            "symptoms": [s for s in patient.get("symptoms", []) if match(s["name"])] or patient.get("symptoms", []),
            "side_effects_reported": [
                s for s in patient.get("side_effects_reported", []) if match(s["name"])
            ] or patient.get("side_effects_reported", []),
        }

    def close(self):
        if self._driver:
            self._driver.close()
