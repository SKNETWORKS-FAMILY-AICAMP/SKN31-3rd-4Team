import sys, os
sys.path.append(os.path.dirname(__file__))
from qdrant_client.models import Filter, FieldCondition, MatchValue
from box.qdrant_vectorstore.vectorstore import load_vectorstore

vectorstore = load_vectorstore()

def retriever(query, ingredient_code, section=None, k=3):
    """
    FieldCondition + MatchValue로 구성

    {"page_content": ..., "metadata": {...}} 구조로 저장하기 때문에,
    ingredient_code/section은 metadata 안에 중첩되어 있다.
    """
    must_conditions = [
        FieldCondition(
            key="metadata.ingredient_code",
            match=MatchValue(value=ingredient_code),
        )
    ]

    if section:
        must_conditions.append(
            FieldCondition(
                key="metadata.section",
                match=MatchValue(value=section),
            )
        )

    qdrant_filter = Filter(must=must_conditions)

    result = vectorstore.similarity_search(
        query=query,
        k=k,
        filter=qdrant_filter,
    )

    return result