// Schedule Management JavaScript

const API_BASE = (typeof window !== 'undefined' && window.location.port === '3000')
    ? '/api/schedule-management'
    : (typeof window !== 'undefined' && window.location.origin.includes(':8000') ? '/schedule-management' : 'http://localhost:8000/schedule-management');

function getAuthHeaders(extraHeaders = {}) {
    const token = window.api ? window.api.getToken() : (localStorage.getItem('auth_token') || localStorage.getItem('access_token'));
    const headers = { ...extraHeaders };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

// Initialize Schedule Management
document.addEventListener('DOMContentLoaded', function() {
    loadAnnouncements();
    loadFeedbackStats();
    setupFormSubmission();
    setupAnnouncementForm();
    syncUserInfo();
    loadInstitutionalSchedules();
});

window.addEventListener('auth:login', function() {
    syncUserInfo();
    loadInstitutionalSchedules();
});
window.addEventListener('auth:ready', function() {
    syncUserInfo();
    loadInstitutionalSchedules();
});

function syncUserInfo() {
    const user = window.currentUser;
    const student = window.currentStudent;
    if (!user) return;

    const nameInput = document.getElementById('student-name');
    const rollInput = document.getElementById('roll-number');
    if (nameInput && (!nameInput.value || nameInput.value === 'Alex Johnson')) {
        nameInput.value = student?.name || user.full_name || user.username;
    }
    if (rollInput && (!rollInput.value || rollInput.value === '21BCS101')) {
        rollInput.value = student?.roll_no || user.username;
    }

    // Announcement author prefill
    const authorInput = document.getElementById('announcement-author');
    if (authorInput && !authorInput.value) {
        authorInput.value = user.full_name || user.username;
    }

    // Role check for announcement container
    const isStudent = (user.role || '').toLowerCase() === 'student';
    const formContainer = document.getElementById('announcement-form')?.closest('.schedule-card');
    if (formContainer && isStudent) {
        formContainer.style.display = 'none';
    } else if (formContainer) {
        formContainer.style.display = 'block';
    }
}

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
        
        container.textContent = '';
        announcements.forEach(announcement => {
            const card = document.createElement('div');
            const safePriority = String(announcement.priority || 'medium').toLowerCase().replace(/[^a-z0-9_-]/g, '');
            card.className = `announcement-card priority-${safePriority}`;

            const header = document.createElement('div');
            header.className = 'announcement-header';
            const badge = document.createElement('span');
            badge.className = `priority-badge ${safePriority}`;
            badge.textContent = String(announcement.priority || 'MEDIUM').toUpperCase();
            const dateSpan = document.createElement('span');
            dateSpan.className = 'announcement-date';
            dateSpan.textContent = formatDate(announcement.created_at);
            header.appendChild(badge);
            header.appendChild(dateSpan);

            const titleEl = document.createElement('h4');
            titleEl.className = 'announcement-title';
            titleEl.textContent = announcement.title || '';

            const contentEl = document.createElement('p');
            contentEl.className = 'announcement-content';
            contentEl.textContent = announcement.content || '';

            const footer = document.createElement('div');
            footer.className = 'announcement-footer';
            const authorSpan = document.createElement('span');
            authorSpan.className = 'announcement-author';
            const authorIcon = document.createElement('i');
            authorIcon.className = 'fas fa-user-tie';
            authorSpan.appendChild(authorIcon);
            authorSpan.appendChild(document.createTextNode(` ${announcement.author || 'Faculty'}`));

            const audienceSpan = document.createElement('span');
            audienceSpan.className = 'announcement-audience';
            const audienceIcon = document.createElement('i');
            audienceIcon.className = 'fas fa-users';
            audienceSpan.appendChild(audienceIcon);
            audienceSpan.appendChild(document.createTextNode(` ${announcement.target_audience || 'All'}`));

            footer.appendChild(authorSpan);
            footer.appendChild(audienceSpan);

            card.appendChild(header);
            card.appendChild(titleEl);
            card.appendChild(contentEl);
            card.appendChild(footer);
            container.appendChild(card);
        });
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
                headers: getAuthHeaders({
                    'Content-Type': 'application/json',
                }),
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

    const content = document.createElement('div');
    content.className = 'notification-modal-content';

    const header = document.createElement('div');
    header.className = 'notification-modal-header';
    const headerTitle = document.createElement('h3');
    headerTitle.innerHTML = '<i class="fas fa-check-circle"></i> Feedback Submitted Successfully!';
    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-modal';
    closeBtn.setAttribute('aria-label', 'Close modal');
    closeBtn.innerHTML = '<i class="fas fa-times"></i>';
    closeBtn.addEventListener('click', () => modal.remove());
    header.appendChild(headerTitle);
    header.appendChild(closeBtn);

    const body = document.createElement('div');
    body.className = 'notification-modal-body';

    const successMsg = document.createElement('p');
    successMsg.className = 'success-message';
    successMsg.textContent = result.message || 'Feedback submitted successfully.';
    body.appendChild(successMsg);

    const tabs = document.createElement('div');
    tabs.className = 'notification-tabs';
    tabs.innerHTML = `
        <button class="notification-tab-btn active" data-tab="whatsapp">
            <i class="fab fa-whatsapp"></i> WhatsApp
        </button>
        <button class="notification-tab-btn" data-tab="telegram">
            <i class="fab fa-telegram"></i> Telegram
        </button>
        <button class="notification-tab-btn" data-tab="email">
            <i class="fas fa-envelope"></i> Email
        </button>
    `;
    body.appendChild(tabs);

    // WhatsApp preview
    const waPreview = document.createElement('div');
    waPreview.className = 'notification-preview active';
    waPreview.id = 'whatsapp-preview';
    waPreview.innerHTML = '<h4>WhatsApp Message</h4>';
    const waPre = document.createElement('pre');
    waPre.className = 'message-preview';
    waPre.textContent = result.whatsapp_message || '';
    const waBtn = document.createElement('button');
    waBtn.className = 'btn btn-success';
    waBtn.innerHTML = '<i class="fas fa-copy"></i> Copy Message';
    waBtn.addEventListener('click', () => copyToClipboard(result.whatsapp_message || '', 'WhatsApp'));
    waPreview.appendChild(waPre);
    waPreview.appendChild(waBtn);
    body.appendChild(waPreview);

    // Telegram preview
    const tgPreview = document.createElement('div');
    tgPreview.className = 'notification-preview';
    tgPreview.id = 'telegram-preview';
    tgPreview.innerHTML = '<h4>Telegram Message</h4>';
    const tgPre = document.createElement('pre');
    tgPre.className = 'message-preview';
    tgPre.textContent = result.telegram_message || '';
    const tgBtn = document.createElement('button');
    tgBtn.className = 'btn btn-success';
    tgBtn.innerHTML = '<i class="fas fa-copy"></i> Copy Message';
    tgBtn.addEventListener('click', () => copyToClipboard(result.telegram_message || '', 'Telegram'));
    tgPreview.appendChild(tgPre);
    tgPreview.appendChild(tgBtn);
    body.appendChild(tgPreview);

    // Email preview
    const emPreview = document.createElement('div');
    emPreview.className = 'notification-preview';
    emPreview.id = 'email-preview';
    emPreview.innerHTML = '<h4>Email</h4>';
    const emSubj = document.createElement('p');
    const emSubjStrong = document.createElement('strong');
    emSubjStrong.textContent = 'Subject: ';
    emSubj.appendChild(emSubjStrong);
    emSubj.appendChild(document.createTextNode(result.email_subject || ''));
    const emPre = document.createElement('pre');
    emPre.className = 'message-preview';
    emPre.textContent = result.email_body || '';
    const emBtn = document.createElement('button');
    emBtn.className = 'btn btn-success';
    emBtn.innerHTML = '<i class="fas fa-copy"></i> Copy Content';
    emBtn.addEventListener('click', () => copyToClipboard(result.email_body || '', 'Email'));
    emPreview.appendChild(emSubj);
    emPreview.appendChild(emPre);
    emPreview.appendChild(emBtn);
    body.appendChild(emPreview);

    const infoDiv = document.createElement('div');
    infoDiv.className = 'notification-info';
    infoDiv.innerHTML = '<i class="fas fa-info-circle"></i><p>Team members have been notified automatically. Copy the message above to share in your group.</p>';
    body.appendChild(infoDiv);

    content.appendChild(header);
    content.appendChild(body);
    modal.appendChild(content);
    document.body.appendChild(modal);

    // Tab switching
    const tabButtons = modal.querySelectorAll('.notification-tab-btn');
    const previews = modal.querySelectorAll('.notification-preview');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            previews.forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            modal.querySelector(`#${btn.dataset.tab}-preview`)?.classList.add('active');
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
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
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
                headers: getAuthHeaders({
                    'Content-Type': 'application/json',
                }),
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
    const safeType = ['success', 'error', 'warning', 'info'].includes(type) ? type : 'info';
    alert.className = `alert alert-${safeType}`;
    const icon = document.createElement('i');
    icon.className = `fas fa-${safeType === 'success' ? 'check-circle' : safeType === 'error' ? 'exclamation-circle' : 'info-circle'}`;
    const span = document.createElement('span');
    span.textContent = message;
    alert.appendChild(icon);
    alert.appendChild(span);
    
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


// Load institutional schedules from backend API (Task 7)
async function loadInstitutionalSchedules() {
    const apiBase = (typeof window !== 'undefined' && window.location.port === '3000')
        ? '/api'
        : (typeof window !== 'undefined' && window.location.origin.includes(':8000') ? '' : 'http://localhost:8000');
    
    const token = window.api ? window.api.getToken() : (localStorage.getItem('auth_token') || localStorage.getItem('access_token'));
    const headers = token ? { 'Authorization': 'Bearer ' + token } : {};

    try {
        const endpoint = token ? `${apiBase}/schedules/my-schedule` : `${apiBase}/schedules/active`;
        const res = await fetch(endpoint, { headers });
        if (!res.ok) return;
        const schedules = await res.json();

        // Update Daily Schedule Timeline
        const timeline = document.querySelector('.schedule-timeline');
        const dailyH4 = document.querySelector('.daily-schedule h4');
        if (dailyH4) {
            const now = new Date();
            dailyH4.textContent = now.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', weekday: 'long' });
        }

        if (timeline) {
            if (!schedules || schedules.length === 0) {
                timeline.innerHTML = `
                    <div class="empty-schedule-state" style="padding: 24px; text-align: center; color: #888;">
                        <i class="fas fa-calendar-check" style="font-size: 32px; color: #5B7EFF; margin-bottom: 12px; display: block;"></i>
                        <p style="font-weight: 500;">No institutional classes or events scheduled today.</p>
                        <p style="font-size: 12px; margin-top: 4px;">Check your study tasks or consult your department timetable.</p>
                    </div>
                `;
            } else {
                timeline.innerHTML = schedules.map(s => {
                    let iconClass = 'fas fa-chalkboard-user';
                    if (s.event_type === 'Exam') iconClass = 'fas fa-file-pen';
                    else if (s.event_type === 'Event') iconClass = 'fas fa-calendar-star';
                    else if (s.event_type === 'Holiday') iconClass = 'fas fa-umbrella-beach';

                    const startTime = s.start_date ? new Date(s.start_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'TBD';
                    const endTime = s.end_date ? new Date(s.end_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
                    const timeRange = endTime ? `${startTime} - ${endTime}` : startTime;

                    return `
                        <div class="timeline-item">
                            <div class="timeline-marker">
                                <i class="${iconClass}"></i>
                            </div>
                            <div class="timeline-content">
                                <p class="time">${timeRange}</p>
                                <p class="title">${escapeScheduleHtml(s.title)} <span class="badge" style="font-size: 11px; margin-left: 6px; padding: 2px 6px; background: rgba(91, 126, 255, 0.15); color: #5B7EFF; border-radius: 4px;">${escapeScheduleHtml(s.event_type)}</span></p>
                                <p class="description">${escapeScheduleHtml(s.location || 'Campus')} • ${escapeScheduleHtml(s.audience || 'All')}</p>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        }
    } catch (err) {
        console.debug('Could not load institutional schedules:', err);
    }
}

function escapeScheduleHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
