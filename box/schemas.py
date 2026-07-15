"""
LLM Entity/Relation Extraction 및 상태 관리를 위한 Pydantic 스키마.
기술스택 표의 'Entity Extraction: Structured Output(Pydantic)'에 해당.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


EntityType = Literal[
    "drug",        # 약물명 (예: 세로토닌 재흡수 억제제, 졸피뎀 등)
    "disease",     # 진단명 (예: 우울증, 불안장애)
    "symptom",     # 증상 (예: 불면, 두통, 메스꺼움)
    "dosage",      # 용량/용법 (예: 20mg, 하루 1회)
    "side_effect", # 부작용
    "lab_value",   # 검사 수치
    "other",
]

RelationLabel = Literal[
    "TAKES",            # 환자 -TAKES-> 약물
    "HAS_SYMPTOM",       # 환자 -HAS_SYMPTOM-> 증상
    "DIAGNOSED_WITH",    # 환자 -DIAGNOSED_WITH-> 질병
    "CAUSES_SIDE_EFFECT",# 약물 -CAUSES_SIDE_EFFECT-> 부작용
    "TREATS",            # 약물 -TREATS-> 질병
    "INTERACTS_WITH",    # 약물 -INTERACTS_WITH-> 약물
    "REPORTED_IN",       # 관계 -REPORTED_IN-> 논문
]


class Entity(BaseModel):
    name: str = Field(description="개체명 (예: 에스시탈로프람, 불면증)")
    type: EntityType


class Relation(BaseModel):
    source: str
    relation: RelationLabel
    target: str


class ExtractionResult(BaseModel):
    """LLM Entity / Relation Extraction 노드의 구조화 출력."""
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    intent: Literal[
        "medication_question",   # 복용법/용량 문의
        "side_effect_report",    # 부작용 보고
        "symptom_report",        # 증상 보고
        "adherence_check",       # 복약 순응도 확인
        "general_question",      # 일반 질문
        "emergency",             # 응급 상황 의심
    ] = "general_question"
    urgency: Literal["low", "medium", "high"] = "low"


class Citation(BaseModel):
    source_graph: Literal["personal", "medical", "vector"]
    node_or_doc: str
    snippet: Optional[str] = None

# 환자 정보 필드 추가
class PatientInfo(BaseModel):
    name: str = ""
    age: int = 0
    gender: str = "선택 안함"
    is_pregnant: bool = False
    conditions: list[str] = Field(default_factory=list)
    ingredient_code: str = ""

class ChatState(BaseModel):
    """LangGraph 전체에서 공유되는 상태 객체."""
    user_role: Literal["patient", "doctor"] = "patient"
    user_input: str = ""
    history: list[dict] = Field(default_factory=list)

    extraction: Optional[ExtractionResult] = None

    personal_subgraph: dict = Field(default_factory=dict)
    medical_subgraph: dict = Field(default_factory=dict)
    merged_context: str = ""
    citations: list[Citation] = Field(default_factory=list)

    answer: str = ""
    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    
    class Config:
        arbitrary_types_allowed = True
    
