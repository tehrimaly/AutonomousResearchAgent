from typing import TypedDict, Annotated, List
import operator


class AgentState(TypedDict):
    query: str
    sub_tasks: List[str]
    completed_tasks: Annotated[List[dict], operator.add]
    current_task: str
    tool_calls: Annotated[List[dict], operator.add]
    scratchpad: str
    final_report: str
    iteration: int
