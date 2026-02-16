"""
Analytics API Routes
Trend detection, anomaly detection, and data analysis
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas.analytics import (
    AttendanceTrendResponse,
    ComplaintTrendResponse,
    ComplaintHeatmapResponse,
    RiskDistributionResponse,
    AnalyticsAnomalies,
    AnomalyAlert,
)
from backend.models.attendance import Attendance
from backend.models.complaint import Complaint
from backend.models.risk import RiskLog
from backend.models.student import Student
from backend.core.agents import TrendDetectionAgent, AnomalyDetectionAgent
from datetime import datetime, timedelta
from typing import List, Dict
from collections import defaultdict

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/attendance-trends/{student_id}", response_model=AttendanceTrendResponse)
def get_attendance_trends(student_id: int, days: int = 30, db: Session = Depends(get_db)):
    """
    Get attendance trends for a specific student
    Includes daily data, moving average, and trend direction
    """
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        trend_data = TrendDetectionAgent.calculate_attendance_trend(student_id, db, days)

        if not trend_data:
            raise HTTPException(status_code=404, detail="No attendance data found")

        return trend_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching attendance trends: {str(e)}")


@router.get("/complaint-heatmap", response_model=ComplaintHeatmapResponse)
def get_complaint_heatmap(days: int = 30, db: Session = Depends(get_db)):
    """
    Get complaint filing patterns as heatmap
    Shows when complaints are filed most frequently (day/hour)
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        complaints = db.query(Complaint).filter(Complaint.created_at >= cutoff_date).all()

        if not complaints:
            raise HTTPException(status_code=404, detail="No complaint data found")

        # Build heatmap (day of week × hour of day)
        heatmap_data = defaultdict(lambda: defaultdict(int))
        category_counts = defaultdict(int)

        for complaint in complaints:
            day_of_week = complaint.created_at.strftime("%A")
            hour = complaint.created_at.hour
            heatmap_data[day_of_week][hour] += 1
            category_counts[complaint.category] += 1

        # Convert to list format with intensity
        max_count = max(
            [count for day_dict in heatmap_data.values() for count in day_dict.values()], default=1
        )

        heatmap_list = []
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            for hour in range(24):
                count = heatmap_data.get(day, {}).get(hour, 0)
                intensity = count / max_count if max_count > 0 else 0
                heatmap_list.append(
                    {
                        "day_of_week": day,
                        "hour": hour,
                        "count": count,
                        "intensity": round(intensity, 2),
                    }
                )

        # Find top complaint times
        time_counts = defaultdict(int)
        for complaint in complaints:
            time_key = f"{complaint.created_at.strftime('%A')} {complaint.created_at.hour}:00"
            time_counts[time_key] += 1

        top_times = sorted(
            [{"time": k, "count": v} for k, v in time_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        return {
            "period_days": days,
            "total_complaints": len(complaints),
            "heatmap": heatmap_list,
            "top_categories": dict(
                sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
            ),
            "top_times": top_times,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating heatmap: {str(e)}")


@router.get("/risk-distribution", response_model=RiskDistributionResponse)
def get_risk_distribution(db: Session = Depends(get_db)):
    """
    Get distribution of risks by type and severity
    Shows which risk types are most common
    """
    try:
        all_risks = db.query(RiskLog).all()
        unresolved_risks = db.query(RiskLog).filter(RiskLog.resolved == 0).all()
        resolved_risks = db.query(RiskLog).filter(RiskLog.resolved == 1).all()

        if not all_risks:
            raise HTTPException(status_code=404, detail="No risk data found")

        # Distribution by risk type
        risk_type_counts = defaultdict(int)
        risk_severity_breakdown = defaultdict(lambda: defaultdict(int))
        severity_distribution = defaultdict(int)

        for risk in all_risks:
            risk_type_counts[risk.risk_type] += 1
            risk_severity_breakdown[risk.risk_type][risk.severity] += 1
            severity_distribution[risk.severity] += 1

        # Build distribution list
        total_risks = len(all_risks)
        distribution = []
        for risk_type, count in sorted(risk_type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_risks) * 100 if total_risks > 0 else 0
            distribution.append(
                {
                    "risk_type": risk_type,
                    "count": count,
                    "percentage": round(percentage, 2),
                    "severity_breakdown": dict(risk_severity_breakdown[risk_type]),
                }
            )

        # Get top affected students
        student_risk_counts = defaultdict(int)
        for risk in all_risks:
            if risk.student_id:
                student_risk_counts[risk.student_id] += 1

        top_students = []
        for student_id, count in sorted(
            student_risk_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            student = db.query(Student).filter(Student.id == student_id).first()
            if student:
                top_students.append(
                    {"student_id": student_id, "student_name": student.name, "risk_count": count}
                )

        return {
            "total_risks": total_risks,
            "unresolved_risks": len(unresolved_risks),
            "resolved_risks": len(resolved_risks),
            "risk_distribution": distribution,
            "severity_distribution": dict(severity_distribution),
            "top_affected_students": top_students,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing risk distribution: {str(e)}")


@router.get("/complaint-trends", response_model=ComplaintTrendResponse)
def get_complaint_trends(days: int = 30, db: Session = Depends(get_db)):
    """
    Get complaint trends over time
    Weekly aggregation with moving averages
    """
    try:
        trend_data = TrendDetectionAgent.calculate_complaint_trend(db, days)

        if not trend_data:
            raise HTTPException(status_code=404, detail="No complaint data found")

        return trend_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching complaint trends: {str(e)}")


@router.post("/detect-anomalies")
def detect_anomalies(db: Session = Depends(get_db)):
    """
    Manually trigger anomaly detection
    Checks for attendance drops and complaint spikes
    """
    try:
        # Run anomaly detection
        AnomalyDetectionAgent.detect_attendance_anomalies(db)
        AnomalyDetectionAgent.detect_complaint_spikes(db)

        # Get recent anomalies
        cutoff = datetime.utcnow() - timedelta(days=1)
        anomalies = (
            db.query(RiskLog)
            .filter(
                (RiskLog.description.contains("ANOMALY"))
                | (RiskLog.description.contains("Complaint spike")),
                RiskLog.created_at >= cutoff,
            )
            .all()
        )

        return {
            "status": "anomaly detection completed",
            "anomalies_detected": len(anomalies),
            "details": [
                {
                    "type": (
                        "attendance_anomaly" if "ANOMALY" in a.description else "complaint_spike"
                    ),
                    "severity": a.severity,
                    "description": a.description,
                    "timestamp": a.created_at,
                }
                for a in anomalies
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during anomaly detection: {str(e)}")


@router.get("/anomalies", response_model=AnalyticsAnomalies)
def get_recent_anomalies(days: int = 7, db: Session = Depends(get_db)):
    """
    Get recent anomalies detected by system
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        anomaly_risks = (
            db.query(RiskLog)
            .filter(
                (
                    (RiskLog.description.contains("ANOMALY"))
                    | (RiskLog.description.contains("Complaint spike"))
                ),
                RiskLog.created_at >= cutoff,
            )
            .order_by(RiskLog.created_at.desc())
            .all()
        )

        alerts = []
        attendance_anomaly_count = 0
        complaint_spike_count = 0

        for risk in anomaly_risks:
            if "ANOMALY" in risk.description:
                alert_type = "attendance_drop"
                attendance_anomaly_count += 1
            else:
                alert_type = "complaint_spike"
                complaint_spike_count += 1

            alerts.append(
                {
                    "type": alert_type,
                    "severity": risk.severity,
                    "description": risk.description,
                    "timestamp": risk.created_at,
                    "student_id": risk.student_id,
                }
            )

        return {
            "recent_anomalies": alerts,
            "attendance_anomaly_count": attendance_anomaly_count,
            "complaint_spike_count": complaint_spike_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching anomalies: {str(e)}")


@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    """
    Get overall analytics summary
    Key metrics and insights
    """
    try:
        # Overall metrics
        total_students = db.query(Student).count()
        total_attendance_records = db.query(Attendance).count()
        total_complaints = db.query(Complaint).count()
        total_risks = db.query(RiskLog).count()

        # Recent metrics (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_attendance = db.query(Attendance).filter(Attendance.date >= week_ago).count()
        week_complaints = db.query(Complaint).filter(Complaint.created_at >= week_ago).count()
        week_risks = db.query(RiskLog).filter(RiskLog.created_at >= week_ago).count()

        # Attendance stats
        attendance_records = db.query(Attendance).all()
        present_count = sum(1 for a in attendance_records if a.status == "Present")
        absent_count = sum(1 for a in attendance_records if a.status == "Absent")
        late_count = sum(1 for a in attendance_records if a.status == "Late")

        # Risk stats
        all_risks = db.query(RiskLog).all()
        unresolved_risks = db.query(RiskLog).filter(RiskLog.resolved == 0).count()

        # Complaint stats
        pending_complaints = db.query(Complaint).filter(Complaint.status == "Pending").count()
        resolved_complaints = db.query(Complaint).filter(Complaint.status == "Resolved").count()

        return {
            "timestamp": datetime.utcnow(),
            "overall_metrics": {
                "total_students": total_students,
                "total_attendance_records": total_attendance_records,
                "total_complaints": total_complaints,
                "total_risks": total_risks,
            },
            "weekly_metrics": {
                "attendance_records": week_attendance,
                "complaints": week_complaints,
                "risks": week_risks,
            },
            "attendance_breakdown": {
                "present": present_count,
                "absent": absent_count,
                "late": late_count,
                "total": len(attendance_records),
            },
            "complaint_breakdown": {
                "pending": pending_complaints,
                "resolved": resolved_complaints,
                "total": total_complaints,
            },
            "risk_summary": {
                "total": total_risks,
                "unresolved": unresolved_risks,
                "resolved": total_risks - unresolved_risks,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")
