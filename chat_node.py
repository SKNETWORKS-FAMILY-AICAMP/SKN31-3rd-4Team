from langchain_openai import ChatOpenAI
from state import State,RouteResult
from qdrant_loader import retriever

llm = ChatOpenAI(model="gpt-5.4-mini")
router_llm = llm.with_structured_output(RouteResult)


def chat_node(state: State):
    result = router_llm.invoke(state["messages"])
    return {
        "need_medicine": result.need_medicine,
    }


def router(state: State):
    if state["need_medicine"]:
        return "medicine_node"
    return "general_chat_node"

def entry_router(state: State):
    if state.get("symptom_followup"):
        return "side_effect_followup_node"
    return "chat_node"



def medicine_node(state: State):

    if not state.get("patient_info", {}).get("ingredient_code"):
        return {"medicine_side_effect": None}

    # 사용자 메시지에서 최근 질문 내용을 쿼리에 반영
    last_message = state["messages"][-1].content if state["messages"] else ""
    query = f"부작용 및 주의사항: {last_message}"

    medicine_side_effect = retriever(
        query=query,
        ingredient_code=state["patient_info"]["ingredient_code"]
    )

    return {
        "medicine_side_effect": medicine_side_effect
    }




def side_effect_node(state: State):
    medicine_side_effect = state.get("medicine_side_effect")
    if not medicine_side_effect:
        return {}

    prompt = f"""
    # Context
    - 전체 대화 이력: {state["messages"]}
    - 복용 중인 약: {state['patient_info']['drug']}
    - 이전에 조회된 부작용 정보: {state["medicine_side_effect"]}
    - 환자 정보
        - 이름: {state['patient_info']['name']}
        - 나이: {state['patient_info']['age']}
        - 성별: {state['patient_info']['gender']}
        - 임신 여부: {state['patient_info']['is_pregnant']}

    Role
    당신은 약물 부작용 분석 전문 어시스턴트다.

    Constraints
    반드시 "조회된 부작용 정보"에 있는 내용만 근거로 요약과정을 진행한후 판단을 시작한다.
    정보가 없거나 비어있으면 "죄송하지만 다른 증상을 알려 주실 수 있으신가요?"라고만 답한다.
    사용자와 대화를 이어갈 수 있는 느낌으로 부작용을 설명하거나 물어보면서 대답한다.
    약때문인지 다른원인인지에 대한 판단은 하지 않는다. 또 이와 관련된 대답도 하지 않는다.
    Output Format
    복용 중인 약: {state['patient_info']['drug']}
    """
    response = llm.invoke(prompt)

    return {
        "messages": [response],
        "checklist_index": -1,      
        "checked_symptoms": [],
        "symptom_followup": True,
    }


CRITERIA_ORDER = [
    "onset_timing",         # 증상 시작 시점
    "dechallenge",           # 약 끊으면 호전되는지
    "alternative_causes",   # 다른 원인 가능성
    "prior_reaction",        # 과거 유사 반응 이력
]

CRITERIA_QUESTIONS = {
    "onset_timing": "증상이 약 복용 시점과 비교했을 때 언제부터 시작되었나요?",
    "dechallenge": "약을 끊거나 줄였을 때 증상이 좋아지셨나요?",
    "alternative_causes": "이 증상을 설명할 수 있는 다른 원인(다른 약, 질환 등)이 있으신가요?",
    "prior_reaction": "예전에 이 약이나 비슷한 약을 드셨을 때도 비슷한 반응이 있었나요?",
}

def side_effect_followup_node(state: State):
    idx = state["checklist_index"]
    last_user_answer = state["messages"][-1].content

    if idx == -1:
        # side_effect_node의 자유 질문에 대한 답변 -> 일반 증상으로 기록, 인과성 항목 초기화
        checked = state["checked_symptoms"] + [{"symptom": "일반 증상", "answer": last_user_answer}]
        criteria_status = {k: None for k in CRITERIA_ORDER}
    else:
        checked = state["checked_symptoms"]
        key = CRITERIA_ORDER[idx]
        criteria_status = {**state["criteria_status"], key: last_user_answer}

    idx += 1
    is_last = idx >= len(CRITERIA_ORDER)

    if is_last:
        closing_prompt = f"""
    지금까지 확인된 내용
    - 증상 응답: {checked}
    - 인과성 판정 항목: {criteria_status}
    복용 중인 약: {state['patient_info']['drug']}
    조회된 부작용 정보: {state['medicine_side_effect']}

    약물 부작용 분석 어시스턴트로서, 지금까지 확인한 내용을 종합해서 요약 안내하고 대화를 마무리한다.
    인과성에 대한 최종 판단(약 때문인지 아닌지)은 하지 않는다. 또 이와 관련된 응답도 하지 않는다.
    """
        response = llm.invoke(closing_prompt)
        return {
            "messages": [response],
            "checked_symptoms": checked,
            "criteria_status": criteria_status,
            "checklist_index": idx,
            "symptom_followup": False,
        }

    next_key = CRITERIA_ORDER[idx]
    next_question = CRITERIA_QUESTIONS[next_key]
    prompt = f"""
    `# Context
    `- 전체 대화 이력: {state["messages"]}
    `- 복용 중인 약: {state['patient_info']['drug']}
    `- 이전에 조회된 부작용 정보: {state["medicine_side_effect"]}
    `
    `# Role
    `당신은 약물 부작용 인과성 평가를 돕는 어시스턴트다.
    `
    `# Next Step
    `사용자의 방금 답변에 자연스럽게 반응한 뒤, 다음 질문을 이어서 물어봐줘:
    `"{next_question}"
    `
    `# Constraints
    `1. 인과성에 대한 최종 판단(약 때문인지 아닌지)은 하지 않고 이와 관련된 답변도 하지 않는다.
    `2. 대화를 자연스럽게 이어가는 톤을 유지한다.
    `"""
    response = llm.invoke(prompt)
    return {
        "messages": [response],
        "checked_symptoms": checked,
        "criteria_status": criteria_status,
        "checklist_index": idx,
        "symptom_followup": True,
    }


def general_chat_node(state: State):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}
