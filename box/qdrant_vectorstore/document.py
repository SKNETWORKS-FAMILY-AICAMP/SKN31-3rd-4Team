import re
import pandas as pd
from langchain_core.documents import Document

df = pd.read_excel('./qdrant_vectorstore/data/medicine_new.xlsx', engine='calamine')


def split_long_text(text, max_len=800):
    """
    긴 문장을 800자 기준으로 분할.
    """
    text = text.strip()
    if len(text) <= max_len:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + max_len, len(text))

        if end != len(text):
            cut = text.rfind("\n", start, end)  # 분할 기준 1순위: 줄바꿈

            if cut == -1:
                cut = text.rfind(".", start, end)  # 2순위: 마침표

            if cut == -1 or cut <= start:
                # 구분자를 못 찾았거나, 찾았어도 전진이 안 되는 경우 -> 강제 분할
                cut = end
            else:
                cut += 1  # 구분자 다음 글자부터 다음 청크 시작 
        else:
            cut = end

        chunk = text[start:cut].strip()
        if chunk:
            chunks.append(chunk)

        start = max(cut, start + 1)  # 항상 최소 1글자 전진

    return chunks


def documents(df):

    docs = []  # 매 실행시 초기화되도록 함수 내부 이동
    for _, row in df.iterrows():
        code = str(row["주성분코드"]) if not pd.isna(row["주성분코드"]) else ""

        ###############################################
        # 1. 효능효과
        ###############################################

        if not pd.isna(row.get("효능효과")):
            docs.append(
                Document(
                    page_content=f"[효능효과]\n{str(row['효능효과']).strip()}",
                    metadata={
                        "ingredient_code": code,
                        "section": "효능효과"
                    }
                )
            )

        ###############################################
        # 2. 용법용량
        ###############################################

        if not pd.isna(row.get("용법용량")):

            dosage = str(row["용법용량"]).strip()

            chunks = split_long_text(dosage)

            for idx, chunk in enumerate(chunks):
                docs.append(
                    Document(
                        page_content=f"[용법용량]\n{chunk}",
                        metadata={
                            "ingredient_code": code,
                            "section": "용법용량",
                            "part": idx + 1
                        }
                    )
                )

        ###############################################
        # 3. 사용상의주의사항
        ###############################################

        text_val = row["사용상의주의사항"]

        if pd.isna(text_val):
            continue

        text = str(text_val).strip()
        # 줄 시작점(^)에 오는 '숫자. 제목' 패턴만 타겟팅 (re.MULTILINE 필수)
        pattern = r'^(\d+\.\s+[^\n]+)'
        matches = list(re.finditer(pattern, text, re.MULTILINE))

        if not matches:
            # 매칭되는 제목이 아예 없는 텍스트 예외 처리
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "ingredient_code": code,
                        "section": "전체"
                    }
                )
            )
            continue

        # 첫 번째 제목(1. 경고 등) 이전에 도입 문구가 있을 때 누락 방지
        first_match_start = matches[0].start()
        if first_match_start > 0:
            intro = text[:first_match_start].strip()
            if intro:
                docs.append(
                    Document(
                        page_content=intro,
                        metadata={
                            "ingredient_code": code,
                            "section": "개요"
                        }
                    )
                )

        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk = text[start:end].strip()
            title = match.group().strip()

            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "ingredient_code": code,
                        "section": title
                    }
                )
            )

    print(f"생성된 Document 수 : {len(docs)}")

    return docs