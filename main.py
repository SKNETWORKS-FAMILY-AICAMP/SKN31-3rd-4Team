# main.py
from dotenv import load_dotenv
# 1. 최상단에서 환경 변수를 가장 먼저 로드합니다.
load_dotenv()

from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from builder import graph
from state import *

app = FastAPI()

class PatientInfo(BaseModel):
    name: str
    age: int
    gender: str
    is_pregnant: bool
    ingredient_code: str
    drug: str

class ChatRequest(BaseModel):
    query: str
    thread_id: str
    model: str
    patient_info: PatientInfo


@app.post("/chat")
async def chat(request: ChatRequest):
    # LangGraph 실행을 위한 config 설정
    config = {"configurable": {"thread_id": request.thread_id}}

    # 입력 상태(state) 구성
    state = {
        "messages": [HumanMessage(content=request.query)],
        "patient_info": request.patient_info.model_dump(),
    }
    
    # LangGraph 호출
    result = graph.invoke(state, config=config)

    # 응답 메시지 추출
    answer = result["messages"][-1].content
    return {"answer": answer, "model": request.model}