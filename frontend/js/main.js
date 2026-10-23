/* ==================== MAIN JAVASCRIPT ==================== */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize the application
    initializeNavigation();
    initializeEventListeners();
    initializeCategoryFilter();
    initializeScheduleTabs();
});

// Navigation
function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const contentSections = document.querySelectorAll('.content-section');

    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Get the section ID from data attribute
            const sectionId = this.getAttribute('data-section');
            const targetSection = document.getElementById(sectionId);
            
            if (!targetSection) return;

            // Update active nav item
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');

            // Update active content section
            contentSections.forEach(section => section.classList.remove('active'));
            targetSection.classList.add('active');

            // Update page title
            const pageTitle = document.getElementById('page-title');
            const titleMap = {
                'dashboard': 'Dashboard',
                'clubs': 'Clubs & Events',
                'attendance': 'Attendance Overview',
                'qr-attendance': 'QR-Based Smart Attendance',
                'schedule': 'Academic Schedule',
                'schedule-feedback': 'Schedule & Announcement Management',
                'academics': 'Academics'
            };
            pageTitle.textContent = titleMap[sectionId] || 'Dashboard';

            // Close sidebar on mobile
            const sidebar = document.querySelector('.sidebar');
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('active');
            }
        });
    });
}

// Event Listeners
function initializeEventListeners() {
    // Menu toggle
    const menuToggle = document.querySelector('.menu-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
        });
    }

    // Close sidebar when clicking outside
    document.addEventListener('click', function(e) {
        const sidebar = document.querySelector('.sidebar');
        const menuToggle = document.querySelector('.menu-toggle');
        
        if (window.innerWidth <= 768) {
            if (!sidebar.contains(e.target) && !menuToggle.contains(e.target)) {
                sidebar.classList.remove('active');
            }
        }
    });

    // Club search
    const clubSearch = document.getElementById('club-search');
    if (clubSearch) {
        clubSearch.addEventListener('input', function() {
            filterClubs(this.value.toLowerCase());
        });
    }

    // Initialize real event registration
    initializeEventRegistration();
}

async function initializeEventRegistration() {
    const API_BASE = window.API_BASE_URL || '/api';
    const token = localStorage.getItem('auth_token');
    
    // Fetch upcoming events from backend
    let dbEvents = [];
    try {
        const res = await fetch(`${API_BASE}/events`, {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        if (res.ok) {
            dbEvents = await res.json();
        }
    } catch (e) {}

    // Check my registrations
    let myRegs = [];
    if (token) {
        try {
            const myRes = await fetch(`${API_BASE}/events/my-registrations`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (myRes.ok) {
                myRegs = await myRes.json();
            }
        } catch (e) {}
    }
    const registeredEventIds = new Set(
        myRegs.filter(r => r.status !== 'cancelled').map(r => r.event_id)
    );

    const eventCards = document.querySelectorAll('.events-section .event-card');
    eventCards.forEach(card => {
        const titleEl = card.querySelector('h4');
        if (!titleEl) return;
        const title = titleEl.textContent.trim();
        const matched = dbEvents.find(e => 
            e.name.toLowerCase() === title.toLowerCase() ||
            e.name.toLowerCase().includes(title.toLowerCase()) ||
            title.toLowerCase().includes(e.name.toLowerCase())
        );

        const btn = card.querySelector('button');
        if (!btn) return;

        if (matched && registeredEventIds.has(matched.id)) {
            btn.textContent = 'Registered (Cancel)';
            btn.className = 'btn btn-outline';
            btn.dataset.registered = 'true';
            btn.dataset.eventId = matched.id;
        } else if (matched) {
            btn.dataset.eventId = matched.id;
            btn.dataset.registered = 'false';
        }

        btn.addEventListener('click', async function(e) {
            e.preventDefault();
            const curToken = localStorage.getItem('auth_token');
            if (!curToken) {
                showNotification('Please log in to register for events');
                return;
            }

            const targetEvent = matched || (dbEvents.length > 0 ? dbEvents[0] : null);
            if (!targetEvent) {
                showNotification('Event not found in backend registry');
                return;
            }

            if (btn.dataset.registered === 'true') {
                // Cancel registration
                const reg = myRegs.find(r => r.event_id === targetEvent.id && r.status !== 'cancelled');
                if (reg) {
                    try {
                        const cancelRes = await fetch(`${API_BASE}/events/registrations/${reg.id}/cancel`, {
                            method: 'POST',
                            headers: { 'Authorization': `Bearer ${curToken}` }
                        });
                        if (cancelRes.ok) {
                            btn.dataset.registered = 'false';
                            btn.textContent = 'Register Now →';
                            btn.className = 'btn btn-primary';
                            showNotification(`Cancelled registration for ${targetEvent.name}`);
                            return;
                        }
                    } catch (err) {}
                }
            }

            // Register
            try {
                const user = window.currentUser || {};
                const student = window.currentStudent || {};
                const studentId = student.id || user.linked_student_id || user.user_id || '1';
                const studentName = student.name || user.full_name || user.username || 'Student';
                const studentEmail = user.email || student.email || `${user.username || 'student'}@mbm.ac.in`;

                const regPayload = {
                    event_id: targetEvent.id,
                    student_id: String(studentId),
                    student_name: studentName,
                    student_email: studentEmail,
                    student_phone: "9876543210",
                    branch: student.department || "Computer Science",
                    year: "3rd Year",
                    roll_number: student.roll_no || user.sub || "21BCS101"
                };

                const res = await fetch(`${API_BASE}/events/registrations`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${curToken}`
                    },
                    body: JSON.stringify(regPayload)
                });

                if (res.ok) {
                    const data = await res.json();
                    myRegs.push(data);
                    btn.dataset.registered = 'true';
                    btn.textContent = 'Registered (Cancel)';
                    btn.className = 'btn btn-outline';
                    showNotification(`Successfully registered for ${targetEvent.name}!`);
                } else {
                    const err = await res.json().catch(() => ({}));
                    showNotification(err.detail || 'Registration failed');
                }
            } catch (err) {
                showNotification(`Network error: ${err.message}`);
            }
        });
    });
}

// Category Filter
function initializeCategoryFilter() {
    const categoryBtns = document.querySelectorAll('.category-btn');
    
    categoryBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Update active button
            categoryBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            // Filter clubs
            const category = this.getAttribute('data-category');
            filterClubsByCategory(category);
        });
    });
}

function filterClubs(searchTerm) {
    const clubCards = document.querySelectorAll('.club-card');
    
    clubCards.forEach(card => {
        const title = card.querySelector('h4').textContent.toLowerCase();
        const description = card.querySelector('p').textContent.toLowerCase();
        
        if (title.includes(searchTerm) || description.includes(searchTerm)) {
            card.style.display = '';
            card.parentElement.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

function filterClubsByCategory(category) {
    const clubCards = document.querySelectorAll('.club-card');
    
    if (category === 'all') {
        clubCards.forEach(card => card.style.display = '');
        return;
    }

    const categoryMap = {
        'tech': ['Coding Club', 'Robotics Society'],
        'arts': ['Arts & Culture', 'Music Club'],
        'sports': ['Sports Federation'],
        'academic': ['Coding Club', 'Robotics Society'],
        'social': ['Social Service']
    };

    clubCards.forEach(card => {
        const title = card.querySelector('h4').textContent;
        if (categoryMap[category]?.some(cat => title.includes(cat))) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

// Schedule Tabs
function initializeScheduleTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            
            // Update active button
            tabBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            // Update active content
            tabContents.forEach(content => content.classList.remove('active'));
            const targetContent = document.getElementById(tabId);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    // Set first tab as active by default
    if (tabBtns.length > 0) {
        tabBtns[0].classList.add('active');
        tabContents[0]?.classList.add('active');
    }
}

// Notification
function showNotification(message) {
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #43E97B 0%, #38F9D7 100%);
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
        font-weight: 600;
        z-index: 2000;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add animation styles dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
