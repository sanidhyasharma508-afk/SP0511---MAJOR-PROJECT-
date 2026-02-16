"""
Core Backend Agents
Rule-based agents that respond to events and trigger actions
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.core.event_bus import Event, EventType
from backend.models.risk import RiskLog
from backend.models.attendance import Attendance
from backend.models.complaint import Complaint

logger = logging.getLogger(__name__)


class AttendanceRiskAgent:
    """
    Monitors attendance patterns and flags students at risk
    Trigger: AttendanceMarked event
    """

    ATTENDANCE_THRESHOLD = 0.75  # 75% attendance required
    LOOKBACK_DAYS = 30

    @staticmethod
    def handle_attendance_marked(event: Event, db: Session):
        """
        Handle attendance marked event
        Logic: If attendance < threshold → mark student at risk
        """
        try:
            student_id = event.data.get("student_id")
            attendance_status = event.data.get("status")

            # Query last 30 days of attendance
            cutoff_date = datetime.utcnow() - timedelta(days=AttendanceRiskAgent.LOOKBACK_DAYS)
            attendance_records = (
                db.query(Attendance)
                .filter(Attendance.student_id == student_id, Attendance.date >= cutoff_date)
                .all()
            )

            if not attendance_records:
                return

            # Calculate attendance percentage
            present_count = sum(1 for r in attendance_records if r.status == "Present")
            attendance_ratio = present_count / len(attendance_records)

            # Check if at risk
            if attendance_ratio < AttendanceRiskAgent.ATTENDANCE_THRESHOLD:
                # Check if risk log already exists for today
                today = datetime.utcnow().date()
                existing_risk = (
                    db.query(RiskLog)
                    .filter(
                        RiskLog.student_id == student_id,
                        RiskLog.risk_type == "Attendance",
                        RiskLog.resolved == 0,
                    )
                    .first()
                )

                if not existing_risk:
                    risk_log = RiskLog(
                        student_id=student_id,
                        risk_type="Attendance",
                        severity="High" if attendance_ratio < 0.6 else "Medium",
                        description=f"Low attendance detected. Current: {attendance_ratio*100:.1f}% (Threshold: {AttendanceRiskAgent.ATTENDANCE_THRESHOLD*100:.1f}%)",
                        action_taken="Flagged for monitoring",
                    )
                    db.add(risk_log)
                    db.commit()
                    logger.info(
                        f"Risk log created for student {student_id} - Attendance: {attendance_ratio*100:.1f}%"
                    )
        except Exception as e:
            logger.error(f"Error in AttendanceRiskAgent: {e}")


class ComplaintTriageAgent:
    """
    Automatically categorizes and prioritizes complaints
    Trigger: ComplaintFiled event
    """

    PRIORITY_KEYWORDS = {
        "high": ["urgent", "critical", "emergency", "serious", "severe", "immediate"],
        "medium": ["important", "significant", "issue", "problem", "concern"],
        "low": ["minor", "small", "feedback", "suggestion", "note"],
    }

    CATEGORY_KEYWORDS = {
        "Academic": [
            "exam",
            "grade",
            "subject",
            "course",
            "class",
            "assignment",
            "marks",
            "result",
        ],
        "Conduct": ["behavior", "discipline", "misconduct", "harassment", "bullying", "violence"],
        "Health": ["sick", "ill", "health", "medical", "injury", "accident", "doctor", "hospital"],
        "Other": [],
    }

    @staticmethod
    def handle_complaint_filed(event: Event, db: Session):
        """
        Handle complaint filed event
        Logic: Categorize complaint, assign priority
        """
        try:
            complaint_id = event.data.get("complaint_id")
            title = event.data.get("title", "").lower()
            description = event.data.get("description", "").lower()

            # Get complaint from database
            complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
            if not complaint:
                return

            # Determine priority based on keywords
            text = f"{title} {description}"
            priority = "Normal"
            for level, keywords in ComplaintTriageAgent.PRIORITY_KEYWORDS.items():
                if any(keyword in text for keyword in keywords):
                    priority = level.capitalize()
                    break

            # Auto-categorize if not already set
            if complaint.category == "Other":
                for category, keywords in ComplaintTriageAgent.CATEGORY_KEYWORDS.items():
                    if category != "Other" and any(keyword in text for keyword in keywords):
                        complaint.category = category
                        break

            # Update priority
            complaint.priority = priority
            complaint.updated_at = datetime.utcnow()
            db.commit()

            logger.info(
                f"Complaint {complaint_id} triaged - Category: {complaint.category}, Priority: {priority}"
            )
        except Exception as e:
            logger.error(f"Error in ComplaintTriageAgent: {e}")


class SchedulerConflictAgent:
    """
    Detects time clashes and room conflicts in schedules
    Trigger: ScheduleUpdated event
    """

    @staticmethod
    def handle_schedule_updated(event: Event, db: Session):
        """
        Handle schedule updated event
        Logic: Detect time clashes and room conflicts
        """
        try:
            from backend.models.schedule import Schedule

            schedule_id = event.data.get("schedule_id")
            schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule:
                return

            # Find overlapping schedules for the same location
            conflicts = (
                db.query(Schedule)
                .filter(
                    Schedule.id != schedule_id,
                    Schedule.location == schedule.location,
                    Schedule.is_active == 1,
                    Schedule.start_date < schedule.end_date,
                    Schedule.end_date > schedule.start_date,
                )
                .all()
            )

            if conflicts:
                for conflict in conflicts:
                    # Create risk log for conflict
                    conflict_desc = f"Schedule conflict detected: '{schedule.title}' overlaps with '{conflict.title}' at {schedule.location}"

                    risk_log = RiskLog(
                        student_id=None,
                        risk_type="Academic",
                        severity="High",
                        description=conflict_desc,
                        action_taken="Conflict logged - Awaiting resolution",
                    )
                    db.add(risk_log)

                db.commit()
                logger.warning(f"Found {len(conflicts)} conflicts for schedule {schedule_id}")
        except Exception as e:
            logger.error(f"Error in SchedulerConflictAgent: {e}")


class AnomalyDetectionAgent:
    """
    Detects anomalies in attendance and complaints
    Rules: Sudden drops in attendance, complaint spikes
    """

    ATTENDANCE_DROP_THRESHOLD = 0.2  # 20% drop is anomaly
    COMPLAINT_SPIKE_THRESHOLD = 3  # 3+ complaints in a day

    @staticmethod
    def detect_attendance_anomalies(db: Session):
        """
        Detect sudden drops in attendance
        Compares today's absence rate with last 7 days average
        """
        try:
            from collections import defaultdict

            today = datetime.utcnow().date()
            week_ago = today - timedelta(days=7)

            # Get attendance records for last 7 days grouped by student
            recent_records = (
                db.query(Attendance)
                .filter(Attendance.date >= datetime.combine(week_ago, datetime.min.time()))
                .all()
            )

            student_attendance = defaultdict(list)
            for record in recent_records:
                student_attendance[record.student_id].append(
                    {"date": record.date.date(), "status": record.status}
                )

            # Analyze each student
            for student_id, records in student_attendance.items():
                if len(records) < 2:
                    continue

                # Separate by date
                daily_stats = defaultdict(lambda: {"present": 0, "total": 0})
                for record in records:
                    daily_stats[record["date"]]["total"] += 1
                    if record["status"] == "Present":
                        daily_stats[record["date"]]["present"] += 1

                if len(daily_stats) < 2:
                    continue

                dates = sorted(daily_stats.keys())

                # Calculate attendance rate for previous 6 days
                prev_attendance_rate = 0
                for date in dates[:-1]:
                    stats = daily_stats[date]
                    if stats["total"] > 0:
                        prev_attendance_rate += stats["present"] / stats["total"]

                prev_attendance_rate /= len(dates) - 1

                # Check today's attendance rate
                today_stats = daily_stats.get(today)
                if today_stats and today_stats["total"] > 0:
                    today_rate = today_stats["present"] / today_stats["total"]

                    # Detect anomaly
                    if prev_attendance_rate > 0:
                        drop_rate = (prev_attendance_rate - today_rate) / prev_attendance_rate

                        if drop_rate >= AnomalyDetectionAgent.ATTENDANCE_DROP_THRESHOLD:
                            # Create anomaly risk log
                            anomaly_risk = RiskLog(
                                student_id=student_id,
                                risk_type="Attendance",
                                severity="Critical",
                                description=f"ANOMALY: Sudden attendance drop detected! Previous: {prev_attendance_rate*100:.1f}%, Today: {today_rate*100:.1f}%",
                                action_taken="Flagged for immediate review",
                            )
                            db.add(anomaly_risk)
                            logger.warning(f"Attendance anomaly detected for student {student_id}")

                db.commit()
        except Exception as e:
            logger.error(f"Error in attendance anomaly detection: {e}")

    @staticmethod
    def detect_complaint_spikes(db: Session):
        """
        Detect spikes in complaint filing
        Threshold: 3+ complaints in a day
        """
        try:
            today = datetime.utcnow().date()

            # Count complaints filed today
            today_complaints = (
                db.query(Complaint)
                .filter(
                    Complaint.created_at >= datetime.combine(today, datetime.min.time()),
                    Complaint.created_at
                    < datetime.combine(today + timedelta(days=1), datetime.min.time()),
                )
                .count()
            )

            # Get yesterday's complaint count
            yesterday = today - timedelta(days=1)
            yesterday_complaints = (
                db.query(Complaint)
                .filter(
                    Complaint.created_at >= datetime.combine(yesterday, datetime.min.time()),
                    Complaint.created_at < datetime.combine(today, datetime.min.time()),
                )
                .count()
            )

            # Detect spike
            if today_complaints >= AnomalyDetectionAgent.COMPLAINT_SPIKE_THRESHOLD:
                spike_percent = (
                    (today_complaints - yesterday_complaints) / max(yesterday_complaints, 1)
                ) * 100

                anomaly_risk = RiskLog(
                    student_id=None,
                    risk_type="Academic",
                    severity="High",
                    description=f"ANOMALY: Complaint spike detected! {today_complaints} complaints filed today vs {yesterday_complaints} yesterday (+{spike_percent:.0f}%)",
                    action_taken="Spike logged - Dean notification recommended",
                )
                db.add(anomaly_risk)
                db.commit()
                logger.warning(f"Complaint spike detected: {today_complaints} complaints today")
        except Exception as e:
            logger.error(f"Error in complaint spike detection: {e}")


class TrendDetectionAgent:
    """
    Detects trends in attendance, complaints, and risk
    Calculates moving averages and growth rates
    """

    MOVING_AVERAGE_DAYS = 7

    @staticmethod
    def calculate_attendance_trend(student_id: int, db: Session, days: int = 30):
        """
        Calculate attendance trend for a student
        Returns: trend data with moving average
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            records = (
                db.query(Attendance)
                .filter(Attendance.student_id == student_id, Attendance.date >= cutoff_date)
                .order_by(Attendance.date)
                .all()
            )

            if not records:
                return None

            # Group by date and calculate daily attendance rate
            from collections import defaultdict

            daily_attendance = defaultdict(lambda: {"present": 0, "total": 0})

            for record in records:
                date_key = record.date.date()
                daily_attendance[date_key]["total"] += 1
                if record.status == "Present":
                    daily_attendance[date_key]["present"] += 1

            # Calculate daily rates
            dates = sorted(daily_attendance.keys())
            daily_rates = []

            for date in dates:
                stats = daily_attendance[date]
                if stats["total"] > 0:
                    rate = stats["present"] / stats["total"]
                    daily_rates.append(
                        {
                            "date": str(date),
                            "attendance_rate": round(rate, 4),
                            "present": stats["present"],
                            "total": stats["total"],
                        }
                    )

            # Calculate moving averages
            moving_avg = []
            for i in range(len(daily_rates)):
                window_start = max(0, i - TrendDetectionAgent.MOVING_AVERAGE_DAYS + 1)
                window = daily_rates[window_start : i + 1]
                avg_rate = sum(r["attendance_rate"] for r in window) / len(window)
                moving_avg.append(round(avg_rate, 4))

            # Calculate trend (linear regression slope)
            if len(daily_rates) > 1:
                x = list(range(len(daily_rates)))
                y = [r["attendance_rate"] for r in daily_rates]

                n = len(x)
                x_mean = sum(x) / n
                y_mean = sum(y) / n

                numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
                denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

                trend_slope = numerator / denominator if denominator != 0 else 0
            else:
                trend_slope = 0

            return {
                "student_id": student_id,
                "period_days": days,
                "daily_data": daily_rates,
                "moving_average": moving_avg,
                "trend_slope": round(trend_slope, 6),
                "trend_direction": (
                    "improving" if trend_slope > 0 else "declining" if trend_slope < 0 else "stable"
                ),
            }
        except Exception as e:
            logger.error(f"Error calculating attendance trend: {e}")
            return None

    @staticmethod
    def calculate_complaint_trend(db: Session, days: int = 30):
        """
        Calculate complaint trend for entire system
        Returns: trend data with weekly aggregation
        """
        try:
            from collections import defaultdict

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            complaints = (
                db.query(Complaint)
                .filter(Complaint.created_at >= cutoff_date)
                .order_by(Complaint.created_at)
                .all()
            )

            # Group by week
            weekly_data = defaultdict(
                lambda: {"total": 0, "urgent": 0, "high": 0, "medium": 0, "low": 0}
            )

            for complaint in complaints:
                week_num = complaint.created_at.isocalendar()[1]
                year = complaint.created_at.year
                week_key = f"{year}-W{week_num}"

                weekly_data[week_key]["total"] += 1
                if complaint.priority == "Urgent":
                    weekly_data[week_key]["urgent"] += 1
                elif complaint.priority == "High":
                    weekly_data[week_key]["high"] += 1
                elif complaint.priority == "Normal":
                    weekly_data[week_key]["medium"] += 1
                else:
                    weekly_data[week_key]["low"] += 1

            weeks = sorted(weekly_data.keys())

            # Calculate moving average
            moving_avg = []
            for i in range(len(weeks)):
                window_start = max(0, i - TrendDetectionAgent.MOVING_AVERAGE_DAYS // 7)
                window = [weekly_data[weeks[j]]["total"] for j in range(window_start, i + 1)]
                avg_count = sum(window) / len(window)
                moving_avg.append(round(avg_count, 2))

            # Calculate trend
            if len(weeks) > 1:
                x = list(range(len(weeks)))
                y = [weekly_data[weeks[i]]["total"] for i in range(len(weeks))]

                n = len(x)
                x_mean = sum(x) / n
                y_mean = sum(y) / n

                numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
                denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

                trend_slope = numerator / denominator if denominator != 0 else 0
            else:
                trend_slope = 0

            weekly_summary = []
            for i, week in enumerate(weeks):
                weekly_summary.append(
                    {
                        "week": week,
                        "total": weekly_data[week]["total"],
                        "urgent": weekly_data[week]["urgent"],
                        "high": weekly_data[week]["high"],
                        "medium": weekly_data[week]["medium"],
                        "low": weekly_data[week]["low"],
                    }
                )

            return {
                "period_days": days,
                "total_complaints": len(complaints),
                "weekly_data": weekly_summary,
                "moving_average": moving_avg,
                "trend_slope": round(trend_slope, 6),
                "trend_direction": (
                    "increasing"
                    if trend_slope > 0
                    else "decreasing" if trend_slope < 0 else "stable"
                ),
            }
        except Exception as e:
            logger.error(f"Error calculating complaint trend: {e}")
            return None
