/* Schedule Tasks - "My Today's Schedule" checklist, timers, notifications, persistence */
(function(){
  const KEY_PREFIX = 'scheduleTasks__';
  function todayKey() { return KEY_PREFIX + new Date().toISOString().split('T')[0]; }

  function createTaskElement(task, idx) {
    const div = document.createElement('div');
    div.className = 'task-item';
    div.dataset.idx = idx;
    div.innerHTML = `
      <input type="checkbox" class="task-complete" ${task.complete ? 'checked' : ''} />
      <div class="task-meta">
        <p class="task-title">${task.title}</p>
        <p class="task-desc">${task.desc || ''}</p>
      </div>
      <div class="task-controls">
        <div class="task-timer" data-remaining="${task.remaining || 0}">${formatRemaining(task.remaining)}</div>
        <div class="task-badge">${task.notify ? '!' : ''}</div>
      </div>
    `;

    const checkbox = div.querySelector('.task-complete');
    checkbox.addEventListener('change', (e) => {
      task.complete = checkbox.checked;
      saveTasks(tasks);
      renderTasks();
    });

    return div;
  }

  function formatRemaining(sec) {
    if (!sec || sec <= 0) return '00:00:00';
    const h = Math.floor(sec / 3600); const m = Math.floor((sec % 3600) / 60); const s = sec % 60;
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  }

  function saveTasks(ts) { try { localStorage.setItem(todayKey(), JSON.stringify(ts)); } catch(e){} }
  function loadTasks() { return JSON.parse(localStorage.getItem(todayKey() || '[]') || '[]'); }

  let tasks = loadTasks();
  let timers = [];

  function startTimers() {
    clearIntervalAll();
    timers = setInterval(() => {
      let updated = false;
      tasks.forEach(t => {
        if (!t.complete && t.remaining > 0) { t.remaining -= 1; updated = true; }
        if (!t.notified && t.remaining === 0 && !t.complete) { t.notified = true; notifyTask(t); }
      });
      if (updated) { saveTasks(tasks); updateTimersInDOM(); }
    }, 1000);
  }

  function clearIntervalAll() { if (timers) { clearInterval(timers); timers = null; } }

  function updateTimersInDOM() {
    document.querySelectorAll('.task-item').forEach(el => {
      const idx = Number(el.dataset.idx);
      const timerEl = el.querySelector('.task-timer');
      timerEl.textContent = formatRemaining(tasks[idx].remaining);
      el.querySelector('.task-badge').textContent = tasks[idx].notified ? '🔔' : '';
    });
  }

  function notifyTask(task) {
    const n = document.createElement('div');
    n.textContent = `Time up: ${task.title}`;
    n.style.cssText = 'position:fixed;top:20px;left:20px;background:#0b1a12;color:#bfffe4;padding:8px 12px;border-radius:8px;z-index:2200;';
    document.body.appendChild(n); setTimeout(() => n.remove(), 4000);
  }

  function renderTasks() {
    const list = document.getElementById('tasks-list');
    if (!list) return;
    list.innerHTML = '';
    tasks.forEach((t, i) => list.appendChild(createTaskElement(t, i)));
    updateTimersInDOM();
  }

  document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('add-task-form');
    if (!form) return;

    form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const title = document.getElementById('task-title').value.trim();
      const duration = parseInt(document.getElementById('task-duration').value || '0', 10);
      const desc = document.getElementById('task-desc').value.trim();
      const remaining = duration > 0 ? duration * 60 : 0; // store seconds
      const task = { title, desc, remaining, complete:false, notified:false, notify: duration>0 };
      tasks.unshift(task);
      saveTasks(tasks);
      renderTasks();
      form.reset();
      startTimers();
    });

    // load existing
    tasks = loadTasks();
    renderTasks();
    startTimers();
  });
})();