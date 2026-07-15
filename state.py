from typing import TypedDict , Annotated
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages

class PatientInfo(TypedDict):
    name: str
    age: int
    gender: str
    is_pregnant: bool
    ingredient_code: str
    drug: str | None

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    need_medicine: bool
    medicine_side_effect: dict | None
    patient_info: PatientInfo
    symptom_followup: bool
    checklist_index: int
    checked_symptoms: list[dict]
    criteria_status: dict[str, str | None] 

class RouteResult(BaseModel):
    need_medicine: bool = Field(
        description="약에 대한 정보 조회가 필요한지 알려줘"
    )