# Campus Automation - PHASE 3: Analytics & Trend Detection

## ✅ PHASE 3 COMPLETE

All analytics, anomaly detection, and trend detection features implemented and deployed.

---

## 🎯 PHASE 3 FEATURES IMPLEMENTED

### 1. Anomaly Detection Agent
**File**: `backend/core/agents.py::AnomalyDetectionAgent`

#### Attendance Drop Detection
- **Trigger**: Monitors attendance daily
- **Logic**: Compares current day to 7-day average
- **Threshold**: 20% sudden drop = anomaly
- **Action**: Creates "Critical" severity risk log
- **Detection Method**:
  - Groups attendance by student and date
  - Calculates daily attendance rate
  - Compares today vs previous 6 days average
  - If drop >= 20% → Critical risk log created
  - Logs include percentage comparison

#### Complaint Spike Detection
- **Trigger**: Monitors complaint filings daily
- **Logic**: Compares today vs yesterday
- **Threshold**: 3+ complaints per day = spike
- **Action**: Creates "High" severity risk log
- **Detection Method**:
  - Counts complaints per day
  - Compares with previous day
  - Calculates percentage increase
  - If >= threshold → Risk log with spike details
  - Recommends dean notification

### 2. Trend Detection Agent
**File**: `backend/core/agents.py::TrendDetectionAgent`

#### Attendance Trends
- **Calculation**: Student-level 30-day analysis
- **Daily Data**: Present count, total classes, attendance percentage
- **Moving Average**: 7-day smoothed trend line
- **Trend Slope**: Linear regression slope (improving/declining/stable)
- **Returns**:
  ```json
  {
    "student_id": 1,
    "daily_data": [
      {"date": "2026-01-20", "attendance_rate": 0.85, "present": 17, "total": 20}
    ],
    "moving_average": [0.85, 0.84, 0.83, ...],
    "trend_slope": -0.002,
    "trend_direction": "declining"
  }
  ```

#### Complaint Trends
- **Calculation**: System-wide weekly aggregation
- **Weekly Data**: Total, urgent, high, medium, low priority counts
- **Moving Average**: 7-week smoothed trend
- **Trend Slope**: Linear regression (increasing/decreasing/stable)
- **Returns**:
  ```json
  {
    "weekly_data": [
      {"week": "2026-W03", "total": 5, "urgent": 1, "high": 2, "medium": 2, "low": 0}
    ],
    "moving_average": [5.0, 5.2, 4.8, ...],
    "trend_slope": 0.15,
    "trend_direction": "increasing"
  }
  ```

---

## 📊 ANALYTICS APIS

### Core Analytics Endpoints

#### 1. Attendance Trends
```
GET /analytics/attendance-trends/{student_id}?days=30
```
**Returns**: Student's attendance trend with moving average and direction

**Example Response**:
```json
{
  "student_id": 1,
  "period_days": 30,
  "daily_data": [
    {
      "date": "2026-01-20",
      "attendance_rate": 0.85,
      "present": 17,
      "total": 20
    }
  ],
  "moving_average": [0.85, 0.84, 0.83],
  "trend_slope": -0.002,
  "trend_direction": "declining"
}
```

#### 2. Complaint Heatmap
```
GET /analytics/complaint-heatmap?days=30
```
**Returns**: When complaints are filed (day/hour pattern)

**Features**:
- Heatmap grid: 7 days × 24 hours
- Intensity values (0-1) showing complaint frequency
- Top complaint categories
- Top complaint filing times

**Example Response**:
```json
{
  "period_days": 30,
  "total_complaints": 45,
  "heatmap": [
    {
      "day_of_week": "Monday",
      "hour": 9,
      "count": 3,
      "intensity": 0.75
    }
  ],
  "top_categories": {
    "Academic": 28,
    "Conduct": 10,
    "Health": 7
  },
  "top_times": [
    {"time": "Monday 10:00", "count": 5},
    {"time": "Friday 14:00", "count": 4}
  ]
}
```

#### 3. Risk Distribution
```
GET /analytics/risk-distribution
```
**Returns**: How risks are distributed across types and severity

**Example Response**:
```json
{
  "total_risks": 25,
  "unresolved_risks": 18,
  "resolved_risks": 7,
  "risk_distribution": [
    {
      "risk_type": "Attendance",
      "count": 15,
      "percentage": 60.0,
      "severity_breakdown": {
        "High": 8,
        "Medium": 7
      }
    },
    {
      "risk_type": "Academic",
      "count": 10,
      "percentage": 40.0,
      "severity_breakdown": {
        "High": 6,
        "Medium": 4
      }
    }
  ],
  "severity_distribution": {
    "High": 14,
    "Medium": 11,
    "Low": 0
  },
  "top_affected_students": [
    {
      "student_id": 1,
      "student_name": "John Doe",
      "risk_count": 5
    }
  ]
}
```

#### 4. Complaint Trends
```
GET /analytics/complaint-trends?days=30
```
**Returns**: Complaint trend over time with weekly aggregation

**Example Response**:
```json
{
  "period_days": 30,
  "total_complaints": 42,
  "weekly_data": [
    {
      "week": "2026-W03",
      "total": 12,
      "urgent": 2,
      "high": 4,
      "medium": 5,
      "low": 1
    }
  ],
  "moving_average": [12.0, 11.5, 11.2],
  "trend_slope": -0.15,
  "trend_direction": "decreasing"
}
```

#### 5. Anomalies (Auto-Detected)
```
GET /analytics/anomalies?days=7
```
**Returns**: Recent anomalies detected by system

**Example Response**:
```json
{
  "recent_anomalies": [
    {
      "type": "attendance_drop",
      "severity": "Critical",
      "description": "ANOMALY: Sudden attendance drop! Previous: 85%, Today: 60%",
      "timestamp": "2026-01-20T10:30:00",
      "student_id": 5
    },
    {
      "type": "complaint_spike",
      "severity": "High",
      "description": "ANOMALY: Complaint spike detected! 5 complaints filed today vs 1 yesterday (+400%)",
      "timestamp": "2026-01-19T14:15:00",
      "student_id": null
    }
  ],
  "attendance_anomaly_count": 2,
  "complaint_spike_count": 1
}
```

#### 6. Manual Anomaly Detection Trigger
```
POST /analytics/detect-anomalies
```
**Returns**: Manually triggers detection algorithms

**Example Response**:
```json
{
  "status": "anomaly detection completed",
  "anomalies_detected": 3,
  "details": [
    {
      "type": "attendance_anomaly",
      "severity": "Critical",
      "description": "...",
      "timestamp": "2026-01-20T10:30:00"
    }
  ]
}
```

#### 7. Analytics Summary
```
GET /analytics/summary
```
**Returns**: Overall analytics summary and key metrics

**Example Response**:
```json
{
  "timestamp": "2026-01-20T15:30:00",
  "overall_metrics": {
    "total_students": 50,
    "total_attendance_records": 2500,
    "total_complaints": 42,
    "total_risks": 25
  },
  "weekly_metrics": {
    "attendance_records": 350,
    "complaints": 8,
    "risks": 3
  },
  "attendance_breakdown": {
    "present": 2100,
    "absent": 300,
    "late": 100,
    "total": 2500
  },
  "complaint_breakdown": {
    "pending": 12,
    "resolved": 30,
    "total": 42
  },
  "risk_summary": {
    "total": 25,
    "unresolved": 18,
    "resolved": 7
  }
}
```

---

## 🔧 ALGORITHMS & FORMULAS

### Attendance Trend Slope (Linear Regression)
```
For each student over N days:
  daily_rate[i] = present_count[i] / total_count[i]
  
Linear Regression:
  slope = Σ(x - x̄)(y - ȳ) / Σ(x - x̄)²
  
Where:
  x = day number (0 to N)
  y = daily_rate
  x̄ = mean of x
  ȳ = mean of y
  
Result:
  slope > 0  → attendance improving ✓
  slope < 0  → attendance declining ✗
  slope ≈ 0  → attendance stable →
```

### Moving Average (7-day/7-week)
```
For each point i in data:
  window = data[max(0, i-6):i+1]
  moving_avg[i] = Σwindow / len(window)
  
Smooths short-term fluctuations to show overall trend
```

### Attendance Anomaly Detection
```
previous_avg = mean(attendance_rate[day-7 to day-1])
today_rate = attendance_rate[today]

drop_rate = (previous_avg - today_rate) / previous_avg

IF drop_rate >= 0.20:  # 20% drop
  → CRITICAL ANOMALY
  Create risk log with severity "Critical"
```

### Complaint Spike Detection
```
today_count = COUNT(complaints filed today)
yesterday_count = COUNT(complaints filed yesterday)

IF today_count >= 3:
  spike_percent = ((today_count - yesterday_count) / yesterday_count) * 100
  → HIGH SPIKE ANOMALY
  Create risk log with severity "High"
```

### Heatmap Intensity
```
For each hour of each day:
  count = number of complaints at that time
  
intensity = count / max_count
  
Result: 0 to 1 scale
  0.0 = no complaints
  1.0 = highest complaint time
```

---

## 📈 TREND INTERPRETATION GUIDE

### Attendance Trends
| Trend Slope | Direction | Interpretation |
|------------|-----------|-----------------|
| > 0.01 | Improving | Attendance getting better ✓ |
| -0.01 to 0.01 | Stable | Attendance consistent → |
| < -0.01 | Declining | Attendance getting worse ✗ |

### Complaint Trends
| Trend Slope | Direction | Interpretation |
|------------|-----------|-----------------|
| > 0.1 | Increasing | More complaints coming in ⚠️ |
| -0.1 to 0.1 | Stable | Consistent complaint rate → |
| < -0.1 | Decreasing | Fewer complaints ✓ |

### Heatmap Intensity
| Intensity | Meaning |
|-----------|---------|
| 0.8 - 1.0 | Hot spot - many complaints |
| 0.5 - 0.8 | Warm - moderate activity |
| 0.2 - 0.5 | Cool - low activity |
| 0.0 - 0.2 | Cold - very few complaints |

---

## 🔌 ANALYTICS INTEGRATION WITH AGENTS

### Data Flow
```
Database Updates
    ↓
Scheduled Analytics Run (or manual trigger)
    ↓
TrendDetectionAgent Calculates Trends
    ↓
AnomalyDetectionAgent Detects Anomalies
    ↓
Risk Logs Created if Anomalies Found
    ↓
Frontend Fetches Via Analytics APIs
    ↓
Dashboard Displays Insights
```

---

## 🎯 USE CASES & INSIGHTS

### 1. Early Warning System
**Use Case**: Detect students at risk before crisis
```
Attendance trend declining? → Notify parents
Sudden drop detected? → Immediate intervention
```

### 2. Resource Planning
**Use Case**: Understand peak complaint times
```
Most complaints on Mondays 10am?
→ Increase admin staff at that time
```

### 3. Pattern Recognition
**Use Case**: Identify systemic issues
```
All risks in "Academic" category?
→ Curriculum might need review
```

### 4. Predictive Insights
**Use Case**: Forecast future trends
```
Complaint trend increasing?
→ Campus may need more support services
```

### 5. Student Intervention
**Use Case**: Personalized support
```
Student's attendance declining for 2 weeks?
→ Schedule meeting with academic advisor
```

---

## 📊 EXAMPLE ANALYTICS WORKFLOW

### Scenario: Monitor Class A for Attendance Issues

**Step 1**: Get attendance trends
```
GET /analytics/attendance-trends/1?days=30
```
Response shows: trend_direction = "declining"

**Step 2**: Check for anomalies
```
GET /analytics/anomalies?days=7
```
Response shows: attendance_drop anomaly for student 1

**Step 3**: View risk distribution
```
GET /analytics/risk-distribution
```
Response shows: 60% of risks are "Attendance" type

**Step 4**: Take action
- Contact student
- Provide support
- Monitor next week
- Verify trend improves

---

## 🔍 TECHNICAL DETAILS

### Time Complexity
- Attendance trends: O(n) where n = days
- Complaint heatmap: O(m) where m = complaints
- Risk distribution: O(r) where r = risk logs
- All algorithms: Linear time, no ML overhead

### Storage Requirements
- No additional tables needed
- Calculated on-the-fly from existing data
- Results cached in memory during request
- No persistent analytics storage

### Performance Considerations
- Trends calculated for specific time periods
- Configurable lookback windows (default 30 days)
- Heatmap uses simple counting (fast)
- No heavy computations, all rule-based

---

## 🚀 DEPLOYMENT CHECKLIST

- ✅ AnomalyDetectionAgent implemented
- ✅ TrendDetectionAgent implemented
- ✅ Analytics routes created
- ✅ All 7 analytics endpoints deployed
- ✅ Schemas for all response types created
- ✅ Server running on 127.0.0.1:8000
- ✅ Swagger /docs shows all analytics endpoints
- ✅ Anomaly detection rules configured
- ✅ Trend calculation algorithms implemented
- ✅ Error handling in place

---

## 📋 ANALYTICS ENDPOINTS SUMMARY

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/analytics/attendance-trends/{id}` | GET | Student attendance trend |
| `/analytics/complaint-trends` | GET | System complaint trends |
| `/analytics/complaint-heatmap` | GET | Complaint pattern heatmap |
| `/analytics/risk-distribution` | GET | Risk type distribution |
| `/analytics/anomalies` | GET | Recent detected anomalies |
| `/analytics/detect-anomalies` | POST | Trigger detection manually |
| `/analytics/summary` | GET | Overall analytics summary |

---

## 🎉 PHASE 3 STATUS: COMPLETE ✅

**All requirements fulfilled:**
- ✅ Anomaly Detection Agent (attendance drops + complaint spikes)
- ✅ Trend Detection Agent (weekly/monthly aggregation, moving averages)
- ✅ Analytics APIs (3 core + 4 supporting endpoints)
- ✅ Rule-based detection (no ML)
- ✅ Growth & decline detection
- ✅ Integration with existing system

**Backend now provides complete analytics capabilities!** 📊
