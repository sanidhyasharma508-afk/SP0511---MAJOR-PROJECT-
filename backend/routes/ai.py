from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas.ai import (
    AttendanceExplanationResponse,
    ComplaintSpikeExplanationResponse,
    RiskExplanationResponse,
    RAGContextResponse,
    AIHealthCheckResponse,
    NaturalLanguageQueryRequest,
    NaturalLanguageQueryResponse,
    KnowledgeBaseDocument,
)
from backend.ai.ai_agents import get_attendance_agent, get_complaint_agent, get_risk_agent
from backend.ai.rag_pipeline import get_rag_pipeline
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai-intelligence"])


# ==================== HEALTH & STATUS ====================


@router.get("/health", response_model=AIHealthCheckResponse)
def ai_health_check():
    """Check AI pipeline health"""
    try:
        rag = get_rag_pipeline()
        attendance_agent = get_attendance_agent()
        complaint_agent = get_complaint_agent()
        risk_agent = get_risk_agent()

        return {
            "status": "operational",
            "rag_pipeline": True,
            "agents": [attendance_agent.name, complaint_agent.name, risk_agent.name],
            "knowledge_base_size": len(rag.knowledge_base.documents),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"AI health check failed: {str(e)}")
        return {
            "status": "error",
            "rag_pipeline": False,
            "agents": [],
            "knowledge_base_size": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }


# ==================== ATTENDANCE INTELLIGENCE ====================


@router.get("/explain-attendance/{student_id}", response_model=AttendanceExplanationResponse)
def explain_attendance_issues(student_id: int, days: int = 30, db: Session = Depends(get_db)):
    """
    Explain why a student's attendance has dropped

    Uses:
    - Student attendance records
    - Complaint history
    - Campus attendance policies
    - Historical patterns
    """
    try:
        agent = get_attendance_agent()
        result = agent.explain_attendance_drop(student_id, db, days)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except Exception as e:
        logger.error(f"Error explaining attendance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing attendance: {str(e)}")


@router.get("/why-attendance-dropped/{student_id}")
def why_attendance_dropped(student_id: int, days: int = 30, db: Session = Depends(get_db)):
    """
    Natural language explanation for why attendance dropped
    """
    try:
        agent = get_attendance_agent()
        result = agent.explain_attendance_drop(student_id, db, days)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        # Extract key insights for natural language response
        metrics = result["metrics"]
        analysis = result["analysis"]
        actions = result["actions"]

        response = {
            "query": f"Why has {result['student']['name']}'s attendance dropped?",
            "answer": result["reasoning"],
            "confidence": "High" if analysis["severity"] in ["Critical", "High"] else "Medium",
            "reasoning": f"Student has {metrics['total_records']} attendance records over {metrics['period_days']} days with {metrics['attendance_rate']*100:.1f}% attendance rate. Trend is {analysis['trend']}.",
            "sources": result["retrieved_context"]["sources"],
            "timestamp": result["timestamp"],
        }

        return response
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== COMPLAINT INTELLIGENCE ====================


@router.get("/explain-complaints", response_model=ComplaintSpikeExplanationResponse)
def explain_complaint_spike(days: int = 7, db: Session = Depends(get_db)):
    """
    Explain why complaints have increased

    Uses:
    - Recent complaint history
    - Complaint categorization
    - Historical patterns
    - Campus policies
    """
    try:
        agent = get_complaint_agent()
        result = agent.explain_complaint_spike(db, days)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except Exception as e:
        logger.error(f"Error explaining complaints: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing complaints: {str(e)}")


@router.get("/why-complaints-increased")
def why_complaints_increased(days: int = 7, db: Session = Depends(get_db)):
    """
    Natural language explanation for complaint spike
    """
    try:
        agent = get_complaint_agent()
        result = agent.explain_complaint_spike(db, days)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        # Extract for natural language response
        metrics = result["metrics"]
        analysis = result["analysis"]

        response = {
            "query": "Why have complaints increased?",
            "answer": result["reasoning"],
            "confidence": "High" if analysis["severity"] in ["Critical", "High"] else "Medium",
            "reasoning": f"Complaints increased {metrics['spike_percentage']:.1f}% from {metrics['previous_period']['total_complaints']} to {metrics['recent_period']['total_complaints']} in the past {days} days. Trend is {analysis['trend']}.",
            "sources": result["retrieved_context"]["sources"],
            "timestamp": result["timestamp"],
        }

        return response
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== RISK INTELLIGENCE ====================


@router.get("/explain-risk/{risk_id}", response_model=RiskExplanationResponse)
def explain_risk(risk_id: int, db: Session = Depends(get_db)):
    """
    Explain a risk and provide AI-driven insights

    Uses:
    - Risk information
    - Related student data
    - Intervention strategies
    - Historical patterns
    """
    try:
        agent = get_risk_agent()
        result = agent.explain_risk(risk_id, db)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except Exception as e:
        logger.error(f"Error explaining risk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing risk: {str(e)}")


@router.post("/explain-risk-natural-language")
def explain_risk_natural_language(risk_id: int, db: Session = Depends(get_db)):
    """
    Natural language explanation for a specific risk
    """
    try:
        agent = get_risk_agent()
        result = agent.explain_risk(risk_id, db)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        response = {
            "query": f"What is the nature and severity of risk {risk_id}?",
            "answer": result["reasoning"],
            "confidence": "High" if result["analysis"]["risk_score"] > 70 else "Medium",
            "reasoning": f"Risk type: {result['risk']['type']}, Severity: {result['risk']['severity']}, Score: {result['analysis']['risk_score']}/100",
            "sources": result["retrieved_context"]["sources"],
            "timestamp": result["timestamp"],
        }

        return response
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== GENERAL QUERY & RAG ====================


@router.post("/query", response_model=NaturalLanguageQueryResponse)
def query_knowledge_base(request: NaturalLanguageQueryRequest):
    """
    Query campus knowledge base using RAG

    Retrieves relevant documents about:
    - Campus policies
    - Historical patterns
    - Intervention strategies
    - Support services
    """
    try:
        rag = get_rag_pipeline()
        context = rag.retrieve_context(request.query, request.context or "general")

        # Build answer from retrieved documents
        docs = context["retrieved_documents"]
        sources = [doc["title"] for doc in docs]

        # Create comprehensive answer
        answer = f"Based on campus knowledge base, {request.query}:\n\n"
        for doc in docs[:3]:  # Top 3 results
            answer += f"- {doc['title']}: {doc['content'][:200]}...\n"

        response = {
            "query": request.query,
            "answer": answer,
            "confidence": "High" if len(docs) > 2 else "Medium",
            "reasoning": f"Retrieved {len(docs)} relevant documents from knowledge base",
            "sources": sources,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return response
    except Exception as e:
        logger.error(f"Error querying knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying knowledge base: {str(e)}")


@router.get("/knowledge-base/retrieve")
def retrieve_documents(query: str, limit: int = 5):
    """
    Retrieve documents from knowledge base
    """
    try:
        rag = get_rag_pipeline()
        documents = rag.knowledge_base.retrieve_relevant_documents(query, limit)

        return {
            "query": query,
            "document_count": len(documents),
            "documents": [
                {
                    "id": doc["id"],
                    "type": doc["type"],
                    "title": doc["title"],
                    "content": doc["content"][:500],  # Truncate for response
                    "category": doc["category"],
                    "relevance_score": doc.get("relevance_score", 0),
                }
                for doc in documents
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error retrieving documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-base/info")
def knowledge_base_info():
    """
    Get information about knowledge base
    """
    try:
        rag = get_rag_pipeline()
        kb = rag.knowledge_base

        # Count by type
        type_counts = {}
        for doc in kb.documents:
            doc_type = doc["type"]
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

        return {
            "total_documents": len(kb.documents),
            "by_type": type_counts,
            "categories": list(set(doc["category"] for doc in kb.documents)),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting KB info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== INSIGHTS & ANALYTICS ====================


@router.get("/insights/attendance-patterns")
def attendance_patterns_insight(db: Session = Depends(get_db)):
    """
    Get AI insights about attendance patterns
    """
    try:
        rag = get_rag_pipeline()
        patterns = rag.knowledge_base.get_similar_patterns("attendance")

        return {
            "insight_type": "attendance_patterns",
            "patterns": patterns,
            "key_takeaway": "Attendance follows predictable patterns - understanding these helps with early intervention",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting insights: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights/complaint-patterns")
def complaint_patterns_insight(db: Session = Depends(get_db)):
    """
    Get AI insights about complaint patterns
    """
    try:
        rag = get_rag_pipeline()
        patterns = rag.knowledge_base.get_similar_patterns("complaint")

        return {
            "insight_type": "complaint_patterns",
            "patterns": patterns,
            "key_takeaway": "Complaints follow temporal patterns - specific times and days see higher volumes",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting insights: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights/intervention-strategies/{risk_type}")
def intervention_strategies_insight(risk_type: str):
    """
    Get recommended intervention strategies for a risk type
    """
    try:
        rag = get_rag_pipeline()
        strategies = rag.knowledge_base.get_intervention_strategies(risk_type)

        if not strategies:
            raise HTTPException(status_code=404, detail=f"No strategies found for {risk_type}")

        return {
            "risk_type": risk_type,
            "strategies": strategies,
            "description": f"Recommended interventions for {risk_type} risks",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting strategies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
