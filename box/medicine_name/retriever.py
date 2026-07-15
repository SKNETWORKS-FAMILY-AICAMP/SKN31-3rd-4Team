from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

vector_db = Chroma(
    persist_directory="./medicine_name_db",
    embedding_function=OpenAIEmbeddings(
        model="text-embedding-3-small"
    )
)

retriever = vector_db.as_retriever(
    search_kwargs={"k": 1}
)

def retriever_medicine(medicine_name):

    docs = vector_db.similarity_search(
        medicine_name,
        k=1
    )
# 반환값 없을 때 에러방지
    if not docs:
        return None

    doc = docs[0]

    return {
        "제품명": doc.metadata["제품명"],
        "주성분코드": doc.metadata["주성분코드"],
        "성분": doc.metadata["성분"]
    }
