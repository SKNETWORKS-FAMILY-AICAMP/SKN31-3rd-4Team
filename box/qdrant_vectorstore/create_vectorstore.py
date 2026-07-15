from dotenv import load_dotenv
import pandas as pd

from box.qdrant_vectorstore.document import documents
from box.qdrant_vectorstore.vectorstore import create_vectorstore 

#### 1번만 실행 ####

load_dotenv()

df = pd.read_excel("./qdrant_vectorstore/data/medicine_new.xlsx", engine='calamine')

print('시작')

docs = documents(df)

create_vectorstore(docs) # 임베딩 후 Vector DB저장

print("Vector DB 생성 완료")