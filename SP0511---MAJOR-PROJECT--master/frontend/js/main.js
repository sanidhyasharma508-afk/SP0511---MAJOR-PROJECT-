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
                'attendance': 'Attendance',
                'schedule': 'Schedule',
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

    // Button events
    const joinButtons = document.querySelectorAll('.btn-primary');
    joinButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (btn.textContent.includes('Join')) {
                e.preventDefault();
                showNotification('Successfully joined the club!');
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
