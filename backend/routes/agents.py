from fastapi import APIRouter, HTTPException, status, Depends
from backend.schemas.agent import AgentRequest, AgentResponse
from backend.core.auth import TokenData
from backend.core.rbac import get_current_user
import logging
from typing import Any

logger = logging.getLogger("agents")
router = APIRouter(prefix="/agents", tags=["Agents"])

# Simulated agent registry
AGENTS = {
    "admission": "Handles student admission tasks",
    "registration": "Handles course registration",
    "attendance": "Handles attendance tracking",
    "grades": "Handles grade management",
}

# Permitted roles per agent type
AGENT_ROLE_PERMISSIONS = {
    "admission": {"admin", "staff"},
    "grades": {"faculty", "staff", "admin"},
    "attendance": {"student", "faculty", "staff", "admin"},
    "registration": {"student", "faculty", "staff", "admin"},
}


@router.get("/")
def list_agents():
    """List available agents (Public discovery)"""
    return {"available_agents": AGENTS}


@router.post("/execute", response_model=AgentResponse)
def execute_agent(
    request: AgentRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Execute a specific agent with given task.
    Enforces:
    - User authentication and role-based permissions per agent type.
    - Anti-impersonation: student identity derived from authenticated principal.
    - Safe error reporting without internal state leakage.
    """
    if request.agent_name not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{request.agent_name}' not found")

    user_role = (current_user.role or "").lower()
    allowed_roles = AGENT_ROLE_PERMISSIONS.get(request.agent_name, {"admin", "staff"})
    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user_role}' is not authorized to execute the '{request.agent_name}' agent",
        )

    # Anti-impersonation: students cannot pass parameters targeting other students
    if user_role == "student" and request.parameters:
        for id_key in ("student_id", "user_id"):
            if id_key in request.parameters:
                val = str(request.parameters[id_key])
                valid_ids = {str(current_user.user_id), str(current_user.sub)}
                if current_user.linked_student_id is not None:
                    valid_ids.add(str(current_user.linked_student_id))
                if val not in valid_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot execute agent with another student's identifier",
                    )

    try:
        # Placeholder for actual agent logic execution
        result = {
            "agent": request.agent_name,
            "task": request.task,
            "parameters": request.parameters,
            "processed": True,
            "executed_by": current_user.sub,
            "role": user_role,
        }

        return AgentResponse(agent_name=request.agent_name, status="success", result=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent execution error: {str(e)}")
        return AgentResponse(
            agent_name=request.agent_name,
            status="failed",
            result=None,
            error="Agent execution encountered an error",
        )


@router.get("/{agent_name}")
def get_agent_info(agent_name: str):
    """Get information about a specific agent"""
    if agent_name not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"name": agent_name, "description": AGENTS[agent_name], "status": "active"}
