from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from builder import graph

load_dotenv()
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
    config = {"configurable": {"thread_id": request.thread_id}}

    state = {
        "messages": [HumanMessage(content=request.query)],
        "patient_info": request.patient_info.model_dump(),
    }
    result = graph.invoke(state, config=config)

    answer = result["messages"][-1].content
    return {"answer": answer, "model": request.model}