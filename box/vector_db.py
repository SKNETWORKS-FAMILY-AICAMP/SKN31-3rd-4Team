"""
Qdrant 기반 Vector DB 커넥터.
Medical Graph의 논문/가이드라인 문서를 임베딩하여 의미 기반 검색을 보조한다.
(Graph Retriever의 '+ Vector' 부분을 담당)

실제 DB 연결 방법:
  1. Qdrant 서버 실행 (예: docker run -p 6333:6333 qdrant/qdrant)
  2. .env 의 QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION 설정
  3. USE_MOCK_DB=false 로 변경
  4. 아래 index_documents()로 문서를 한 번 인덱싱해야 검색이 동작함
"""
from config import settings

_MOCK_DOCS = [
    {
        "id": "doc1",
        "text": "SSRI와 수면제 병용 시 졸림, 어지러움이 증가할 수 있으며 저녁 시간대 복용 조정이 권장된다.",
        "source": "SSRI 병용 시 수면제 상호작용에 대한 메타분석 (2023)",
    },
    {
        "id": "doc2",
        "text": "에스시탈로프람 복용 초기 2주 내 메스꺼움, 두통이 흔하게 나타나며 대개 시간이 지나며 완화된다.",
        "source": "SSRI 초기 부작용 임상 가이드라인",
    },
    {
        "id": "doc3",
        "text": "졸피뎀 장기 복용 시 인지기능 저하 및 의존성 위험이 보고되어 4주 이내 단기 사용이 권장된다.",
        "source": "졸피뎀 장기 복용과 인지기능 변화 연구 (2022)",
    },
]


class VectorDB:
    def __init__(self):
        self.use_mock = settings.USE_MOCK_DB
        self._client = None
        if not self.use_mock:
            self._connect_real()

    # ---------------- 실제 DB 연결부 ----------------
    def _connect_real(self):
        from qdrant_client import QdrantClient
        self._client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
        )

    def _embed(self, text: str) -> list[float]:
        # text-embedding-3-large 등 임베딩 모델 호출부
        from langchain_openai import OpenAIEmbeddings
        embedder = OpenAIEmbeddings(model=settings.EMBEDDING_MODEL, api_key=settings.OPENAI_API_KEY)
        return embedder.embed_query(text)

    def index_documents(self, docs: list[dict]):
        """docs: [{"id":..., "text":..., "source":...}, ...] 를 컬렉션에 업서트."""
        from qdrant_client.models import PointStruct
        points = []
        for d in docs:
            vector = self._embed(d["text"])
            points.append(PointStruct(id=d["id"], vector=vector, payload={"text": d["text"], "source": d["source"]}))
        self._client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)

    def _run_real_search(self, query: str, top_k: int = 3) -> list[dict]:
        vector = self._embed(query)
        hits = self._client.search(
            collection_name=settings.QDRANT_COLLECTION, query_vector=vector, limit=top_k
        )
        return [{"text": h.payload["text"], "source": h.payload["source"], "score": h.score} for h in hits]

    # ---------------- 공개 API ----------------
    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if self.use_mock:
            return self._mock_search(query, top_k)
        return self._run_real_search(query, top_k)

    def _mock_search(self, query: str, top_k: int) -> list[dict]:
        # 간단한 키워드 매칭 기반 유사 검색 흉내
        scored = []
        for doc in _MOCK_DOCS:
            score = sum(1 for token in query.split() if token in doc["text"])
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"text": d["text"], "source": d["source"], "score": s} for s, d in scored[:top_k]]
