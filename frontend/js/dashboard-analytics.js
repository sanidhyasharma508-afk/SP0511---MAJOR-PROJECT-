// Dashboard Analytics with Chart.js
// Integrates with backend /dashboard/student/me for authenticated live data.

// Student Data State
const studentData = {
    name: "Student",
    rollNumber: "—",
    branch: "General Studies",
    year: "Semester 1",
    attendance: null,
    cgpa: null,
    eventsParticipated: 0,
    studyHours: 0,
    attendanceGoal: 75,
    eventGoal: 15
};

// Chart instances
let attendanceChartInstance = null;
let eventChartInstance = null;
let subjectChartInstance = null;
let isFetchingDashboard = false;

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    initCharts();
    if (window.currentUser) {
        syncUserToStudentData(window.currentUser, window.currentStudent);
    }
    fetchDashboardData();
});

// React to auth lifecycle events
window.addEventListener('auth:login', function(e) {
    if (e.detail) {
        syncUserToStudentData(e.detail, window.currentStudent);
    }
    fetchDashboardData();
});

window.addEventListener('auth:ready', function(e) {
    if (window.currentUser) {
        syncUserToStudentData(window.currentUser, window.currentStudent);
    }
    fetchDashboardData();
});

function syncUserToStudentData(user, student) {
    if (!user) return;
    if (student) {
        studentData.name = student.name || user.full_name || user.username;
        studentData.rollNumber = student.roll_no || user.username;
        studentData.branch = student.department || 'General Studies';
        studentData.year = `Semester ${student.semester || 1}`;
    } else {
        studentData.name = user.full_name || user.username;
        studentData.rollNumber = user.username;
        studentData.branch = user.role ? (user.role.toUpperCase() + ' Member') : 'General';
        studentData.year = 'Active Session';
    }
    updateStudentInfo();
}

// Fetch live student dashboard from backend
async function fetchDashboardData() {
    if (isFetchingDashboard) return;
    isFetchingDashboard = true;

    const apiBase = window.location.port === '3000'
        ? '/api'
        : (window.location.origin.includes(':8000') ? '' : 'http://localhost:8000');
    
    const token = window.api ? window.api.getToken() : localStorage.getItem('access_token');
    if (!token) {
        isFetchingDashboard = false;
        return;
    }

    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };

    try {
        const response = await fetch(`${apiBase}/dashboard/student/me`, { headers });
        if (response.ok) {
            const data = await response.json();
            renderLiveDashboard(data);
        } else if (response.status === 404) {
            console.debug('No linked student record found for current account.');
            renderEmptyDashboard();
        } else if (response.status === 401) {
            console.debug('Session expired or unauthorized.');
        } else {
            console.warn(`Dashboard fetch returned status: ${response.status}`);
        }
    } catch (e) {
        console.error('Network error fetching dashboard data:', e.message || e);
    } finally {
        isFetchingDashboard = false;
    }
}

function renderLiveDashboard(data) {
    if (!data) return;

    // 1. Student profile
    if (data.student) {
        studentData.name = data.student.name;
        studentData.rollNumber = data.student.roll_no;
        studentData.branch = data.student.department;
        studentData.year = `Semester ${data.student.semester}`;
    }

    // 2. Attendance
    studentData.attendance = data.attendance?.overall_percentage ?? null;

    // 3. CGPA / Academics
    studentData.cgpa = data.academics?.cgpa ?? null;

    // 4. Tasks & Hours
    studentData.studyHours = data.study_tasks?.study_hours ?? 0;

    // 5. Events
    studentData.eventsParticipated = data.campus_involvement?.events_registered_count ?? 0;

    updateStudentInfo();
    checkAlerts(data);
    updateCharts(data);
    updateGreeting(data);
}

function renderEmptyDashboard() {
    studentData.attendance = null;
    studentData.cgpa = null;
    studentData.eventsParticipated = 0;
    studentData.studyHours = 0;
    updateStudentInfo();
}

// Update Student Information in DOM
function updateStudentInfo() {
    const setIf = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    setIf('student-name', studentData.name);
    setIf('student-branch', studentData.branch);
    setIf('student-year', studentData.year);
    setIf('student-roll', studentData.rollNumber);

    const attEl = document.getElementById('attendance-percentage');
    if (attEl) {
        attEl.textContent = studentData.attendance !== null ? `${studentData.attendance}%` : 'No records';
    }

    const cgpaEl = document.getElementById('cgpa-value');
    if (cgpaEl) {
        cgpaEl.textContent = studentData.cgpa !== null ? studentData.cgpa : 'N/A';
        cgpaEl.title = 'No examination marks are recorded in the institutional database.';
    }

    setIf('events-participated', studentData.eventsParticipated);
    setIf('study-hours', `${studentData.studyHours}h`);
}

function checkAlerts(data) {
    const attPct = studentData.attendance;
    const attendanceAlert = document.getElementById('attendance-alert');

    // 1. Attendance Alert
    if (attendanceAlert) {
        if (attPct !== null && attPct < 75) {
            attendanceAlert.style.display = 'flex';
            const total = data?.attendance?.total_sessions || 0;
            const attended = data?.attendance?.attended_sessions || 0;
            // Formula to reach 75%: (attended + x) / (total + x) >= 0.75 => x >= 3*total - 4*attended
            const classesNeeded = Math.max(1, Math.ceil(3 * total - 4 * attended));
            const neededEl = document.getElementById('classes-needed');
            if (neededEl) {
                neededEl.textContent = `${classesNeeded} more class${classesNeeded > 1 ? 'es' : ''}`;
            }
        } else {
            attendanceAlert.style.display = 'none';
        }
    }

    // 2. Academic Risk Alert (Replaces static cgpa-alert)
    const riskCard = document.getElementById('cgpa-alert');
    if (riskCard && data?.academic_risk) {
        const risk = data.academic_risk;
        if (risk.risk_level === 'HIGH' || risk.risk_level === 'MEDIUM') {
            riskCard.style.display = 'flex';
            riskCard.className = `alert-card ${risk.risk_level === 'HIGH' ? 'risk-alert' : 'goal-alert'}`;
            const titleEl = riskCard.querySelector('h4');
            const textEl = riskCard.querySelector('p');
            if (titleEl) {
                titleEl.textContent = `Academic Advisory: ${risk.risk_level} Risk (${risk.risk_score}/100)`;
            }
            if (textEl) {
                const primaryReason = risk.contributing_reasons && risk.contributing_reasons.length > 0
                    ? risk.contributing_reasons[0]
                    : 'Advisory notice based on current attendance and task engagement.';
                textEl.innerHTML = `<strong>Attention:</strong> ${primaryReason}`;
            }
        } else {
            riskCard.style.display = 'none';
        }
    }

    // 3. Event Participation
    const eventProgress = document.getElementById('event-progress');
    if (eventProgress) {
        eventProgress.textContent = `${studentData.eventsParticipated}/${studentData.eventGoal}`;
    }
}

function updateGreeting(data) {
    const greetingTitle = document.querySelector('.greeting-content h2');
    if (greetingTitle && studentData.name) {
        greetingTitle.textContent = `Welcome, ${studentData.name}! 👋`;
    }

    const greetingText = document.querySelector('.greeting-content p');
    if (greetingText && data) {
        const pendingTasks = data.study_tasks?.pending_tasks || 0;
        const totalSessions = data.attendance?.total_sessions || 0;
        const attStr = studentData.attendance !== null ? `Your attendance is currently at ${studentData.attendance}%.` : 'Class attendance is active.';
        const taskStr = pendingTasks > 0 ? ` You have ${pendingTasks} pending study task${pendingTasks > 1 ? 's' : ''}.` : ' All study tasks are up to date!';
        greetingText.textContent = `${attStr}${taskStr} Review your upcoming schedule below.`;
    }
}

// Initialize Charts
function initCharts() {
    createAttendanceChart();
    createEventChart();
    createSubjectChart();
}

function createAttendanceChart() {
    const ctx = document.getElementById('attendanceChart');
    if (!ctx) return;

    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(102, 126, 234, 0.8)');
    gradient.addColorStop(1, 'rgba(118, 75, 162, 0.2)');

    attendanceChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Session 1', 'Session 2', 'Session 3', 'Session 4', 'Session 5'],
            datasets: [{
                label: 'Attendance %',
                data: [100, 100, 100, 100, 100],
                backgroundColor: gradient,
                borderColor: '#667EEA',
                borderWidth: 3,
                fill: true,
                tension: 0.3,
                pointBackgroundColor: '#667EEA',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#a0aec0',
                        callback: val => val + '%'
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#a0aec0' }
                }
            }
        }
    });
}

function createEventChart() {
    const ctx = document.getElementById('eventChart');
    if (!ctx) return;

    eventChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Events Registered', 'Clubs Joined', 'Study Tasks Completed'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: ['#667EEA', '#F093FB', '#4FACFE'],
                borderWidth: 0,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#a0aec0', usePointStyle: true }
                }
            },
            cutout: '65%'
        }
    });
}

function createSubjectChart() {
    const ctx = document.getElementById('subjectChart');
    if (!ctx) return;

    subjectChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['No Subjects Recorded'],
            datasets: [{
                label: 'Attendance %',
                data: [0],
                backgroundColor: 'rgba(102, 126, 234, 0.8)',
                borderRadius: 8,
                barThickness: 28
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true },
                tooltip: {
                    callbacks: {
                        label: ctx => `Attendance: ${ctx.parsed.y}%`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#a0aec0',
                        callback: val => val + '%'
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#a0aec0' }
                }
            }
        }
    });
}

function updateCharts(data) {
    // 1. Update Subject Chart
    if (subjectChartInstance && data.attendance?.subjects) {
        const subjects = data.attendance.subjects;
        if (subjects.length > 0) {
            subjectChartInstance.data.labels = subjects.map(s => s.subject_code);
            subjectChartInstance.data.datasets = [{
                label: 'Verified Attendance %',
                data: subjects.map(s => s.percentage),
                backgroundColor: subjects.map(s => s.percentage < 75 ? 'rgba(245, 87, 108, 0.85)' : 'rgba(102, 126, 234, 0.85)'),
                borderRadius: 8,
                barThickness: 28
            }];
        } else {
            subjectChartInstance.data.labels = ['No Attendance Records'];
            subjectChartInstance.data.datasets = [{
                label: 'Attendance %',
                data: [0],
                backgroundColor: 'rgba(160, 174, 192, 0.5)',
                borderRadius: 8,
                barThickness: 28
            }];
        }
        subjectChartInstance.update();
    }

    // 2. Update Trend Chart
    if (attendanceChartInstance) {
        const trend = data.attendance?.trend || [];
        if (trend.length > 0) {
            attendanceChartInstance.data.labels = trend.map((t, idx) => `Sess ${idx + 1} (${t.subject_code})`);
            // Compute rolling attendance percentage
            let runningAttended = 0;
            const percentages = trend.map((t, idx) => {
                if (t.is_present) runningAttended++;
                return Math.round((runningAttended / (idx + 1)) * 100);
            });
            attendanceChartInstance.data.datasets[0].data = percentages;
        } else if (studentData.attendance !== null) {
            attendanceChartInstance.data.labels = ['Overall'];
            attendanceChartInstance.data.datasets[0].data = [studentData.attendance];
        } else {
            attendanceChartInstance.data.labels = ['No Records'];
            attendanceChartInstance.data.datasets[0].data = [0];
        }
        attendanceChartInstance.update();

        // Footer numbers
        const presEl = document.getElementById('present-days');
        if (presEl) presEl.textContent = data.attendance?.attended_sessions ?? 0;
        const absEl = document.getElementById('absent-days');
        if (absEl) absEl.textContent = data.attendance?.absent_sessions ?? 0;
    }

    // 3. Update Event / Engagement Chart
    if (eventChartInstance) {
        const evCount = data.campus_involvement?.events_registered_count || 0;
        const clubCount = data.campus_involvement?.clubs_joined_count || 0;
        const tasksCompleted = data.study_tasks?.completed_tasks || 0;

        const totalItems = evCount + clubCount + tasksCompleted;
        if (totalItems > 0) {
            eventChartInstance.data.datasets[0].data = [evCount, clubCount, tasksCompleted];
        } else {
            eventChartInstance.data.datasets[0].data = [0, 0, 0];
        }
        eventChartInstance.update();
    }
}

// Initial animations
function initializeDashboard() {
    const statItems = document.querySelectorAll('.profile-stat-item');
    statItems.forEach((item, index) => {
        setTimeout(() => {
            item.style.opacity = '0';
            item.style.transform = 'translateY(20px)';
            setTimeout(() => {
                item.style.transition = 'all 0.5s ease';
                item.style.opacity = '1';
                item.style.transform = 'translateY(0)';
            }, 50);
        }, index * 100);
    });
}
