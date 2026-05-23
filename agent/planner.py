import json
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from .state import AgentState

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)

PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a research planner. Given a research query, break it into
3-5 concrete, independently-answerable sub-tasks. Each sub-task should be
specific enough that a web search or code execution can fully resolve it.

Return ONLY a valid JSON array of strings. No extra text, no markdown fences.
Example: ["What is X?", "How does Y work?", "Compare A and B"]""",
    ),
    ("human", "{query}"),
])


def planner_node(state: AgentState) -> AgentState:
    response = (PLANNER_PROMPT | llm).invoke({"query": state["query"]})
    raw = response.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    sub_tasks: list = json.loads(raw)
    return {
        **state,
        "sub_tasks": sub_tasks,
        "current_task": sub_tasks[0],
        "iteration": 0,
        "scratchpad": "",
        "completed_tasks": [],
        "tool_calls": [],
        "final_report": "",
    }
