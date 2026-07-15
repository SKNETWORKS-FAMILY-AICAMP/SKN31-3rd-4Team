import os
import time
from dotenv import load_dotenv
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings

# .env 파일이 있다면 로드
load_dotenv()

# 환경 변수 설정 (기본값 제공)
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "medical_docs")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
# Docker Qdrant 서버 주소
QDRANT_URL = os.getenv("QDRANT_URL", "http://192.168.0.32:6333")

# Qdrant 로컬 저장 경로 설정 (서버를 쓴다면 URL과 API_KEY로 대체 )
# QDRANT_PATH: str = os.getenv("QDRANT_PATH", "./medicine_qdrant_db")


def create_vectorstore(docs):
    """
    Documents를 받아 임베딩 후 Qdrant Vector DB를 생성하고 로컬에 저장합니다.
    """
    print(f"[{QDRANT_COLLECTION}] 컬렉션 생성 및 데이터 삽입 시작...")
    
    embedding = OpenAIEmbeddings(
        chunk_size=100,
        max_retries=5,
        model=EMBEDDING_MODEL
    )

    BATCH_SIZE =100 # 한 번에 보낼 문서 개수
    total = len(docs)

    print(f"{total}개- {BATCH_SIZE}씩 나눠 업로드 ")

    first_batch = docs[0:BATCH_SIZE]

    # LangChain의 QdrantVectorStore 모듈을 이용한 연동 및 생성
    vectorstore = QdrantVectorStore.from_documents(
        documents=docs,
        embedding=embedding,
        # path=QDRANT_PATH,                
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION # 컬렉션 이름 설정
    )
    print(f"--{min(BATCH_SIZE, total)}/{total} 초기 컬렉션 생성--")

    for i in range(BATCH_SIZE, total, BATCH_SIZE):
        # Rate Limit 방지를 위해 각 업로드 사이에 2~3초간 쉬어줍니다.
        time.sleep(2.5) 
        
        batch = docs[i:i + BATCH_SIZE]
        vectorstore.add_documents(batch)
        done = min(i + BATCH_SIZE, total)
        print(f"  {done}/{total} 완료")
 
    print("모든 문서 업로드 완료.")
    return vectorstore


def load_vectorstore():
    """
    기존에 생성된 Qdrant Vector DB를 불러옵니다.
    """
    embedding = OpenAIEmbeddings(
        model=EMBEDDING_MODEL
    )

    # 기존 컬렉션과 경로를 바라보도록 설정하여 로드
    vectorstore = QdrantVectorStore.from_existing_collection(
        embedding=embedding,
        # path=QDRANT_PATH,
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION
    )
    
    return vectorstore