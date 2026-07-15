import requests
import requests
import logging

logger = logging.getLogger(__name__)

FASTAPI_URL = "http://localhost:8000/chat"

def get_api_response(
    prompt: str,
    thread_id: str,
    patient_info: dict,
    model: str = "gpt-4o-mini"
) -> dict:
    """
    FastAPI 백엔드 서버의 /chat 엔드포인트로 사용자의 입력과 환자 세션 정보를 전송합니다.
    """
    # 1. FastAPI ChatRequest 스키마와 동일한 구조로 payload 구성
    payload = {
        "query": prompt,
        "thread_id": thread_id,
        "model": model,
        "patient_info": patient_info
    }
    
    try:
        # 2. POST 요청 전송 (JSON 포맷, 타임아웃 60초)
        response = requests.post(FASTAPI_URL, json=payload, timeout=60)
        
        # 3. HTTP 응답 상태 코드 확인 (200 OK가 아니면 예외 발생)
        response.raise_for_status()
        
        # 4. 정상적인 경우 JSON 결과 반환 {"answer": "...", "model": "..."}
        return response.json()
        
    except requests.exceptions.RequestException as e:
        # 통신 장애, 서버 다운, 타임아웃 등 에러 처리 및 로그 남기기
        logger.error(f"FastAPI 연결 오류 발생: {e}")
        return None
