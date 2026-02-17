// Schedule Management JavaScript

const API_BASE = 'http://localhost:8000/schedule-management';

// Initialize Schedule Management
document.addEventListener('DOMContentLoaded', function() {
    loadAnnouncements();
    loadFeedbackStats();
    setupFormSubmission();
    setupAnnouncementForm();
});

// Load and display announcements
async function loadAnnouncements() {
    try {
        const response = await fetch(`${API_BASE}/announcements?active_only=true`);
        const announcements = await response.json();
        
        const container = document.getElementById('announcements-container');
        if (!container) return;
        
        if (announcements.length === 0) {
            container.innerHTML = '<p class="no-announcements">No active announcements at this time.</p>';
            return;
        }
        
        container.innerHTML = announcements.map(announcement => `
            <div class="announcement-card priority-${announcement.priority}">
                <div class="announcement-header">
                    <span class="priority-badge ${announcement.priority}">${announcement.priority.toUpperCase()}</span>
                    <span class="announcement-date">${formatDate(announcement.created_at)}</span>
                </div>
                <h4 class="announcement-title">${announcement.title}</h4>
                <p class="announcement-content">${announcement.content}</p>
                <div class="announcement-footer">
                    <span class="announcement-author">
                        <i class="fas fa-user-tie"></i> ${announcement.author}
                    </span>
                    <span class="announcement-audience">
                        <i class="fas fa-users"></i> ${announcement.target_audience}
                    </span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading announcements:', error);
    }
}

// Setup feedback form submission
function setupFormSubmission() {
    const form = document.getElementById('schedule-feedback-form');
    if (!form) return;
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = {
            name: document.getElementById('student-name').value,
            roll_number: document.getElementById('roll-number').value,
            issue_type: document.getElementById('issue-type').value,
            preferred_timing: document.getElementById('preferred-timing').value || null,
            additional_comments: document.getElementById('additional-comments').value || null
        };
        
        try {
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
            
            const response = await fetch(`${API_BASE}/feedback`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });
            
            if (!response.ok) {
                throw new Error('Failed to submit feedback');
            }
            
            const result = await response.json();
            
            // Show success message with notification preview
            showNotificationModal(result);
            
            // Reset form
            form.reset();
            
            // Update stats
            loadFeedbackStats();
            
        } catch (error) {
            console.error('Error submitting feedback:', error);
            showAlert('Error submitting feedback. Please try again.', 'error');
        } finally {
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Feedback';
        }
    });
}

// Show notification modal with generated messages
function showNotificationModal(result) {
    const modal = document.createElement('div');
    modal.className = 'notification-modal';
    modal.innerHTML = `
        <div class="notification-modal-content">
            <div class="notification-modal-header">
                <h3><i class="fas fa-check-circle"></i> Feedback Submitted Successfully!</h3>
                <button class="close-modal" onclick="this.closest('.notification-modal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="notification-modal-body">
                <p class="success-message">${result.message}</p>
                
                <div class="notification-tabs">
                    <button class="notification-tab-btn active" data-tab="whatsapp">
                        <i class="fab fa-whatsapp"></i> WhatsApp
                    </button>
                    <button class="notification-tab-btn" data-tab="telegram">
                        <i class="fab fa-telegram"></i> Telegram
                    </button>
                    <button class="notification-tab-btn" data-tab="email">
                        <i class="fas fa-envelope"></i> Email
                    </button>
                </div>
                
                <div class="notification-preview active" id="whatsapp-preview">
                    <h4>WhatsApp Message</h4>
                    <pre class="message-preview">${result.whatsapp_message}</pre>
                    <button class="btn btn-success" onclick="copyToClipboard('${escapeHtml(result.whatsapp_message)}', 'WhatsApp')">
                        <i class="fas fa-copy"></i> Copy Message
                    </button>
                </div>
                
                <div class="notification-preview" id="telegram-preview">
                    <h4>Telegram Message</h4>
                    <pre class="message-preview">${result.telegram_message}</pre>
                    <button class="btn btn-success" onclick="copyToClipboard('${escapeHtml(result.telegram_message)}', 'Telegram')">
                        <i class="fas fa-copy"></i> Copy Message
                    </button>
                </div>
                
                <div class="notification-preview" id="email-preview">
                    <h4>Email</h4>
                    <p><strong>Subject:</strong> ${result.email_subject}</p>
                    <pre class="message-preview">${result.email_body}</pre>
                    <button class="btn btn-success" onclick="copyToClipboard('${escapeHtml(result.email_body)}', 'Email')">
                        <i class="fas fa-copy"></i> Copy Content
                    </button>
                </div>
                
                <div class="notification-info">
                    <i class="fas fa-info-circle"></i>
                    <p>Team members have been notified automatically. Copy the message above to share in your group.</p>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Setup tab switching
    const tabButtons = modal.querySelectorAll('.notification-tab-btn');
    const previews = modal.querySelectorAll('.notification-preview');
    
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            previews.forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(`${btn.dataset.tab}-preview`).classList.add('active');
        });
    });
}

// Copy to clipboard function
function copyToClipboard(text, platform) {
    const decodedText = text.replace(/&#x27;/g, "'").replace(/&quot;/g, '"');
    navigator.clipboard.writeText(decodedText).then(() => {
        showAlert(`${platform} message copied to clipboard!`, 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showAlert('Failed to copy message', 'error');
    });
}

// Escape HTML for safe insertion
function escapeHtml(text) {
    return text.replace(/'/g, "&#x27;").replace(/"/g, "&quot;");
}

// Load feedback statistics
async function loadFeedbackStats() {
    try {
        const response = await fetch(`${API_BASE}/feedback/stats/summary`);
        const stats = await response.json();
        
        const statsContainer = document.getElementById('feedback-stats');
        if (!statsContainer) return;
        
        statsContainer.innerHTML = `
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-comments"></i></div>
                <div class="stat-content">
                    <h4>${stats.total_feedback}</h4>
                    <p>Total Feedback</p>
                </div>
            </div>
            <div class="stat-card pending">
                <div class="stat-icon"><i class="fas fa-clock"></i></div>
                <div class="stat-content">
                    <h4>${stats.pending}</h4>
                    <p>Pending</p>
                </div>
            </div>
            <div class="stat-card progress">
                <div class="stat-icon"><i class="fas fa-tasks"></i></div>
                <div class="stat-content">
                    <h4>${stats.in_progress}</h4>
                    <p>In Progress</p>
                </div>
            </div>
            <div class="stat-card resolved">
                <div class="stat-icon"><i class="fas fa-check-circle"></i></div>
                <div class="stat-content">
                    <h4>${stats.resolved}</h4>
                    <p>Resolved</p>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Setup announcement form for faculty
function setupAnnouncementForm() {
    const form = document.getElementById('announcement-form');
    if (!form) return;
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = {
            title: document.getElementById('announcement-title').value,
            content: document.getElementById('announcement-content').value,
            author: document.getElementById('announcement-author').value,
            priority: document.getElementById('announcement-priority').value,
            target_audience: document.getElementById('target-audience').value
        };
        
        try {
            const response = await fetch(`${API_BASE}/announcements`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });
            
            if (!response.ok) throw new Error('Failed to create announcement');
            
            showAlert('Announcement created successfully!', 'success');
            form.reset();
            loadAnnouncements();
            
        } catch (error) {
            console.error('Error creating announcement:', error);
            showAlert('Error creating announcement', 'error');
        }
    });
}

// Utility: Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    const options = { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return date.toLocaleDateString('en-US', options);
}

// Utility: Show alert
function showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(alert);
    
    setTimeout(() => {
        alert.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 300);
    }, 3000);
}

// Generate weekly schedule (calendar view)
function generateWeeklySchedule() {
    const scheduleData = {
        Monday: [
            { time: '09:00 AM', subject: 'Data Structures', room: '304', type: 'lecture' },
            { time: '11:00 AM', subject: 'Database Systems', room: '202', type: 'lecture' },
            { time: '02:00 PM', subject: 'Lab Session', room: 'Lab 1', type: 'lab' }
        ],
        Tuesday: [
            { time: '10:00 AM', subject: 'Operating Systems', room: '305', type: 'lecture' },
            { time: '01:00 PM', subject: 'Computer Networks', room: '201', type: 'lecture' }
        ],
        Wednesday: [
            { time: '09:00 AM', subject: 'Software Engineering', room: '304', type: 'lecture' },
            { time: '03:00 PM', subject: 'Project Discussion', room: '401', type: 'tutorial' }
        ],
        Thursday: [
            { time: '10:00 AM', subject: 'Web Technologies', room: '203', type: 'lecture' },
            { time: '02:00 PM', subject: 'Lab Session', room: 'Lab 2', type: 'lab' }
        ],
        Friday: [
            { time: '09:00 AM', subject: 'Machine Learning', room: '305', type: 'lecture' },
            { time: '11:00 AM', subject: 'Seminar', room: 'Auditorium', type: 'seminar' }
        ]
    };
    
    const calendarContainer = document.getElementById('weekly-calendar');
    if (!calendarContainer) return;
    
    let html = '<div class="weekly-schedule-grid">';
    
    Object.keys(scheduleData).forEach(day => {
        html += `
            <div class="schedule-day-column">
                <h4 class="day-header">${day}</h4>
                <div class="day-classes">
                    ${scheduleData[day].map(cls => `
                        <div class="class-block ${cls.type}">
                            <span class="class-time"><i class="fas fa-clock"></i> ${cls.time}</span>
                            <span class="class-subject">${cls.subject}</span>
                            <span class="class-room"><i class="fas fa-door-open"></i> ${cls.room}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    calendarContainer.innerHTML = html;
}

// Call on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', generateWeeklySchedule);
} else {
    generateWeeklySchedule();
}
