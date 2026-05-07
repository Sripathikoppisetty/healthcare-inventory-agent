"""agent/core.py — LangGraph ReAct agent wired to Groq."""

from datetime import date
from typing import TypedDict, Annotated
import operator

from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from config.settings import settings
from agent.prompts import SYSTEM_PROMPT

# ── Import all tools ──────────────────────────────────────────────────────────
from tools.inventory import check_stock, reorder_item, transfer_sku, bulk_update_par_levels
from tools.analytics import demand_forecast, abc_analysis, anomaly_detection
from tools.compliance import expiry_scan, compliance_check
from tools.supplier import supplier_lookup

ALL_TOOLS = [
    check_stock,
    reorder_item,
    transfer_sku,
    bulk_update_par_levels,
    demand_forecast,
    abc_analysis,
    anomaly_detection,
    expiry_scan,
    compliance_check,
    supplier_lookup,
]

# ── Agent state ───────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


# ── LLM + tools binding ───────────────────────────────────────────────────────

def build_llm():
    return ChatGroq(
        model=settings.model_name,
        api_key=settings.groq_api_key,
        temperature=0,
        max_tokens=4096,
    ).bind_tools(ALL_TOOLS)


# ── Agent node ────────────────────────────────────────────────────────────────

def agent_node(state: AgentState):
    """Invoke the LLM with the current message history."""
    llm = build_llm()
    system = SystemMessage(
        content=SYSTEM_PROMPT.format(today=date.today().isoformat())
    )
    messages = [system] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_agent():
    """Compile and return the LangGraph agent."""
    tool_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


# ── Public interface ──────────────────────────────────────────────────────────

_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def run_query(user_message: str) -> str:
    """
    Run a single user query through the agent and return the final text response.

    Args:
        user_message: Natural language query from the user.

    Returns:
        Agent's final text response.
    """
    agent = get_agent()
    state = {"messages": [HumanMessage(content=user_message)]}
    result = agent.invoke(state, {"recursion_limit": settings.max_iterations})

    # Return the last AI message content
    for msg in reversed(result["messages"]):
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
            return msg.content
    return "Agent completed without a text response."


def stream_query(user_message: str):
    """
    Stream agent output token-by-token (generator).
    Useful for real-time UIs.
    """
    agent = get_agent()
    state = {"messages": [HumanMessage(content=user_message)]}
    for chunk in agent.stream(state, {"recursion_limit": settings.max_iterations}):
        if "agent" in chunk:
            msgs = chunk["agent"].get("messages", [])
            for m in msgs:
                if hasattr(m, "content") and m.content:
                    yield m.content
