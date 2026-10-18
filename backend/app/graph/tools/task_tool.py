from typing import Optional, List
from langchain_core.tools import tool


@tool
def manage_active_task(
    goal: str,
    status: str = "in_progress",
    current_step: Optional[str] = None,
    constraints: Optional[List[str]] = None,
    artifacts: Optional[List[str]] = None,
) -> str:
    """
    Update or record the user's active structured task state.
    Use this tool whenever executing multi-step complex workflows, coding tasks, or project plans.
    Parameters:
    - goal: Overarching objective or task goal.
    - status: 'in_progress', 'completed', 'blocked', or 'paused'.
    - current_step: Current sub-task or milestone being worked on.
    - constraints: Specific constraints, user instructions, or boundaries.
    - artifacts: Deliverables, files, or key findings produced.
    """
    details = [f"Goal: {goal}", f"Status: {status}"]
    if current_step:
        details.append(f"Current Step: {current_step}")
    if constraints:
        details.append(f"Constraints: {', '.join(constraints)}")
    if artifacts:
        details.append(f"Artifacts: {', '.join(artifacts)}")
    return f"Active task state recorded: {'; '.join(details)}"
