/* Schedule Tasks - "My Today's Schedule" checklist, timers, notifications, and persistent backend API */
(function() {
  let tasks = [];
  let timerInterval = null;

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function formatRemaining(sec) {
    if (!sec || sec <= 0) return '00:00:00';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  function showToast(msg, type = 'info') {
    const n = document.createElement('div');
    n.className = `task-toast task-toast-${type}`;
    n.textContent = msg;
    const bg = type === 'error' ? 'rgba(214, 48, 49, 0.95)' : 'rgba(20, 30, 45, 0.92)';
    n.style.cssText = `position:fixed;bottom:24px;right:24px;background:${bg};color:#fff;padding:12px 18px;border-radius:8px;font-size:14px;box-shadow:0 4px 14px rgba(0,0,0,0.25);z-index:9999;transition:opacity 0.3s ease;`;
    document.body.appendChild(n);
    setTimeout(() => {
      n.style.opacity = '0';
      setTimeout(() => n.remove(), 300);
    }, 2800);
  }

  function notifyTaskComplete(task) {
    const n = document.createElement('div');
    n.textContent = `⏰ Time's up for task: ${task.title}`;
    n.style.cssText = 'position:fixed;top:24px;right:24px;background:#0b1a12;color:#bfffe4;padding:12px 18px;border-radius:8px;font-weight:600;box-shadow:0 6px 18px rgba(0,0,0,0.3);z-index:9999;';
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 5000);
  }

  function createTaskElement(task) {
    const div = document.createElement('div');
    div.className = `task-item ${task.is_completed ? 'is-completed' : ''}`;
    div.dataset.id = task.id;
    div.innerHTML = `
      <input type="checkbox" class="task-complete" ${task.is_completed ? 'checked' : ''} aria-label="Mark task complete" />
      <div class="task-meta" style="flex:1; margin: 0 12px;">
        <p class="task-title" style="${task.is_completed ? 'text-decoration: line-through; opacity: 0.6;' : 'font-weight: 600;'}">${escapeHtml(task.title)}</p>
        <p class="task-desc" style="font-size: 12px; color: #888; margin-top: 2px;">${escapeHtml(task.description || '')}</p>
      </div>
      <div class="task-controls" style="display:flex; align-items:center; gap:8px;">
        <div class="task-timer" data-remaining="${task.remaining_seconds || 0}" style="font-family:monospace; font-size:12px; color: #5B7EFF;">${formatRemaining(task.remaining_seconds)}</div>
        <div class="task-badge">${task.remaining_seconds > 0 && !task.is_completed ? '⏱️' : ''}</div>
        <button type="button" class="btn-task-delete" title="Delete task" aria-label="Delete task" style="background:none; border:none; color:#999; font-size:18px; cursor:pointer; line-height:1; padding:2px 6px; border-radius:4px;">&times;</button>
      </div>
    `;

    // Toggle completion listener
    const checkbox = div.querySelector('.task-complete');
    checkbox.addEventListener('change', async () => {
      const isChecked = checkbox.checked;
      task.is_completed = isChecked;
      const titleEl = div.querySelector('.task-title');
      if (titleEl) {
        titleEl.style.textDecoration = isChecked ? 'line-through' : 'none';
        titleEl.style.opacity = isChecked ? '0.6' : '1.0';
      }
      if (isChecked) {
        div.classList.add('is-completed');
      } else {
        div.classList.remove('is-completed');
      }

      if (window.api && window.api.hasValidToken()) {
        try {
          await window.api.updateStudyTask(task.id, { is_completed: isChecked });
        } catch (err) {
          console.error('Failed to sync task status:', err);
          showToast('Failed to update task status', 'error');
          // Revert checkbox on error
          task.is_completed = !isChecked;
          checkbox.checked = !isChecked;
          if (titleEl) {
            titleEl.style.textDecoration = !isChecked ? 'line-through' : 'none';
            titleEl.style.opacity = !isChecked ? '0.6' : '1.0';
          }
        }
      }
    });

    // Delete task listener
    const deleteBtn = div.querySelector('.btn-task-delete');
    deleteBtn.addEventListener('click', async () => {
      if (window.api && window.api.hasValidToken()) {
        try {
          await window.api.deleteStudyTask(task.id);
          tasks = tasks.filter(t => t.id !== task.id);
          div.remove();
          showToast('Task removed');
        } catch (err) {
          console.error('Failed to delete task:', err);
          showToast('Failed to delete task', 'error');
        }
      } else {
        tasks = tasks.filter(t => t.id !== task.id);
        div.remove();
      }
    });

    return div;
  }

  function renderTasks() {
    const list = document.getElementById('tasks-list');
    if (!list) return;
    list.innerHTML = '';

    if (tasks.length === 0) {
      list.innerHTML = '<p class="no-tasks-msg" style="color:#888; font-size:13px; text-align:center; padding:12px 0;">No study tasks scheduled yet. Add a task above to track your study sessions.</p>';
      return;
    }

    tasks.forEach(task => {
      list.appendChild(createTaskElement(task));
    });
    updateTimersInDOM();
  }

  function updateTimersInDOM() {
    document.querySelectorAll('.task-item').forEach(el => {
      const taskId = parseInt(el.dataset.id, 10);
      const task = tasks.find(t => t.id === taskId);
      if (!task) return;
      const timerEl = el.querySelector('.task-timer');
      if (timerEl) {
        timerEl.textContent = formatRemaining(task.remaining_seconds);
      }
      const badgeEl = el.querySelector('.task-badge');
      if (badgeEl) {
        badgeEl.textContent = task.remaining_seconds > 0 && !task.is_completed ? '⏱️' : (task.notified ? '🔔' : '');
      }
    });
  }

  function startTimers() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      let updated = false;
      tasks.forEach(t => {
        if (!t.is_completed && t.remaining_seconds > 0) {
          t.remaining_seconds -= 1;
          updated = true;
          if (t.remaining_seconds === 0 && !t.notified) {
            t.notified = true;
            notifyTaskComplete(t);
          }
        }
      });
      if (updated) {
        updateTimersInDOM();
      }
    }, 1000);
  }

  async function loadTasksFromBackend() {
    if (!window.api || !window.api.hasValidToken()) {
      tasks = [];
      renderTasks();
      return;
    }

    const list = document.getElementById('tasks-list');
    if (list && tasks.length === 0) {
      list.innerHTML = '<p style="color:#888; font-size:13px; text-align:center; padding:12px 0;">Loading tasks...</p>';
    }

    try {
      const data = await window.api.getStudyTasks();
      tasks = Array.isArray(data) ? data : [];
      renderTasks();
      startTimers();
    } catch (err) {
      console.error('Failed to load study tasks from API:', err);
      if (list) {
        list.innerHTML = '<p style="color:#e74c3c; font-size:13px; text-align:center; padding:12px 0;">Failed to load study tasks. Please try again.</p>';
      }
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('add-task-form');
    if (!form) return;

    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const titleInput = document.getElementById('task-title');
      const durationInput = document.getElementById('task-duration');
      const descInput = document.getElementById('task-desc');

      const title = titleInput ? titleInput.value.trim() : '';
      if (!title) return;

      const duration = parseInt(durationInput ? durationInput.value || '0' : '0', 10);
      const desc = descInput ? descInput.value.trim() : '';
      const remaining = duration > 0 ? duration * 60 : 0;

      const taskPayload = {
        title: title,
        description: desc,
        duration_minutes: duration,
        remaining_seconds: remaining,
        is_completed: false,
      };

      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      try {
        if (!window.api || !window.api.hasValidToken()) {
          throw new Error('Please sign in to save study tasks');
        }

        const createdTask = await window.api.createStudyTask(taskPayload);
        tasks.unshift(createdTask);
        renderTasks();
        form.reset();
        showToast('Study task added successfully');
      } catch (err) {
        console.error('Failed to create study task:', err);
        showToast(err.message || 'Failed to create task', 'error');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });

    // Load tasks on startup and when user logs in / out
    loadTasksFromBackend();
    window.addEventListener('auth:login', loadTasksFromBackend);
    window.addEventListener('auth:ready', loadTasksFromBackend);
    window.addEventListener('auth:logout', () => {
      tasks = [];
      renderTasks();
    });
  });
})();