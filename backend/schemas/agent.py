from pydantic import BaseModel
from typing import Any, Optional


class AgentRequest(BaseModel):
    """Schema for agent execution request"""

    agent_name: str
    task: str
    parameters: dict = {}


class AgentResponse(BaseModel):
    """Schema for agent execution response"""

    agent_name: str
    status: str
    result: Any
    error: Optional[str] = None
