// Theme toggle (Dark / Light) with persistence
(function() {
  const THEME_KEY = 'mbm_theme';
  const btn = document.getElementById('theme-toggle-btn');

  function applyTheme(theme) {
    if (theme === 'dark') {
      document.body.classList.add('dark-mode');
      btn.setAttribute('aria-pressed', 'true');
      btn.innerHTML = '<i class="fas fa-sun"></i>';
    } else {
      document.body.classList.remove('dark-mode');
      btn.setAttribute('aria-pressed', 'false');
      btn.innerHTML = '<i class="fas fa-moon"></i>';
    }
    try { localStorage.setItem(THEME_KEY, theme); } catch(e){}
  }

  document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem(THEME_KEY) || 'light';
    applyTheme(saved);

    btn?.addEventListener('click', () => {
      const active = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
      applyTheme(active === 'dark' ? 'light' : 'dark');
    });
  });
})();