from box.retriever import retriever

# 테스트를 위한 가상의 조건 설정
query = "임산부가 복용해도 안전한가요?"
ingredient_code = "626402ATR"  # 엑셀 데이터에 존재하는 실제 주성분 코드를 입력하세요
section = "용법용량"   # 특정 섹션을 지정하거나 생략(None)할 수 있습니다
k=3

# 1. 데이터 조회 실행
search_results = retriever(
    query=query, 
    ingredient_code=ingredient_code, 
    section=section, 
    k=3
)

# 2. 결과 출력하기
print(f"--- 검색 결과 (총 {len(search_results)}개) ---")
for idx, doc in enumerate(search_results):
    print(f"\n[{idx + 1}번째 관련 문서]")
    print(f"내용:\n{doc.page_content}")
    print(f"메타데이터: {doc.metadata}")