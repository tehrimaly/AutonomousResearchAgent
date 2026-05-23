from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from .state import AgentState
from .planner import planner_node
from .synthesizer import synthesizer_node
from tools.web_search import web_search
from tools.code_executor import execute_python
from tools.file_writer import write_file

MAX_ITERATIONS = 12

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
tools = [web_search, execute_python, write_file]
llm_with_tools = llm.bind_tools(tools)

REACT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an autonomous research agent working on one focused sub-task.

CURRENT SUB-TASK: {current_task}

OVERALL RESEARCH QUERY: {query}

SCRATCHPAD (your work so far on this task):
{scratchpad}

Instructions:
- Think step by step. Use the available tools to gather information.
- After each tool call, reason about the result before deciding the next step.
- When you have fully answered the sub-task, write TASK_COMPLETE on its own line,
  followed by a concise JSON summary: {{"findings": "...", "sources": [...]}}
- Do NOT mark TASK_COMPLETE until you have real evidence from tool calls.
- Maximum {max_iter} iterations — be efficient.""",
    ),
    ("human", "Continue working on the current sub-task."),
])


def think_act_node(state: AgentState) -> AgentState:
    response = (REACT_PROMPT | llm_with_tools).invoke({
        "current_task": state["current_task"],
        "query": state["query"],
        "scratchpad": state["scratchpad"] or "(empty — just starting)",
        "max_iter": MAX_ITERATIONS,
    })

    new_scratch = state["scratchpad"] + f"\n\n--- Iteration {state['iteration'] + 1} ---\n{response.content}"
    new_tool_calls: list = []

    for tool_call in getattr(response, "tool_calls", []):
        tool_fn = next((t for t in tools if t.name == tool_call["name"]), None)
        if tool_fn is None:
            output = f"ERROR: unknown tool '{tool_call['name']}'"
        else:
            try:
                output = tool_fn.invoke(tool_call["args"])
            except Exception as exc:
                output = f"ERROR running {tool_call['name']}: {exc}"

        snippet = str(output)[:800]
        new_scratch += f"\n[Tool: {tool_call['name']}]\n{snippet}"
        new_tool_calls.append({"call": tool_call, "output": str(output)})

    return {
        **state,
        "scratchpad": new_scratch,
        "tool_calls": new_tool_calls,
        "iteration": state["iteration"] + 1,
    }


def should_continue(state: AgentState) -> str:
    if state["iteration"] >= MAX_ITERATIONS:
        remaining = _remaining_tasks(state)
        return "next_task" if remaining else "synthesize"

    last_lines = state["scratchpad"].split("\n")[-6:]
    if any("TASK_COMPLETE" in line for line in last_lines):
        remaining = _remaining_tasks(state)
        return "next_task" if remaining else "synthesize"

    return "continue"


def next_task_node(state: AgentState) -> AgentState:
    completed = state["completed_tasks"] + [
        {"task": state["current_task"], "scratchpad": state["scratchpad"]}
    ]
    remaining = _remaining_tasks(state)
    next_task = remaining[0] if remaining else ""
    return {
        **state,
        "completed_tasks": completed,
        "current_task": next_task,
        "scratchpad": "",
        "tool_calls": [],
        "iteration": 0,
    }


def _remaining_tasks(state: AgentState) -> list:
    done = {r["task"] for r in state["completed_tasks"]}
    done.add(state["current_task"])
    return [t for t in state["sub_tasks"] if t not in done]


# ── Build the graph ──────────────────────────────────────────────────────────

workflow = StateGraph(AgentState)
workflow.add_node("planner", planner_node)
workflow.add_node("think_act", think_act_node)
workflow.add_node("next_task", next_task_node)
workflow.add_node("synthesize", synthesizer_node)

workflow.set_entry_point("planner")
workflow.add_edge("planner", "think_act")

workflow.add_conditional_edges(
    "think_act",
    should_continue,
    {
        "continue":   "think_act",
        "next_task":  "next_task",
        "synthesize": "synthesize",
    },
)
workflow.add_edge("next_task", "think_act")
workflow.add_edge("synthesize", END)

graph = workflow.compile()
