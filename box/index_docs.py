"""
Qdrant 컬렉션에 문서를 최초 1회 인덱싱하는 스크립트.

실행 방법 (프로젝트 루트에서):
    python index_docs.py

전제 조건:
  - .env 에 USE_MOCK_DB=false, QDRANT_URL, OPENAI_API_KEY 가 설정되어 있어야 함
  - Qdrant 서버가 실행 중이어야 함 (docker run -p 6333:6333 qdrant/qdrant)
"""
from box.vector_db import VectorDB, _MOCK_DOCS

if __name__ == "__main__":
    vdb = VectorDB()
    print(f"'{vdb.__class__.__name__}' 연결 완료. 문서 {len(_MOCK_DOCS)}개 인덱싱 시작...")
    vdb.index_documents(_MOCK_DOCS)
    print("인덱싱 완료! 이제 앱에서 벡터 검색이 정상 동작합니다.")

    # 인덱싱 확인
    results = vdb.search("메스꺼움 부작용", top_k=3)
    print("\n[검증] '메스꺼움 부작용' 검색 결과:")
    for r in results:
        print(f"  - ({r['score']:.3f}) {r['source']}: {r['text'][:40]}...")
