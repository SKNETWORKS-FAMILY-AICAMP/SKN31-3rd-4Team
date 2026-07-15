"""
정신과 복약 관리 챗봇 - Streamlit 프론트엔드.
환자 전용 채팅, 근거(Explainable) 패널 포함.
"""
import streamlit as st
from box.workflow import build_workflow
from box.schemas import ChatState
from sidebar import display_sidebar

st.set_page_config(page_title="마음약속 · 복약 도우미", page_icon="💊", layout="wide")

# ------------------------------------------------------------------
# 스타일 (깔끔 + 귀여운 파스텔 틸 톤, 아키텍처 이미지 컬러 참고)
# ----------------------s--------------------------------------------
st.markdown("""
<style>
:root {
    --primary-dark: #0f3d3e;
    --primary: #16a596;
    --primary-light: #e6f7f5;
    --accent-pink: #ffd7e6;
}
.stApp { background: linear-gradient(180deg, #f7fdfc 0%, #ffffff 100%); }

.chat-header {
    background: linear-gradient(135deg, var(--primary-dark), var(--primary));
    padding: 22px 28px;
    border-radius: 20px;
    color: white;
    margin-bottom: 18px;
    box-shadow: 0 4px 14px rgba(15,61,62,0.15);
}
.chat-header h1 { margin: 0; font-size: 26px; }
.chat-header p { margin: 4px 0 0; opacity: 0.9; font-size: 14px; }

.role-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    background: var(--accent-pink);
    color: #7a2e4d;
    margin-bottom: 8px;
}

div[data-testid="stChatMessage"] {
    border-radius: 18px;
    padding: 4px 6px;
}

.evidence-box {
    background: var(--primary-light);
    border-left: 4px solid var(--primary);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    color: #0f3d3e;
    white-space: pre-wrap;
}

.emergency-banner {
    background: #ffe3e3;
    border: 1px solid #ff8787;
    color: #a61e1e;
    padding: 12px 16px;
    border-radius: 12px;
    font-weight: 600;
    margin-bottom: 12px;
}

section[data-testid="stSidebar"] {
    background: var(--primary-light);
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# 세션 상태 초기화
# ------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []  # [{"role": "patient"/"assistant", "content": str}]
if "workflow" not in st.session_state:
    st.session_state.workflow = build_workflow(patient_id="patient_001")
if "last_citations" not in st.session_state:
    st.session_state.last_citations = []

# ------------------------------------------------------------------
# 사이드바 호출
# ------------------------------------------------------------------
display_sidebar()

st.markdown("---")
if st.button("🧹 대화 초기화"):
    st.session_state.history = []
    st.session_state.last_citations = []
    st.rerun()

# ------------------------------------------------------------------
# 헤더
# ------------------------------------------------------------------
st.markdown("""
<div class="chat-header">
    <h1>💊 마음약속</h1>
    <p>정신과 복약 관리를 위한 개인화 설명형(Explainable) 챗봇</p>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# 대화 렌더링
# ------------------------------------------------------------------
for msg in st.session_state.history:
    is_patient = msg["role"] == "patient"
    with st.chat_message("user" if is_patient else "assistant", avatar="🧑" if is_patient else "🤖"):
        st.write(msg["content"])

# 근거(explainability) 패널 - 가장 최근 답변 기준
if st.session_state.last_citations:
    with st.expander("🔍 이 답변의 근거 보기 (Explainable)"):
        for c in st.session_state.last_citations:
            icon = {"personal": "🧑‍⚕️ 개인 그래프", "medical": "📚 의학 그래프", "vector": "🔎 문헌 검색"}[c.source_graph]
            st.markdown(f"**{icon}** · {c.node_or_doc}")
            if c.snippet:
                st.caption(c.snippet)

# ------------------------------------------------------------------
# 입력창
# ------------------------------------------------------------------

patient_saved = st.session_state.get("patient_saved", False)

placeholder = (
    "환자 정보를 먼저 입력해주세요."
    if not patient_saved
    else "예) 요즘 잠이 잘 안 오고 메스꺼움이 있어요, 약을 바꿔야 할까요?"
)

user_input = st.chat_input(placeholder, disabled=not patient_saved)

if user_input:
    st.session_state.history.append({"role": "patient", "content": user_input})

    state = ChatState(
        user_input=user_input,
        history=st.session_state.history,
    )

    with st.spinner("그래프를 탐색하고 답변을 준비하는 중... 🔎"):
        result = st.session_state.workflow.invoke(state)

    answer = result["answer"]
    citations = result.get("citations", [])
    extraction = result.get("extraction")

    st.session_state.history.append({"role": "assistant", "content": answer})
    st.session_state.last_citations = citations

    if extraction and extraction.urgency == "high":
        st.markdown(
            '<div class="emergency-banner">⚠️ 응급 신호가 감지되었습니다. '
            '즉시 담당 의료진 또는 응급실(119)에 연락하세요.</div>',
            unsafe_allow_html=True,
        )

    st.rerun()
# ------------------------------------------------------------------
# 워크플로 호출 시 환자 정보 실어 보내기
# ------------------------------------------------------------------
user_input=user_input if user_input is not None else ""

state = ChatState(
    user_input=user_input,
    history=st.session_state.history,
    patient_info=st.session_state.get("patient_info", {}),
)