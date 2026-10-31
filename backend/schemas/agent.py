from pydantic import BaseModel, Field
from typing import Any, Optional


class AgentRequest(BaseModel):
    """Schema for agent execution request"""

    agent_name: str = Field(..., min_length=1, max_length=100)
    task: str = Field(..., min_length=1, max_length=1000)
    parameters: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Schema for agent execution response"""

    agent_name: str
    status: str
    result: Any
    error: Optional[str] = None
