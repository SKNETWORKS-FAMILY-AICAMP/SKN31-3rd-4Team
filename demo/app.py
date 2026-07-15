import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
sys.path.append(str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
import streamlit as st
from db_utils import create_patient, create_patient_table
from api_utils import get_api_response
from graph_db.workflow import build_workflow
from graph_db.chat_graph_db import ChatGraphDB

load_dotenv()

st.session_state.model = "gpt-5.4-mini"

st.set_page_config(
    page_title="약한AI 복약 상담 챗봇",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

create_patient_table()


# ------------------------------------------------------------------
# css 함수
# ------------------------------------------------------------------
def load_css(file_name: str = "style.css") -> None:
    css_path = Path(__file__).parent / file_name

    if not css_path.exists():
        st.warning(f"⚠️ 스타일 파일을 찾을 수 없습니다: {css_path}")
        return

    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


load_css("style.css")

st.markdown(
    """
    <div class="app-hero">
        <div class="emoji-badge">💊</div>
        <div>
            <h1>약한AI 복약 상담 챗봇</h1>
            <p>정신질환 약물 부작용 상담 &amp; 복용 용법 안내를 도와드려요 🌤️</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")
if st.button("🧹 대화 초기화"):
    if st.session_state.get("patient_id"):
        chat_db = ChatGraphDB()
        try:
            session_id = chat_db.create_session(st.session_state.patient_id)
            st.session_state.session_id = session_id
            st.session_state.history = []
            st.session_state.last_citations = []
            st.session_state.neo4j_graph = chat_db.get_session_graph(session_id)
        finally:
            chat_db.close()  
    else:
        st.session_state.history = []
        st.session_state.last_citations = []
    st.rerun()
    
# ------------------------------------------------------------------
#! 1. 사이드바 : 사용자 입력 정보
# ------------------------------------------------------------------
def display_sidebar():
    st.sidebar.markdown(
        """
        <div class="sidebar-title">📋 환자 정보 입력</div>
        <div class="sidebar-sub">상담을 시작하기 전에 환자 정보를 알려주세요.</div>
        """,
        unsafe_allow_html=True,
    )

    # 0. 이름 입력
    name = st.sidebar.text_input("이름", placeholder="홍길동")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        # 1. 연령/나이 입력
        age = st.number_input("나이 (세)", min_value=0, max_value=120, value=25, step=1)
    with col2:
        # 2. 성별 선택
        gender = st.selectbox("성별", options=["선택 안함", "남성", "여성"])

    # 3. 임신 여부
    is_pregnant = False
    if gender == "여성":
        is_pregnant = st.sidebar.checkbox("🤰 임신 여부 (임산부)")

    st.sidebar.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    drug = st.sidebar.text_input("약제품명", placeholder="라투다정")

    # 5. 주성분 코드
    ingredient_code = st.sidebar.text_area("일단 주성분코드", placeholder="729801ATB", height=80)

    st.sidebar.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # 6. 저장 버튼
    if st.sidebar.button("💙 환자 정보 저장/업데이트", use_container_width=True):
        patient = create_patient(
            name,
            age,
            gender,
            is_pregnant,
            drug,
            ingredient_code
        )
        # 💡 안전장치: 데이터가 성공적으로 생성되었을 때만 세션과 화면에 기록
        if patient is not None:
            st.session_state.patient = patient
            st.sidebar.success("환자 정보가 저장되었습니다! 🌤️")
        else:
            st.sidebar.error("환자 정보 저장 중 오류가 발생했습니다.")


display_sidebar()

# ------------------------------------------------------------------
#! 2. 메인 대시보드 : 환자 요약 + 채팅
# ------------------------------------------------------------------
def display_patient_summary(patient):
    gender = patient.get("gender", "-")
    chip_gender_class = "mint" if gender == "여성" else "sky-soft"
    pregnant_chip = ""
    if patient.get("is_pregnant"):
        pregnant_chip = '<span class="chip coral">🤰 임산부</span>'

    st.markdown(
        f"""
        <div class="patient-bar">
            <span class="welcome">{patient.get('name', '환자')}님, 어서오세요 😊</span>
            <span class="chip">🎂 {patient.get('age', '-')}세</span>
            <span class="chip {chip_gender_class}">{gender}</span>
            {pregnant_chip}
            <span class="chip">💊 {patient.get('drug', '-')}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def display_chat_interface():
    #! [첫 호출]환자 기본 정보 입력 여부 확인
    if not st.session_state.get("patient"):
        st.markdown(
            """
            <div class="info-card">
                <div class="big-emoji">👈🌤️</div>
                <h3>환자 정보를 먼저 입력해 주세요</h3>
                <p>왼쪽 사이드바에서 이름, 나이, 성별, 약제품명 등을 입력하고<br/>
                <b>[환자 정보 저장/업데이트]</b> 버튼을 눌러주시면 상담을 시작할 수 있어요.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    current_patient = st.session_state.patient
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = st.session_state.patient["thread_id"]
    if "patient_id" not in st.session_state:
        st.session_state.patient_id = st.session_state.patient["patient_id"]
    if "workflow" not in st.session_state:
        st.session_state.workflow = build_workflow(patient_id=st.session_state.patient_id)
    if "last_citations" not in st.session_state:
        st.session_state.last_citations = []
    if "messages" not in st.session_state:
        st.session_state.messages = []

    display_patient_summary(current_patient)

    #! 1.이전 대화 출력
    for message in st.session_state.messages:
        avatar = "🧑" if message["role"] == "user" else "💊"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    #! 2. 사용자 입력
    if prompt := st.chat_input("증상이나 추가 문의 사항을 입력하세요 💬"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="💊"):
            with st.spinner("답변 생성 중... 🌤️"):
                selected_model = st.session_state.get("model", "gpt-4o-mini")
                response = get_api_response(
                    prompt=prompt,
                    thread_id=st.session_state.get("thread_id", "default-thread"),
                    patient_info=st.session_state.get("patient", {}),
                    model=selected_model
                )

            if response is None:
                st.error("API 호출에 실패했습니다.")
                return

            answer = response["answer"]
            st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})


display_chat_interface()