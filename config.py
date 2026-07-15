"""
전역 설정 로더.
.env 파일에서 값을 읽어와 Settings 객체로 노출한다.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- LLM ---
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.5")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    # --- Personal Graph (PGHD) ---
    PERSONAL_GRAPH_URI: str = os.getenv("PERSONAL_GRAPH_URI", "bolt://localhost:7687")
    PERSONAL_GRAPH_USER: str = os.getenv("PERSONAL_GRAPH_USER", "neo4j")
    PERSONAL_GRAPH_PASSWORD: str = os.getenv("PERSONAL_GRAPH_PASSWORD", "password")
    PERSONAL_GRAPH_DATABASE: str = os.getenv("PERSONAL_GRAPH_DATABASE", "neo4j")

    # --- Medical Graph ---
    MEDICAL_GRAPH_URI: str = os.getenv("MEDICAL_GRAPH_URI", "bolt://localhost:7687")
    MEDICAL_GRAPH_USER: str = os.getenv("MEDICAL_GRAPH_USER", "neo4j")
    MEDICAL_GRAPH_PASSWORD: str = os.getenv("MEDICAL_GRAPH_PASSWORD", "password")
    MEDICAL_GRAPH_DATABASE: str = os.getenv("MEDICAL_GRAPH_DATABASE", "neo4j")

    # --- Vector DB ---
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "medical_docs")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

    # --- Mode ---
    USE_MOCK_DB: bool = os.getenv("USE_MOCK_DB", "true").lower() == "true"


settings = Settings()
