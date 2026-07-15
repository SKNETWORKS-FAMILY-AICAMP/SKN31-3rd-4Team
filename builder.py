import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from chat_node import State, chat_node, medicine_node, side_effect_node, router, general_chat_node, side_effect_followup_node ,entry_router

# 그래프 조립
def build_graph():
    graph = StateGraph(State)

    graph.add_node("chat_node", chat_node)
    graph.add_node("medicine_node", medicine_node)
    graph.add_node("side_effect_node",side_effect_node)
    graph.add_node("general_chat_node", general_chat_node) 
    graph.add_node("side_effect_followup_node", side_effect_followup_node)

    graph.add_conditional_edges(
        START,
        entry_router,
        {
            "side_effect_followup_node": "side_effect_followup_node",
            "chat_node": "chat_node",
        },
    )
    graph.add_conditional_edges(
        "chat_node",
        router,
        {
            "medicine_node": "medicine_node",
            "general_chat_node": "general_chat_node",  
        }
    )
    graph.add_edge("medicine_node", "side_effect_node")
    graph.add_edge("side_effect_node", END)
    graph.add_edge("side_effect_followup_node", END)
    graph.add_edge("general_chat_node", END)

    conn = sqlite3.connect("langgraph_checkpoint.db", check_same_thread=False)
    memory = SqliteSaver(conn)

    return graph.compile(checkpointer=memory)

graph = build_graph()