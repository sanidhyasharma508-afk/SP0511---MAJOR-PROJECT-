/* Main UI script — theme + rendering + hooks for backend integration */
(() => {
  const THEME_KEY = 'site-theme';
  const root = document.documentElement;
  const toggle = document.getElementById('theme-toggle');

  /* ---------- Theme handling (localStorage + prefers-color-scheme) ---------- */
  function applyTheme(theme, save = false){
    root.setAttribute('data-theme', theme);
    if(toggle) toggle.setAttribute('aria-pressed', String(theme === 'dark'));
    if(save) localStorage.setItem(THEME_KEY, theme);
  }

  function getInitialTheme(){
    const stored = localStorage.getItem(THEME_KEY);
    if(stored === 'dark' || stored === 'light') return stored;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  /* ---------- Sample data (replace with backend fetch) ---------- */
  const sampleSubjects = [
    { name: 'Computer Networks', code: 'CS-302', percent: 92, attended: '24/26', last: 'Present' },
    { name: 'Engineering Math', code: 'MA-301', percent: 68, attended: '17/25', last: 'Absent' },
    { name: 'Software Lab', code: 'CS-304L', percent: 100, attended: '15/15', last: 'Present' },
    { name: 'Artificial Intelligence', code: 'CS-305', percent: 82, attended: '21/25', last: 'Present' },
    { name: 'Database Systems', code: 'CS-303', percent: 78, attended: '18/23', last: 'Absent' },
    { name: 'Humanities', code: 'HU-101', percent: 45, attended: '9/20', last: 'Absent' }
  ];

  const recentActivity = [
    { text: 'Marked present — Software Lab', time: '2h ago' },
    { text: 'Missed: Engineering Math', time: '1d ago' },
    { text: 'Duty leave approved', time: '3d ago' }
  ];

  /* ---------- Rendering helpers ---------- */
  function statusTag(percent){
    if(percent >= 95) return '<span class="tag safe">Excellent</span>';
    if(percent >= 75) return '<span class="tag safe">Safe</span>';
    if(percent >= 60) return '<span class="tag warning">Warning</span>';
    return '<span class="tag critical">Critical</span>';
  }

  function renderSubjects(list){
    const container = document.getElementById('subjects-grid');
    container.innerHTML = list.map(s => `
      <div class="subject-card card">
        <div style="display:flex;justify-content:space-between;align-items:start;gap:8px">
          <div>
            <div class="title" style="font-weight:700">${s.name}</div>
            <div class="meta">${s.code}</div>
          </div>
          ${statusTag(s.percent)}
        </div>

        <div style="display:flex;align-items:flex-end;gap:8px;margin-top:12px">
          <div class="percent">${s.percent}%</div>
          <div class="meta" style="font-size:12px">attendance</div>
        </div>

        <div class="progress" aria-hidden="true"><span style="width:${s.percent}%"></span></div>

        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted)">
          <div>${s.attended} Attended</div>
          <div>Last: ${s.last}</div>
        </div>
      </div>
    `).join('');
  }

  function renderHeatmap(){
    const days = ['Mon','Tue','Wed','Thu','Fri','Sat'];
    const container = document.getElementById('heatmap');
    container.innerHTML = days.map(d => {
      const cells = new Array(14).fill(0).map((_,i)=>{
        const r = Math.random();
        const cls = r > 0.75 ? 'high' : r > 0.4 ? 'mid' : 'low';
        return `<div class="hm-cell ${cls}" title="${Math.round(r*100)}%"></div>`;
      }).join('');
      return `<div class="hm-row"><div class="weekday">${d}</div><div class="cells">${cells}</div></div>`;
    }).join('');
  }

  function renderRecent(){
    const list = document.getElementById('recent-list');
    list.innerHTML = recentActivity.map(r => `
      <li class="recent-item"><div>${r.text}</div><div class="muted">${r.time}</div></li>
    `).join('');
  }

  /* ---------- Hooks & init ---------- */
  document.addEventListener('DOMContentLoaded', () => {
    // Theme init
    applyTheme(getInitialTheme(), false);

    // Theme toggle
    if(toggle){
      toggle.addEventListener('click', () => {
        const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        applyTheme(next, true);
      });
      toggle.addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle.click(); } });
    }

    // Mobile menu
    const menuBtn = document.getElementById('menu-btn');
    const sidebar = document.getElementById('sidebar');
    menuBtn && menuBtn.addEventListener('click', () => {
      const visible = sidebar.style.display !== 'none';
      sidebar.style.display = visible ? 'none' : 'flex';
    });

    // Render UI
    renderSubjects(sampleSubjects);
    renderHeatmap();
    renderRecent();

    // Segmented control (example of hooking for backend/filtering)
    document.querySelectorAll('.seg-button').forEach(btn => btn.addEventListener('click', e => {
      document.querySelectorAll('.seg-button').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      // TODO: call backend with selected period, e.g. fetchAttendanceData(btn.dataset.view)
    }));
  });

  /* ---------- Backend integration placeholder ---------- */
  async function fetchAttendanceData(period = 'weekly'){
    // Example: replace sampleSubjects with real API call
    // const res = await fetch(`/api/attendance?period=${period}`);
    // const data = await res.json();
    // renderSubjects(data.subjects);
    console.log('fetchAttendanceData()', period);
  }

  // expose for debugging / future hooks
  window.App = { applyTheme, fetchAttendanceData };
})();