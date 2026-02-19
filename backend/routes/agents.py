from fastapi import APIRouter, HTTPException, status
from backend.schemas.agent import AgentRequest, AgentResponse
from typing import Any

router = APIRouter(prefix="/agents", tags=["Agents"])

# Simulated agent registry
AGENTS = {
    "admission": "Handles student admission tasks",
    "registration": "Handles course registration",
    "attendance": "Handles attendance tracking",
    "grades": "Handles grade management",
}


@router.get("/")
def list_agents():
    """List available agents"""
    return {"available_agents": AGENTS}


@router.post("/execute", response_model=AgentResponse)
def execute_agent(request: AgentRequest):
    """Execute a specific agent with given task"""
    if request.agent_name not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{request.agent_name}' not found")

    try:
        # Placeholder for actual agent logic execution
        result = {
            "agent": request.agent_name,
            "task": request.task,
            "parameters": request.parameters,
            "processed": True,
        }

        return AgentResponse(agent_name=request.agent_name, status="success", result=result)
    except Exception as e:
        return AgentResponse(
            agent_name=request.agent_name, status="failed", result=None, error=str(e)
        )


@router.get("/{agent_name}")
def get_agent_info(agent_name: str):
    """Get information about a specific agent"""
    if agent_name not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"name": agent_name, "description": AGENTS[agent_name], "status": "active"}
