import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Campus knowledge base - policies, rules, and guidelines
CAMPUS_KNOWLEDGE_BASE = {
    "policies": [
        {
            "id": "attendance_policy",
            "title": "Attendance Policy",
            "content": """
            Campus Attendance Policy:
            - Minimum 75% attendance required per semester
            - Students below 75% are considered at-risk
            - 3 consecutive absences trigger automatic notification
            - Medical/emergency leave requires documentation within 48 hours
            - Late arrival (>15 mins) counts as absence
            - Attendance reset on semester start
            """,
            "category": "academic",
        },
        {
            "id": "conduct_policy",
            "title": "Student Conduct Policy",
            "content": """
            Campus Conduct Guidelines:
            - Zero tolerance for harassment and bullying
            - Academic integrity violations result in disciplinary action
            - Substance abuse strictly prohibited on campus
            - Respectful behavior mandatory in all interactions
            - Grievance resolution follows formal complaint process
            - Appeal process available within 30 days of action
            """,
            "category": "conduct",
        },
        {
            "id": "support_services",
            "title": "Student Support Services",
            "content": """
            Available Support Services:
            - Academic counseling: 9 AM - 5 PM, Counseling Center, Block A
            - Mental health support: 24/7 hotline available
            - Career guidance: By appointment, Career Office
            - Dean of Students: For serious concerns
            - Peer mentoring: Voluntary program, sign up at Student Services
            - Tutor support: Free tutoring in Math, Science, English
            """,
            "category": "support",
        },
        {
            "id": "complaint_resolution",
            "title": "Complaint Resolution Process",
            "content": """
            How Complaints Are Handled:
            1. Filing: Submit via online portal or Student Services office
            2. Documentation: All details recorded within 24 hours
            3. Investigation: Assigned to relevant department (2-5 days)
            4. Resolution: Action taken based on investigation findings
            5. Follow-up: Check-in with complainant after 1 week
            Priority levels: Urgent (24h), High (48h), Normal (72h)
            """,
            "category": "governance",
        },
        {
            "id": "risk_intervention",
            "title": "Risk Intervention Protocol",
            "content": """
            Risk Detection and Intervention:
            - Attendance drop >20%: Automatic parent notification
            - Complaint spike (3+ in a day): Dean review within 24 hours
            - Low GPA trend: Academic advisor counseling session
            - Mental health flags: Counselor referral with student consent
            - Repeated violations: Disciplinary action planning
            """,
            "category": "risk_management",
        },
    ],
    "historical_patterns": [
        {
            "pattern": "Monday Complaints",
            "description": "Complaints spike on Monday mornings, typically schedule or conduct related",
            "frequency": "High",
            "root_cause": "Weekend stress accumulation, adjustment to week schedule",
        },
        {
            "pattern": "Semester-End Attendance Drop",
            "description": "Attendance drops 15-20% in final 2 weeks before exams",
            "frequency": "Very High",
            "root_cause": "Exam preparation, student focus shift",
        },
        {
            "pattern": "Midterm Academic Crisis",
            "description": "Risk flags increase during midterms",
            "frequency": "High",
            "root_cause": "Academic pressure, assessment peaks",
        },
        {
            "pattern": "Technical Issue Complaints",
            "description": "Portal/system complaints follow platform updates",
            "frequency": "Medium",
            "root_cause": "System transitions, user adjustment period",
        },
    ],
    "intervention_strategies": {
        "low_attendance": [
            "Send motivational message to student",
            "Schedule meeting with academic advisor",
            "Contact parents for support",
            "Offer tutoring or extra support",
        ],
        "complaint_spike": [
            "Immediate dean review",
            "Identify common themes",
            "Address root cause systematically",
            "Communicate resolution to all stakeholders",
        ],
        "at_risk_student": [
            "Assign peer mentor",
            "Schedule counseling session",
            "Create action plan with timeline",
            "Weekly check-ins for 4 weeks",
        ],
        "conduct_issue": [
            "Document incident thoroughly",
            "Schedule disciplinary hearing",
            "Provide education/remediation",
            "Monitor compliance and follow-up",
        ],
    },
}


class KnowledgeBase:
    """Manages campus knowledge base for RAG"""

    def __init__(self):
        """Initialize knowledge base"""
        self.documents = self._build_documents()
        self.embeddings_cache = {}

    def _build_documents(self) -> List[Dict[str, Any]]:
        """Build document collection from knowledge base"""
        documents = []
        doc_id = 0

        # Add policies
        for policy in CAMPUS_KNOWLEDGE_BASE["policies"]:
            documents.append(
                {
                    "id": doc_id,
                    "type": "policy",
                    "title": policy["title"],
                    "content": policy["content"],
                    "category": policy["category"],
                    "timestamp": datetime.utcnow(),
                }
            )
            doc_id += 1

        # Add historical patterns
        for pattern in CAMPUS_KNOWLEDGE_BASE["historical_patterns"]:
            documents.append(
                {
                    "id": doc_id,
                    "type": "pattern",
                    "title": pattern["pattern"],
                    "content": f"Pattern: {pattern['description']}\nFrequency: {pattern['frequency']}\nRoot Cause: {pattern['root_cause']}",
                    "category": "pattern",
                    "timestamp": datetime.utcnow(),
                }
            )
            doc_id += 1

        # Add intervention strategies
        for risk_type, strategies in CAMPUS_KNOWLEDGE_BASE["intervention_strategies"].items():
            content = f"Risk Type: {risk_type}\nStrategies:\n"
            for i, strategy in enumerate(strategies, 1):
                content += f"{i}. {strategy}\n"

            documents.append(
                {
                    "id": doc_id,
                    "type": "strategy",
                    "title": f"Intervention Strategy: {risk_type}",
                    "content": content,
                    "category": "intervention",
                    "timestamp": datetime.utcnow(),
                }
            )
            doc_id += 1

        return documents

    def retrieve_relevant_documents(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve documents relevant to query (simple keyword matching)
        In production, use vector similarity search
        """
        query_lower = query.lower()
        relevant = []

        for doc in self.documents:
            title_match = query_lower in doc["title"].lower()
            content_match = query_lower in doc["content"].lower()

            if title_match or content_match:
                # Score based on matches
                score = 0
                if title_match:
                    score += 2
                if content_match:
                    score += 1

                relevant.append({**doc, "relevance_score": score})

        # Sort by relevance and return top results
        relevant.sort(key=lambda x: x["relevance_score"], reverse=True)
        return relevant[:limit]

    def get_policy(self, policy_id: str) -> Optional[str]:
        """Get specific policy content"""
        for policy in CAMPUS_KNOWLEDGE_BASE["policies"]:
            if policy["id"] == policy_id:
                return policy["content"]
        return None

    def get_intervention_strategies(self, risk_type: str) -> List[str]:
        """Get intervention strategies for a risk type"""
        return CAMPUS_KNOWLEDGE_BASE["intervention_strategies"].get(risk_type, [])

    def get_similar_patterns(self, description: str) -> List[Dict[str, str]]:
        """Find similar historical patterns"""
        description_lower = description.lower()
        similar = []

        for pattern in CAMPUS_KNOWLEDGE_BASE["historical_patterns"]:
            if (
                description_lower in pattern["description"].lower()
                or description_lower in pattern["pattern"].lower()
            ):
                similar.append(pattern)

        return similar


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline"""

    def __init__(self):
        """Initialize RAG pipeline"""
        self.knowledge_base = KnowledgeBase()
        self.context_cache = {}
        logger.info("✓ RAG Pipeline initialized with campus knowledge base")

    def retrieve_context(self, query: str, context_type: str = "general") -> Dict[str, Any]:
        """
        Retrieve relevant context for a query
        """
        documents = self.knowledge_base.retrieve_relevant_documents(query, limit=5)

        context = {
            "query": query,
            "context_type": context_type,
            "retrieved_documents": documents,
            "timestamp": datetime.utcnow().isoformat(),
            "document_count": len(documents),
        }

        # Build context string for LLM
        context_text = "\n\n".join(
            [f"[{doc['type'].upper()}] {doc['title']}\n{doc['content']}" for doc in documents]
        )

        context["context_text"] = context_text

        return context

    def assemble_prompt(
        self, user_query: str, retrieved_context: str, system_role: str = "Campus Administrator"
    ) -> str:
        """
        Assemble prompt for LLM with retrieved context
        """
        prompt = f"""You are a {system_role} assistant for a college campus automation system.

CAMPUS KNOWLEDGE BASE:
{retrieved_context}

USER QUESTION:
{user_query}

Please provide:
1. Direct Answer: Clear, concise response
2. Reasoning: Why this is the case, based on campus policies/data
3. Action Items: What should be done next (if applicable)
4. Confidence: How confident in this assessment (High/Medium/Low)

Format your response clearly with these sections."""

        return prompt

    def get_attendance_context(self, student_id: int, days: int = 30) -> Dict[str, Any]:
        """Get specific context for attendance analysis"""
        query = f"attendance policy student {student_id} low absence"
        context = self.retrieve_context(query, "attendance")
        context["analysis_type"] = "attendance"
        context["student_id"] = student_id
        context["lookback_days"] = days
        return context

    def get_complaint_context(self, complaint_id: int) -> Dict[str, Any]:
        """Get specific context for complaint analysis"""
        query = "complaint resolution process grievance policy"
        context = self.retrieve_context(query, "complaint")
        context["analysis_type"] = "complaint"
        context["complaint_id"] = complaint_id
        return context

    def get_risk_context(self, risk_type: str) -> Dict[str, Any]:
        """Get specific context for risk analysis"""
        query = f"risk {risk_type} intervention strategies"
        context = self.retrieve_context(query, "risk")
        context["analysis_type"] = "risk"
        context["risk_type"] = risk_type

        # Add intervention strategies
        strategies = self.knowledge_base.get_intervention_strategies(
            risk_type.lower().replace(" ", "_")
        )
        context["intervention_strategies"] = strategies

        return context


# Global RAG pipeline instance
_rag_pipeline = None


def get_rag_pipeline() -> RAGPipeline:
    """Get or create RAG pipeline instance"""
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
