"""
LLM 호출을 담당하는 모듈.
- extract_entities(): LLM Entity/Relation Extraction 노드 (Structured Output/Pydantic)
- generate_answer(): 최종 Explainable Personalized Answer 생성 노드

LLM_PROVIDER=openai  -> GPT-5.5 (기술스택 표 권장안)
LLM_PROVIDER=anthropic -> Claude (대체 옵션)
"""
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings
from state import ExtractionResult


def get_llm(temperature: float = 0.2):
    """설정된 provider에 맞는 LangChain ChatModel을 반환."""
    if settings.LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
        )
    elif settings.LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=temperature,
        )
    else:
        raise ValueError(f"지원하지 않는 LLM_PROVIDER: {settings.LLM_PROVIDER}")


EXTRACTION_SYSTEM_PROMPT = """\
당신은 정신과 진료 도메인 전문 정보 추출기입니다.
환자 또는 의사가 입력한 자연어 건강 기록/대화에서 다음을 추출하세요:
1. entities: 약물(drug), 진단명(disease), 증상(symptom), 용량(dosage), 부작용(side_effect), 검사수치(lab_value)
2. relations: 개체 간 관계 (예: 환자-TAKES->약물, 약물-CAUSES_SIDE_EFFECT->부작용)
3. intent: 발화 의도 분류
4. urgency: 자해/자살 언급, 심각한 부작용(호흡곤란, 의식저하 등) 등 응급 신호가 있으면 반드시 high로 설정

의학적으로 부정확한 추정은 하지 말고, 텍스트에 실제로 언급된 내용만 추출하세요.
"""


def extract_entities(user_input: str, user_role: str) -> ExtractionResult:
    """자연어 입력 -> 구조화된 엔티티/관계 추출 (Pydantic Structured Output)."""
    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(ExtractionResult)
    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=f"[화자: {user_role}]\n{user_input}"),
    ]
    result = structured_llm.invoke(messages)
    return result


ANSWER_SYSTEM_PROMPT_PATIENT = """\
당신은 친절하고 신뢰할 수 있는 정신과 복약 관리 도우미입니다.
환자에게 답변할 때는:
- 쉬운 말로, 따뜻하고 공감하는 톤으로 설명하세요.
- 제공된 개인 그래프(PGHD)와 의학 그래프(약물-질병-논문) 근거만 사용하세요. 근거에 없는 내용은 추측하지 마세요.
- 컨텍스트에 "[⚠️ 증상-부작용 매칭]" 섹션이 있다면, 환자가 보고한 증상이 복용 중인 약의 알려진 부작용일 수 있음을
  반드시 답변 앞부분에서 명확히 언급하세요.
- 답변 끝에는 반드시 "이 정보는 참고용이며, 실제 처방 변경은 반드시 담당 의사와 상담하세요." 안내를 포함하세요.
- 응급 신호(자해, 심각한 부작용 등)가 감지되면 즉시 도움을 구하도록 안내하세요.
"""

ANSWER_SYSTEM_PROMPT_DOCTOR = """\
당신은 정신과 의사를 보조하는 임상 의사결정 지원 도우미입니다.
- 환자의 개인 그래프(복약 이력, 증상 추이)와 의학 그래프(약물 상호작용, 최신 논문 근거)를 근거로 간결하고 임상적으로 답하세요.
- 가능하면 근거가 된 출처(그래프 노드/논문)를 함께 제시하세요.
- 최종 처방 결정은 의사의 판단임을 명시하세요.
"""


def generate_answer(user_input: str, user_role: str, context: str, history: list[dict]) -> str:
    """관련 subgraph 컨텍스트를 바탕으로 설명 가능한 개인화 답변 생성."""
    llm = get_llm(temperature=0.4)
    system_prompt = ANSWER_SYSTEM_PROMPT_PATIENT if user_role == "patient" else ANSWER_SYSTEM_PROMPT_DOCTOR

    history_text = "\n".join(f"{h['role']}: {h['content']}" for h in history[-6:])

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"[대화 이력]\n{history_text}\n\n"
                f"[검색된 관련 subgraph 근거]\n{context}\n\n"
                f"[현재 질문 ({user_role})]\n{user_input}"
            )
        ),
    ]
    response = llm.invoke(messages)
    return response.content
