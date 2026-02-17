// Dashboard Analytics with Chart.js

// Student Data (Mock - replace with API calls)
const studentData = {
    name: "Alex Johnson",
    rollNumber: "21BCS101",
    branch: "Computer Science Engineering",
    year: "3rd Year",
    attendance: 85.5,
    cgpa: 8.9,
    eventsParticipated: 12,
    studyHours: 124,
    attendanceGoal: 75,
    eventGoal: 15
};

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    createAttendanceChart();
    createEventChart();
    createSubjectChart();
    checkAlerts();
    updateStudentInfo();
});

// Update Student Information
function updateStudentInfo() {
    document.getElementById('student-name').textContent = studentData.name;
    document.getElementById('student-branch').textContent = studentData.branch;
    document.getElementById('student-year').textContent = studentData.year;
    document.getElementById('student-roll').textContent = studentData.rollNumber;
    document.getElementById('attendance-percentage').textContent = studentData.attendance + '%';
    document.getElementById('cgpa-value').textContent = studentData.cgpa;
    document.getElementById('events-participated').textContent = studentData.eventsParticipated;
    document.getElementById('study-hours').textContent = studentData.studyHours + 'h';
}

// Check and Display Alerts
function checkAlerts() {
    // Attendance Alert
    const attendanceAlert = document.getElementById('attendance-alert');
    if (studentData.attendance < 75) {
        attendanceAlert.style.display = 'flex';
        const classesNeeded = Math.ceil((75 - studentData.attendance) * 2);
        document.getElementById('classes-needed').textContent = classesNeeded + ' more classes';
    }

    // CGPA Goal Alert
    const cgpaAlert = document.getElementById('cgpa-alert');
    if (studentData.cgpa >= 8.8 && studentData.cgpa < 9.0) {
        cgpaAlert.style.display = 'flex';
    }

    // Event Participation Goal
    const eventGoal = document.getElementById('event-goal');
    const eventProgress = document.getElementById('event-progress');
    eventProgress.textContent = `${studentData.eventsParticipated}/${studentData.eventGoal}`;
}

// Initialize Dashboard
function initializeDashboard() {
    console.log('Dashboard Analytics Initialized');
    
    // Animate stat cards on load
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

// Attendance Trend Chart
function createAttendanceChart() {
    const ctx = document.getElementById('attendanceChart');
    if (!ctx) return;

    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(102, 126, 234, 0.8)');
    gradient.addColorStop(1, 'rgba(118, 75, 162, 0.2)');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
            datasets: [{
                label: 'Attendance %',
                data: [78, 80, 82, 83, 84, 85.5],
                backgroundColor: gradient,
                borderColor: '#667EEA',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#667EEA',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    cornerRadius: 8,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return 'Attendance: ' + context.parsed.y + '%';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    min: 70,
                    max: 100,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#a0aec0',
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#a0aec0'
                    }
                }
            }
        }
    });
}

// Event Participation Chart
function createEventChart() {
    const ctx = document.getElementById('eventChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Technical', 'Cultural', 'Sports', 'Social Service'],
            datasets: [{
                data: [5, 4, 3, 2],
                backgroundColor: [
                    '#667EEA',
                    '#F093FB',
                    '#4FACFE',
                    '#FA709A'
                ],
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#a0aec0',
                        padding: 15,
                        font: {
                            size: 12
                        },
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return label + ': ' + value + ' events (' + percentage + '%)';
                        }
                    }
                }
            },
            cutout: '65%'
        }
    });
}

// Subject-wise Performance Chart
function createSubjectChart() {
    const ctx = document.getElementById('subjectChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Data Structures', 'Database Systems', 'Operating Systems', 'Computer Networks', 'Web Tech', 'Software Eng'],
            datasets: [{
                label: 'Attendance %',
                data: [88, 92, 85, 90, 87, 84],
                backgroundColor: 'rgba(102, 126, 234, 0.8)',
                borderRadius: 8,
                barThickness: 30
            }, {
                label: 'Marks %',
                data: [85, 90, 82, 88, 86, 83],
                backgroundColor: 'rgba(240, 147, 251, 0.8)',
                borderRadius: 8,
                barThickness: 30
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    cornerRadius: 8
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#a0aec0',
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#a0aec0',
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

// Period filter handlers
document.addEventListener('change', function(e) {
    if (e.target.id === 'attendance-period') {
        console.log('Attendance period changed to:', e.target.value);
        // Update attendance chart based on period
    }
    
    if (e.target.id === 'event-period') {
        console.log('Event period changed to:', e.target.value);
        // Update event chart based on period
    }
});

// Alert action handlers
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('alert-action')) {
        const alertCard = e.target.closest('.alert-card');
        if (alertCard) {
            const alertType = alertCard.id;
            console.log('Alert action clicked:', alertType);
            
            // Handle different alert actions
            if (alertType === 'attendance-alert') {
                // Navigate to attendance section
                document.querySelector('[data-section="attendance"]')?.click();
            } else if (alertType === 'event-goal') {
                // Navigate to clubs section
                document.querySelector('[data-section="clubs"]')?.click();
            }
        }
    }
});

// Export data function (for future use)
function exportDashboardData() {
    const data = {
        student: studentData,
        timestamp: new Date().toISOString()
    };
    
    const dataStr = JSON.stringify(data, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = 'dashboard-data.json';
    link.click();
}

// Print dashboard (for future use)
function printDashboard() {
    window.print();
}
