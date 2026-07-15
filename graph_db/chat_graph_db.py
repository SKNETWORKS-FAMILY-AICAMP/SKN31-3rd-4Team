"""
환자 정보(sidebar) + 채팅 기록(history)을 Neo4j 노드/관계로 저장.

스키마:
  (:Patient {id, name, age, gender, is_pregnant, ingredient_code, ...})
  (:Condition {name})
  (:ChatSession {id, started_at})
  (:Message {id, role, content, timestamp, turn_index})

  (Patient)-[:HAS_CONDITION]->(Condition)
  (Patient)-[:HAS_SESSION]->(ChatSession)
  (ChatSession)-[:STARTS_WITH]->(Message)          # 첫 메시지
  (Message)-[:NEXT]->(Message)                     # patient → assistant → patient → ...
  (Message:patient)-[:REPLIED_BY]->(Message:assistant)
  (Message:assistant)-[:FOLLOWED_BY]->(Message:patient)

.env 에서 USE_MOCK_DB=false 로 설정하면 실제 Neo4j에 기록됩니다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from config import settings

# ---------------------------------------------------------------------------
# Mock 저장소 (USE_MOCK_DB=true 일 때)
# ---------------------------------------------------------------------------
_MOCK_STORE: dict[str, Any] = {
    "patients": {},       # patient_id -> patient dict
    "sessions": {},       # session_id -> {patient_id, started_at, message_ids: []}
    "messages": {},       # msg_id -> message dict
    "session_starts": {}, # session_id -> first msg_id
    "message_next": {},   # msg_id -> next msg_id
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ChatGraphDB:
    """sidebar patient_info + app history → Neo4j nodes/relationships."""

    def __init__(self):
        self.use_mock = settings.USE_MOCK_DB
        self._driver = None
        if not self.use_mock:
            self._connect()

    def _connect(self) -> None:
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(
            settings.PERSONAL_GRAPH_URI,
            auth=(settings.PERSONAL_GRAPH_USER, settings.PERSONAL_GRAPH_PASSWORD),
        )

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    # ------------------------------------------------------------------
    # Patient (sidebar patient_info)
    # ------------------------------------------------------------------
    def upsert_patient(self, patient_info: dict) -> str:
        """환자 정보 저장/업데이트. patient_id 반환."""
        patient_id = patient_info.get("id") or _new_id("patient")
        payload = {
            "id": patient_id,
            "name": patient_info.get("name", ""),
            "age": int(patient_info.get("age", 0)),
            "gender": patient_info.get("gender", "선택 안함"),
            "is_pregnant": bool(patient_info.get("is_pregnant", False)),
            "ingredient_code": patient_info.get("ingredient_code", ""),
            "conditions": list(patient_info.get("conditions") or []),
            "updated_at": _now_iso(),
        }
        if self.use_mock:
            _MOCK_STORE["patients"][patient_id] = payload
            return patient_id
        return self._upsert_patient_real(payload)

    def _upsert_patient_real(self, payload: dict) -> str:
        base_cypher = """
        MERGE (p:Patient {id: $id})
        SET p.name = $name,
            p.age = $age,
            p.gender = $gender,
            p.is_pregnant = $is_pregnant,
            p.ingredient_code = $ingredient_code,
            p.updated_at = datetime($updated_at)
        WITH p
        OPTIONAL MATCH (p)-[r:HAS_CONDITION]->(:Condition)
        DELETE r
        RETURN p.id AS patient_id
        """
        cond_cypher = """
        MATCH (p:Patient {id: $id})
        UNWIND $conditions AS cond_name
        MERGE (c:Condition {name: cond_name})
        MERGE (p)-[:HAS_CONDITION]->(c)
        """
        params = {
            "id": payload["id"],
            "name": payload["name"],
            "age": payload["age"],
            "gender": payload["gender"],
            "is_pregnant": payload["is_pregnant"],
            "ingredient_code": payload["ingredient_code"],
            "updated_at": payload["updated_at"],
        }
        with self._driver.session(database=settings.PERSONAL_GRAPH_DATABASE) as session:
            record = session.run(base_cypher, **params).single()
            conditions = [c for c in payload["conditions"] if c]
            if conditions:
                session.run(cond_cypher, id=payload["id"], conditions=conditions)
            return record["patient_id"]

    # ------------------------------------------------------------------
    # Chat Session
    # ------------------------------------------------------------------
    def create_session(self, patient_id: str) -> str:
        """새 채팅 세션 생성. session_id 반환."""
        session_id = _new_id("session")
        if self.use_mock:
            _MOCK_STORE["sessions"][session_id] = {
                "id": session_id,
                "patient_id": patient_id,
                "started_at": _now_iso(),
                "message_ids": [],
            }
            return session_id
        return self._create_session_real(patient_id, session_id)

    def _create_session_real(self, patient_id: str, session_id: str) -> str:
        cypher = """
        MATCH (p:Patient {id: $patient_id})
        CREATE (s:ChatSession {id: $session_id, started_at: datetime()})
        CREATE (p)-[:HAS_SESSION]->(s)
        RETURN s.id AS session_id
        """
        with self._driver.session(database=settings.PERSONAL_GRAPH_DATABASE) as session:
            record = session.run(
                cypher, patient_id=patient_id, session_id=session_id
            ).single()
            return record["session_id"]

    # ------------------------------------------------------------------
    # Messages (patient ↔ assistant chain)
    # ------------------------------------------------------------------
    def append_message(
        self, session_id: str, role: str, content: str, turn_index: int
    ) -> str:
        """
        메시지를 세션 체인에 추가.
        role: 'patient' | 'assistant'
        관계: patient -[:REPLIED_BY]-> assistant -[:FOLLOWED_BY]-> patient ...
        """
        msg_id = _new_id("msg")
        msg = {
            "id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": _now_iso(),
            "turn_index": turn_index,
        }
        if self.use_mock:
            return self._append_message_mock(session_id, msg)
        return self._append_message_real(session_id, msg)

    def _append_message_mock(self, session_id: str, msg: dict) -> str:
        msg_id = msg["id"]
        _MOCK_STORE["messages"][msg_id] = msg
        sess = _MOCK_STORE["sessions"].get(session_id)
        if not sess:
            raise ValueError(f"Unknown session: {session_id}")
        sess["message_ids"].append(msg_id)

        if session_id not in _MOCK_STORE["session_starts"]:
            _MOCK_STORE["session_starts"][session_id] = msg_id
        else:
            # 이전 tail 찾기
            start_id = _MOCK_STORE["session_starts"][session_id]
            tail_id = start_id
            while tail_id in _MOCK_STORE["message_next"]:
                tail_id = _MOCK_STORE["message_next"][tail_id]
            prev = _MOCK_STORE["messages"][tail_id]
            _MOCK_STORE["message_next"][tail_id] = msg_id
            # 역할별 관계 기록
            if prev["role"] == "patient" and msg["role"] == "assistant":
                _MOCK_STORE.setdefault("replied_by", {})[tail_id] = msg_id
            elif prev["role"] == "assistant" and msg["role"] == "patient":
                _MOCK_STORE.setdefault("followed_by", {})[tail_id] = msg_id
        return msg_id

    def _append_message_real(self, session_id: str, msg: dict) -> str:
        cypher = """
        MATCH (s:ChatSession {id: $session_id})
        OPTIONAL MATCH (s)-[:STARTS_WITH]->(start:Message)
        OPTIONAL MATCH path = (start)-[:NEXT*]->(tail:Message)
        WHERE NOT (tail)-[:NEXT]->()
        WITH s, COALESCE(tail, start) AS last_msg, start
        CREATE (m:Message {
            id: $msg_id,
            role: $role,
            content: $content,
            timestamp: datetime($timestamp),
            turn_index: $turn_index
        })
        FOREACH (_ IN CASE WHEN start IS NULL THEN [1] ELSE [] END |
            CREATE (s)-[:STARTS_WITH]->(m)
        )
        FOREACH (_ IN CASE WHEN last_msg IS NOT NULL THEN [1] ELSE [] END |
            CREATE (last_msg)-[:NEXT]->(m)
        )
        FOREACH (_ IN CASE WHEN last_msg IS NOT NULL AND last_msg.role = 'patient' AND $role = 'assistant' THEN [1] ELSE [] END |
            CREATE (last_msg)-[:REPLIED_BY]->(m)
        )
        FOREACH (_ IN CASE WHEN last_msg IS NOT NULL AND last_msg.role = 'assistant' AND $role = 'patient' THEN [1] ELSE [] END |
            CREATE (last_msg)-[:FOLLOWED_BY]->(m)
        )
        RETURN m.id AS msg_id
        """
        with self._driver.session(database=settings.PERSONAL_GRAPH_DATABASE) as session:
            record = session.run(
                cypher,
                session_id=session_id,
                msg_id=msg["id"],
                role=msg["role"],
                content=msg["content"],
                timestamp=msg["timestamp"],
                turn_index=msg["turn_index"],
            ).single()
            return record["msg_id"]

    def get_chat_history(self, session_id: str) -> list[dict]:
        """세션의 메시지 체인을 turn_index 순으로 반환."""
        if self.use_mock:
            return self._get_history_mock(session_id)
        return self._get_history_real(session_id)

    def _get_history_mock(self, session_id: str) -> list[dict]:
        start_id = _MOCK_STORE["session_starts"].get(session_id)
        if not start_id:
            return []
        result = []
        current = start_id
        while current:
            msg = _MOCK_STORE["messages"][current]
            result.append({"role": msg["role"], "content": msg["content"]})
            current = _MOCK_STORE["message_next"].get(current)
        return result

    def _get_history_real(self, session_id: str) -> list[dict]:
        cypher = """
        MATCH (s:ChatSession {id: $session_id})-[:STARTS_WITH]->(first:Message)
        OPTIONAL MATCH path = (first)-[:NEXT*0..]->(m:Message)
        WITH m ORDER BY m.turn_index
        RETURN m.role AS role, m.content AS content
        """
        with self._driver.session(database=settings.PERSONAL_GRAPH_DATABASE) as session:
            records = session.run(cypher, session_id=session_id)
            return [{"role": r["role"], "content": r["content"]} for r in records]

    def get_session_graph(self, session_id: str) -> dict:
        """세션의 nodes + relationships (시각화/디버그용)."""
        if self.use_mock:
            return self._get_session_graph_mock(session_id)
        return self._get_session_graph_real(session_id)

    def _get_session_graph_mock(self, session_id: str) -> dict:
        sess = _MOCK_STORE["sessions"].get(session_id, {})
        patient_id = sess.get("patient_id")
        patient = _MOCK_STORE["patients"].get(patient_id, {})
        nodes = []
        relationships = []

        if patient:
            nodes.append({"label": "Patient", **{k: v for k, v in patient.items() if k != "conditions"}})
            for cond in patient.get("conditions", []):
                nodes.append({"label": "Condition", "name": cond})
                relationships.append({
                    "from": patient_id, "to": cond,
                    "type": "HAS_CONDITION",
                })

        if sess:
            nodes.append({"label": "ChatSession", "id": session_id, "started_at": sess.get("started_at")})
            if patient_id:
                relationships.append({"from": patient_id, "to": session_id, "type": "HAS_SESSION"})

        start_id = _MOCK_STORE["session_starts"].get(session_id)
        prev_id = None
        current = start_id
        while current:
            msg = _MOCK_STORE["messages"][current]
            nodes.append({"label": "Message", **msg})
            if prev_id is None:
                relationships.append({"from": session_id, "to": current, "type": "STARTS_WITH"})
            else:
                prev_msg = _MOCK_STORE["messages"][prev_id]
                relationships.append({"from": prev_id, "to": current, "type": "NEXT"})
                if prev_msg["role"] == "patient" and msg["role"] == "assistant":
                    relationships.append({"from": prev_id, "to": current, "type": "REPLIED_BY"})
                elif prev_msg["role"] == "assistant" and msg["role"] == "patient":
                    relationships.append({"from": prev_id, "to": current, "type": "FOLLOWED_BY"})
            prev_id = current
            current = _MOCK_STORE["message_next"].get(current)

        return {"nodes": nodes, "relationships": relationships}

    def _get_session_graph_real(self, session_id: str) -> dict:
        cypher = """
        MATCH (s:ChatSession {id: $session_id})
        OPTIONAL MATCH (p:Patient)-[:HAS_SESSION]->(s)
        OPTIONAL MATCH (p)-[:HAS_CONDITION]->(c:Condition)
        OPTIONAL MATCH (s)-[:STARTS_WITH]->(first:Message)
        OPTIONAL MATCH path = (first)-[:NEXT*0..]->(m:Message)
        OPTIONAL MATCH (m)-[r:NEXT|REPLIED_BY|FOLLOWED_BY]->(m2:Message)
        RETURN p, collect(DISTINCT c) AS conditions, s,
               collect(DISTINCT m) AS messages,
               collect(DISTINCT {type: type(r), from: m.id, to: m2.id}) AS msg_rels
        """
        with self._driver.session(database=settings.PERSONAL_GRAPH_DATABASE) as session:
            record = session.run(cypher, session_id=session_id).single()
            if not record:
                return {"nodes": [], "relationships": []}

            nodes = []
            relationships = []
            p = record["p"]
            if p:
                nodes.append({"label": "Patient", **dict(p)})
                for c in record["conditions"]:
                    if c:
                        nodes.append({"label": "Condition", "name": c["name"]})
                        relationships.append({
                            "from": p["id"], "to": c["name"], "type": "HAS_CONDITION",
                        })
                s = record["s"]
                if s:
                    nodes.append({"label": "ChatSession", **dict(s)})
                    relationships.append({"from": p["id"], "to": s["id"], "type": "HAS_SESSION"})

            for m in record["messages"]:
                if m:
                    nodes.append({"label": "Message", **dict(m)})

            for rel in record["msg_rels"]:
                if rel and rel.get("type"):
                    relationships.append(rel)

            return {"nodes": nodes, "relationships": relationships}
