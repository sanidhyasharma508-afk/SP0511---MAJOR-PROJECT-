"""
AI Intelligence Layer - RAG Pipeline and AI-Assisted Agents

This module provides:
1. RAG Pipeline: Knowledge base retrieval with campus policies and patterns
2. AI Agents: Enhanced agents with explanations and reasoning
3. Natural Language APIs: Query campus knowledge base
"""

from backend.ai.rag_pipeline import RAGPipeline, KnowledgeBase, get_rag_pipeline
from backend.ai.ai_agents import (
    AIAttendanceAgent,
    AIComplaintAgent,
    AIRiskAgent,
    get_attendance_agent,
    get_complaint_agent,
    get_risk_agent,
)

__all__ = [
    "RAGPipeline",
    "KnowledgeBase",
    "get_rag_pipeline",
    "AIAttendanceAgent",
    "AIComplaintAgent",
    "AIRiskAgent",
    "get_attendance_agent",
    "get_complaint_agent",
    "get_risk_agent",
]
