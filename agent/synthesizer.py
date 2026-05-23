from langchain_google_genai import ChatGoogleGenerativeAI
from .state import AgentState

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2)


def synthesizer_node(state: AgentState) -> AgentState:
    all_findings = "\n\n".join(
        f"### Sub-task: {r['task']}\n{r['scratchpad']}"
        for r in state["completed_tasks"]
    )

    prompt = f"""You are a research synthesizer. Multiple sub-investigations have
been completed. Write a comprehensive, well-structured report that directly
answers the original query using all findings below.

ORIGINAL QUERY:
{state['query']}

FINDINGS FROM SUB-TASKS:
{all_findings}

Format the report with:
- An executive summary (2-3 sentences)
- Clearly labelled sections for each major finding
- A conclusions section
- References or sources where available

Write clearly and professionally."""

    report = llm.invoke(prompt).content
    return {**state, "final_report": report}
