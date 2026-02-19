import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.student import Student
from backend.models.attendance import Attendance
from backend.models.complaint import Complaint
from backend.models.risk import RiskLog
from backend.ai.rag_pipeline import get_rag_pipeline

logger = logging.getLogger(__name__)


class AIExplanation:
    """Structure for AI-generated explanations"""

    def __init__(self, query: str, context: Dict[str, Any]):
        self.query = query
        self.context = context
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


class AIAttendanceAgent:
    """AI-assisted agent for explaining attendance issues"""

    def __init__(self):
        self.rag = get_rag_pipeline()
        self.name = "AIAttendanceAgent"

    def explain_attendance_drop(
        self, student_id: int, db: Session, days: int = 30
    ) -> Dict[str, Any]:
        """
        Explain why a student's attendance has dropped
        """
        try:
            # Get student info
            student = db.query(Student).filter(Student.id == student_id).first()
            if not student:
                return {"error": "Student not found"}

            # Get attendance data
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            attendance_records = (
                db.query(Attendance)
                .filter(Attendance.student_id == student_id, Attendance.date >= cutoff_date)
                .all()
            )

            # Calculate metrics
            total_records = len(attendance_records)
            present_count = len([a for a in attendance_records if a.status == "Present"])
            absent_count = len([a for a in attendance_records if a.status == "Absent"])
            late_count = len([a for a in attendance_records if a.status == "Late"])

            attendance_rate = present_count / total_records if total_records > 0 else 0

            # Get recent trend
            recent_week = (
                db.query(Attendance)
                .filter(
                    Attendance.student_id == student_id,
                    Attendance.date >= datetime.utcnow() - timedelta(days=7),
                )
                .all()
            )
            recent_rate = (
                len([a for a in recent_week if a.status == "Present"]) / len(recent_week)
                if recent_week
                else 0
            )

            # Build query for context
            query_text = (
                f"attendance drop policy support academic counseling student {student.name}"
            )
            rag_context = self.rag.retrieve_context(query_text, "attendance")

            # Get student's complaints (possible stress indicators)
            complaints = (
                db.query(Complaint)
                .filter(Complaint.student_id == student_id, Complaint.date >= cutoff_date)
                .count()
            )

            # Build explanation
            explanation = {
                "student": {
                    "id": student_id,
                    "name": student.name,
                    "roll_no": student.roll_no,
                    "department": student.department,
                },
                "metrics": {
                    "attendance_rate": round(attendance_rate, 3),
                    "recent_week_rate": round(recent_rate, 3),
                    "total_records": total_records,
                    "present": present_count,
                    "absent": absent_count,
                    "late": late_count,
                    "period_days": days,
                },
                "analysis": {
                    "trend": "declining" if recent_rate < attendance_rate else "stable",
                    "severity": self._assess_severity(attendance_rate),
                    "related_complaints": complaints,
                    "risk_level": (
                        "High"
                        if attendance_rate < 0.75
                        else "Medium" if attendance_rate < 0.85 else "Low"
                    ),
                },
                "reasoning": self._generate_attendance_reasoning(
                    student.name, attendance_rate, recent_rate, absent_count, complaints
                ),
                "actions": self._get_attendance_actions(attendance_rate),
                "retrieved_context": {
                    "document_count": rag_context["document_count"],
                    "sources": [doc["title"] for doc in rag_context["retrieved_documents"]],
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            return explanation

        except Exception as e:
            logger.error(f"Error in attendance explanation: {str(e)}")
            return {"error": f"Error analyzing attendance: {str(e)}"}

    def _assess_severity(self, rate: float) -> str:
        """Assess attendance severity"""
        if rate < 0.60:
            return "Critical"
        elif rate < 0.75:
            return "High"
        elif rate < 0.85:
            return "Medium"
        return "Low"

    def _generate_attendance_reasoning(
        self, name: str, rate: float, recent_rate: float, absences: int, complaints: int
    ) -> str:
        """Generate reasoning for attendance analysis"""
        reasoning = f"Student {name} has an overall attendance rate of {rate*100:.1f}%"

        if rate < 0.75:
            reasoning += " which is below the 75% minimum policy requirement. "
        else:
            reasoning += " which meets the minimum policy requirement. "

        if recent_rate < rate:
            reasoning += f"However, recent attendance is declining to {recent_rate*100:.1f}%, showing a concerning trend. "

        if absences > 0:
            reasoning += f"There are {absences} absences in the period. "

        if complaints > 0:
            reasoning += f"Additionally, {complaints} complaints filed suggest the student may be experiencing academic or personal stress. "

        reasoning += "Immediate intervention is recommended."

        return reasoning

    def _get_attendance_actions(self, rate: float) -> List[str]:
        """Get recommended actions"""
        actions = []

        if rate < 0.75:
            actions = [
                "Schedule immediate meeting with student",
                "Contact parents/guardians for support",
                "Offer tutoring or academic support",
                "Assign peer mentor for encouragement",
                "Consider temporary schedule adjustment",
            ]
        elif rate < 0.85:
            actions = [
                "Send encouraging message to student",
                "Check-in with academic advisor",
                "Offer optional support resources",
                "Schedule follow-up in 2 weeks",
            ]
        else:
            actions = [
                "Monitor attendance going forward",
                "Provide positive feedback",
                "Encourage continued engagement",
            ]

        return actions


class AIComplaintAgent:
    """AI-assisted agent for analyzing complaints"""

    def __init__(self):
        self.rag = get_rag_pipeline()
        self.name = "AIComplaintAgent"

    def explain_complaint_spike(self, db: Session, days: int = 7) -> Dict[str, Any]:
        """
        Explain why complaints have increased
        """
        try:
            # Get complaint data
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            recent_complaints = db.query(Complaint).filter(Complaint.date >= cutoff_date).all()

            # Historical data (previous period)
            prev_cutoff = cutoff_date - timedelta(days=days)
            previous_complaints = (
                db.query(Complaint)
                .filter(Complaint.date >= prev_cutoff, Complaint.date < cutoff_date)
                .all()
            )

            # Analyze by category
            recent_by_category = {}
            for complaint in recent_complaints:
                category = complaint.category
                recent_by_category[category] = recent_by_category.get(category, 0) + 1

            # Analyze by priority
            recent_by_priority = {}
            for complaint in recent_complaints:
                priority = complaint.priority
                recent_by_priority[priority] = recent_by_priority.get(priority, 0) + 1

            # Calculate spike percentage
            spike_percent = (
                (len(recent_complaints) - len(previous_complaints)) / len(previous_complaints) * 100
                if previous_complaints
                else 0
            )

            # Get context
            query_text = "complaint resolution process policy support"
            rag_context = self.rag.retrieve_context(query_text, "complaint")

            # Build explanation
            explanation = {
                "metrics": {
                    "recent_period": {
                        "days": days,
                        "total_complaints": len(recent_complaints),
                        "by_category": recent_by_category,
                        "by_priority": recent_by_priority,
                    },
                    "previous_period": {"days": days, "total_complaints": len(previous_complaints)},
                    "spike_percentage": round(spike_percent, 2),
                },
                "analysis": {
                    "trend": "increasing" if spike_percent > 10 else "stable",
                    "severity": self._assess_complaint_severity(len(recent_complaints)),
                    "top_category": (
                        max(recent_by_category.items(), key=lambda x: x[1])[0]
                        if recent_by_category
                        else None
                    ),
                    "top_priority": (
                        max(recent_by_priority.items(), key=lambda x: x[1])[0]
                        if recent_by_priority
                        else None
                    ),
                },
                "reasoning": self._generate_complaint_reasoning(
                    len(recent_complaints),
                    len(previous_complaints),
                    spike_percent,
                    recent_by_category,
                    recent_by_priority,
                ),
                "actions": self._get_complaint_actions(spike_percent),
                "retrieved_context": {
                    "document_count": rag_context["document_count"],
                    "sources": [doc["title"] for doc in rag_context["retrieved_documents"]],
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            return explanation

        except Exception as e:
            logger.error(f"Error in complaint analysis: {str(e)}")
            return {"error": f"Error analyzing complaints: {str(e)}"}

    def _assess_complaint_severity(self, count: int) -> str:
        """Assess complaint severity based on count"""
        if count >= 5:
            return "Critical"
        elif count >= 3:
            return "High"
        elif count >= 1:
            return "Medium"
        return "Low"

    def _generate_complaint_reasoning(
        self, recent: int, previous: int, spike: float, by_category: Dict, by_priority: Dict
    ) -> str:
        """Generate reasoning for complaint spike"""
        reasoning = f"In the recent period, {recent} complaints were filed "
        reasoning += f"compared to {previous} in the previous period, "

        if spike > 0:
            reasoning += f"representing a {spike:.1f}% increase. "
        else:
            reasoning += f"representing a {abs(spike):.1f}% decrease. "

        if by_category:
            top_category = max(by_category.items(), key=lambda x: x[1])
            reasoning += (
                f"The most common complaint type is '{top_category[0]}' ({top_category[1]} cases). "
            )

        if by_priority:
            top_priority = max(by_priority.items(), key=lambda x: x[1])
            reasoning += f"Majority are '{top_priority[0]}' priority complaints. "

        if spike > 25:
            reasoning += (
                "This significant spike requires immediate administrative review and action."
            )
        elif spike > 10:
            reasoning += "The increase warrants monitoring and possible interventions."
        else:
            reasoning += "The trend should be monitored in coming days."

        return reasoning

    def _get_complaint_actions(self, spike_percent: float) -> List[str]:
        """Get recommended actions"""
        actions = []

        if spike_percent > 25:
            actions = [
                "Immediate dean review required",
                "Identify common themes across complaints",
                "Schedule emergency meeting with relevant departments",
                "Prepare communication for stakeholders",
                "Implement systemic solutions",
            ]
        elif spike_percent > 10:
            actions = [
                "Conduct detailed analysis of complaints",
                "Meet with department heads",
                "Develop action plan",
                "Monitor for continued increases",
                "Keep stakeholders informed",
            ]
        else:
            actions = [
                "Monitor complaint trends",
                "Process complaints per standard procedure",
                "Review resolution timeline",
                "Continue routine operations",
            ]

        return actions


class AIRiskAgent:
    """AI-assisted agent for risk analysis"""

    def __init__(self):
        self.rag = get_rag_pipeline()
        self.name = "AIRiskAgent"

    def explain_risk(self, risk_id: int, db: Session) -> Dict[str, Any]:
        """
        Explain a specific risk and provide recommendations
        """
        try:
            # Get risk information
            risk = db.query(RiskLog).filter(RiskLog.id == risk_id).first()
            if not risk:
                return {"error": "Risk not found"}

            # Get student info
            student = (
                db.query(Student).filter(Student.id == risk.student_id).first()
                if risk.student_id
                else None
            )

            # Get related data
            recent_complaints = (
                db.query(Complaint).filter(Complaint.student_id == risk.student_id).count()
                if risk.student_id
                else 0
            )

            recent_absences = (
                db.query(Attendance)
                .filter(
                    Attendance.student_id == risk.student_id,
                    Attendance.status == "Absent",
                    Attendance.date >= datetime.utcnow() - timedelta(days=14),
                )
                .count()
                if risk.student_id
                else 0
            )

            # Get RAG context for this risk type
            rag_context = self.rag.get_risk_context(risk.risk_type)

            # Build explanation
            explanation = {
                "risk": {
                    "id": risk_id,
                    "type": risk.risk_type,
                    "severity": risk.severity,
                    "description": risk.description,
                    "created_at": risk.created_at.isoformat(),
                },
                "student": (
                    {"id": student.id, "name": student.name, "roll_no": student.roll_no}
                    if student
                    else None
                ),
                "context": {
                    "related_complaints": recent_complaints,
                    "recent_absences": recent_absences,
                    "days_since_risk": (datetime.utcnow() - risk.created_at).days,
                },
                "analysis": {
                    "risk_active": not risk.resolved,
                    "action_taken": risk.action_taken,
                    "risk_score": self._calculate_risk_score(
                        risk.severity, recent_complaints, recent_absences
                    ),
                },
                "reasoning": self._generate_risk_reasoning(
                    risk.risk_type,
                    risk.severity,
                    risk.description,
                    recent_complaints,
                    recent_absences,
                    student.name if student else "Unknown",
                ),
                "interventions": rag_context.get("intervention_strategies", []),
                "retrieved_context": {
                    "document_count": rag_context["document_count"],
                    "risk_type": rag_context.get("risk_type"),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            return explanation

        except Exception as e:
            logger.error(f"Error in risk explanation: {str(e)}")
            return {"error": f"Error analyzing risk: {str(e)}"}

    def _calculate_risk_score(self, severity: str, complaints: int, absences: int) -> int:
        """Calculate composite risk score"""
        score = 0

        # Severity score
        severity_map = {"Critical": 40, "High": 30, "Medium": 20, "Low": 10}
        score += severity_map.get(severity, 10)

        # Complaint score
        score += min(complaints * 5, 20)

        # Absence score
        score += min(absences * 3, 20)

        return min(score, 100)

    def _generate_risk_reasoning(
        self,
        risk_type: str,
        severity: str,
        description: str,
        complaints: int,
        absences: int,
        student_name: str,
    ) -> str:
        """Generate reasoning for risk analysis"""
        reasoning = f"Student {student_name} has been flagged with a '{risk_type}' risk of '{severity}' severity. "
        reasoning += f"Specifically: {description}. "

        if complaints > 0:
            reasoning += f"This student has filed {complaints} complaints recently. "

        if absences > 0:
            reasoning += (
                f"Additionally, {absences} absences have been recorded in the past 2 weeks. "
            )

        reasoning += "Coordinated intervention is necessary to support this student."

        return reasoning


# Agent instances
_attendance_agent = None
_complaint_agent = None
_risk_agent = None


def get_attendance_agent() -> AIAttendanceAgent:
    """Get or create attendance agent"""
    global _attendance_agent
    if _attendance_agent is None:
        _attendance_agent = AIAttendanceAgent()
    return _attendance_agent


def get_complaint_agent() -> AIComplaintAgent:
    """Get or create complaint agent"""
    global _complaint_agent
    if _complaint_agent is None:
        _complaint_agent = AIComplaintAgent()
    return _complaint_agent


def get_risk_agent() -> AIRiskAgent:
    """Get or create risk agent"""
    global _risk_agent
    if _risk_agent is None:
        _risk_agent = AIRiskAgent()
    return _risk_agent
