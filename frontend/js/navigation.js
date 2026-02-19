/* ==================== NAVIGATION JAVASCRIPT ==================== */

// Handle responsive navigation
document.addEventListener('DOMContentLoaded', function() {
    handleResponsiveDesign();
});

function handleResponsiveDesign() {
    const menuToggle = document.querySelector('.menu-toggle');
    const sidebar = document.querySelector('.sidebar');
    const navItems = document.querySelectorAll('.nav-item');

    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768) {
            sidebar.classList.remove('active');
            menuToggle.style.display = 'none';
        } else {
            menuToggle.style.display = 'block';
        }
    });

    // Initial check
    if (window.innerWidth <= 768) {
        menuToggle.style.display = 'block';
    }

    // Close sidebar when nav item is clicked
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('active');
            }
        });
    });
}

// Smooth scrolling for navigation
document.querySelectorAll('.nav-item').forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        const href = this.getAttribute('href');
        if (href && href.startsWith('#')) {
            const section = document.querySelector(href);
            if (section) {
                section.scrollIntoView({ behavior: 'smooth' });
            }
        }
    });
});

// Active section tracking while scrolling
window.addEventListener('scroll', function() {
    const sections = document.querySelectorAll('.content-section.active');
    // Could be enhanced to track which section is visible
});
