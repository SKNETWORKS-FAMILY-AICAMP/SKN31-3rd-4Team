from medicine_vectorstore.retriever import retriever
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from langchain.tools import tool
import json

@tool
def load_user_profile():
    """사용자의 기본 의료 정보를 가져온다."""
    with open("사용자더미데이터.txt", encoding="utf-8") as f:
        return json.load(f)

SYSTEM_PROMPT = """
당신은 약품 검색 AI이다.

규칙
1. 항상 load_user_profile을 확인하고 답변한다.
2. 항상 retriever를 load_user_profile 에 있는 ingredient_code를 입력해서 사용한다. 예시(query, ingredient_code) section은 작성하지 말고 저 두개만 넣어서 호출해
3. Tool 결과에 없는 내용은 추측하지 않는다.
4. 모르면 모른다고 답한다.
5. 답변은 한국어로 한다.

너는 의약품 정보를 정확하게 안내하는 전문 AI 어시스턴트이다.
반드시 다음의 [답변 규칙]을 엄격하게 준수하여 답변해야 한다.

[답변 규칙]
1. 답변의 근거 제한:
   - 사용자가 질문한 내용에 대해, 반드시 도구(Tool)나 벡터스토어(Vectorstore)를 통해
     조회되어 제공된 [문서 데이터]만을 바탕으로 답변해야 한다.
   - 문서에 명시되지 않은 정보나 너의 배경지식을 활용해 임의로 유추하거나 거짓 정보를 지어내서 대답해서는 절대 안 된다.
     문서에 관련 내용이 없다면 "제공된 문서에서 관련 정보를 찾을 수 없습니다."라고 솔직하게 답변하라.
   - 제공된 문서를 바탕으로 추가적으로 아픈곳이 있는지 꼭 물어봐.
"""

llm = ChatOpenAI(model="gpt-5.4-mini").bind_tools([retriever, load_user_profile])

messages = [
    ("system", SYSTEM_PROMPT),
    HumanMessage("요즘 배가 자주 아파")
]
tool_call_log = []  

while True:
    ai_msg = llm.invoke(messages)
    messages.append(ai_msg)

    if not ai_msg.tool_calls:
        break

    for tool_call in ai_msg.tool_calls:
        tool_call_log.append({           
            "name": tool_call["name"],
            "args": tool_call["args"]
        })

        if tool_call["name"] == "load_user_profile":
            print("-> load_user_profile 실행")
            result = load_user_profile.invoke(tool_call)

        elif tool_call["name"] == "retriever":
            print("-> retriever 실행")
            result = retriever.invoke(tool_call)

        else:
            result = f"알 수 없는 tool: {tool_call['name']}"

        messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )

print("최종 답변:", ai_msg.content)

print("호출된 도구 이력:")   
for log in tool_call_log:
    print(f"  - {log['name']}({log['args']})")