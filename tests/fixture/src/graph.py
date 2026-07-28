from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain.agents import create_agent

def build(pool, tools):
    researcher = create_agent("claude-sonnet-4-6", tools=tools)
    graph = StateGraph(dict)
    graph.add_node("research", researcher)
    graph.add_edge("research", END)
    return graph.compile(checkpointer=PostgresSaver(pool))
