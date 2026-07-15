import pandas as pd
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

# ==========================
# 1. 엑셀 읽기
# ==========================
df = pd.read_excel("data/정신과주성분코드_ATC매핑_ver1.xlsx")

docs = []
print('embedding 시작')

for idx, row in df.iterrows():
    docs.append(
    Document(
        page_content=str(row["제품명"]),
        metadata=row.to_dict()
    )
)
# ==========================
# 2. Vector DB 생성
# ==========================
vector_db = Chroma.from_documents(
    documents=docs,
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
    persist_directory="./medicine_name_db"
)

print('작업완료')
