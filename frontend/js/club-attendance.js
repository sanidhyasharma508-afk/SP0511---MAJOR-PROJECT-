/* Club Attendance (manual) — date-wise storage in localStorage
   Works for any club page opened via clubs-pages.js
*/
(function(){
  function formatDate(d){ const dt = new Date(d); return dt.toISOString().split('T')[0]; }

  function sampleStudents() {
    return [
      { name: 'Alex Johnson', roll: '21BCS101', section: 'A' },
      { name: 'Riya Mehta', roll: '21BCS102', section: 'A' },
      { name: 'Vikram Singh', roll: '21BCS103', section: 'B' },
      { name: 'Meera Patel', roll: '21BCS104', section: 'B' },
      { name: 'Sahil Verma', roll: '21BCS105', section: 'C' }
    ];
  }

  function renderAttendance(root) {
    const clubName = root.dataset.club || 'Club';
    const today = formatDate(new Date());
    root.innerHTML = `
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:12px;">
        <label style="font-weight:600">Date</label>
        <input type="date" id="club-att-date" value="${today}" />
        <button id="club-load-att" class="btn btn-outline">Load</button>
        <button id="club-save-att" class="btn btn-primary">Save Attendance</button>
      </div>
      <div id="club-att-list"></div>
      <div style="margin-top:10px;display:flex;gap:8px;align-items:center;"> 
        <input id="new-student-name" placeholder="Add student name" />
        <input id="new-student-roll" placeholder="Roll" style="width:120px" />
        <button id="add-student-btn" class="btn btn-small btn-outline">Add</button>
      </div>
    `;

    const listEl = root.querySelector('#club-att-list');
    const dateInput = root.querySelector('#club-att-date');
    const loadBtn = root.querySelector('#club-load-att');
    const saveBtn = root.querySelector('#club-save-att');
    const addBtn = root.querySelector('#add-student-btn');

    const API_BASE = window.API_BASE_URL || 'http://localhost:8000';

    function attendanceKey(date) { return `clubAttendance__${clubName}__${date}`; }

    async function loadFor(date) {
      // Try backend first
      const clubId = await (async () => {
        try {
          const res = await fetch(`${API_BASE}/clubs`);
          if (!res.ok) return null;
          const clubs = await res.json();
          const found = clubs.find(c => c.name.toLowerCase().includes(clubName.toLowerCase()));
          return found?.id || null;
        } catch (e) { return null; }
      })();

      if (clubId) {
        try {
          const resp = await fetch(`${API_BASE}/clubs/${clubId}/attendance?date=${date}`);
          if (resp.ok) {
            const records = await resp.json();
            if (records && records.length) {
              renderList(records.map(r => ({ name: r.student_name, roll: r.roll_number, section: r.section, present: r.status === 'Present' })));
              return;
            }
          }
        } catch (e) {
          console.warn('Backend attendance fetch failed, falling back to localStorage');
        }
      }

      // localStorage fallback
      const key = attendanceKey(date);
      const existing = JSON.parse(localStorage.getItem(key) || 'null');
      if (existing && existing.roster) {
        renderList(existing.roster.map(r => ({ name: r.name || r.student_name, roll: r.roll || r.roll_number, section: r.section || r.section, present: !!r.present })));
        return;
      }
      // render sample roster
      renderList(sampleStudents().map(s => ({ ...s, present: false })));
    }

    function renderList(roster) {
      listEl.innerHTML = roster.map((s, idx) => `
        <div class="attendance-row" data-idx="${idx}">
          <label>
            <input type="checkbox" class="present-checkbox" ${s.present ? 'checked' : ''} />
            <div style="display:flex;flex-direction:column;"><strong>${s.name}</strong><small style="color:var(--muted-color)">${s.roll} • ${s.section || '-'}</small></div>
          </label>
        </div>
      `).join('');

      // wire checkboxes
      listEl.querySelectorAll('.present-checkbox').forEach((cb, i) => {
        cb.addEventListener('change', () => { /* visual only until save */ });
      });
    }

    loadBtn.addEventListener('click', () => loadFor(dateInput.value));
    dateInput.addEventListener('change', () => loadFor(dateInput.value));

    saveBtn.addEventListener('click', async () => {
      const date = dateInput.value || formatDate(new Date());
      const rosterEls = listEl.querySelectorAll('.attendance-row');
      const roster = Array.from(rosterEls).map((row, i) => {
        const checkbox = row.querySelector('.present-checkbox');
        const name = row.querySelector('strong')?.textContent || '';
        const meta = row.querySelector('small')?.textContent || '';
        const roll = meta.split('•')[0]?.trim() || '';
        const section = (meta.split('•')[1] || '').trim();
        return { student_name: name, roll_number: roll, section: section, present: !!checkbox.checked };
      });

      // Try backend save
      const clubId = await (async () => {
        try {
          const res = await fetch(`${API_BASE}/clubs`);
          if (!res.ok) return null;
          const clubs = await res.json();
          const found = clubs.find(c => c.name.toLowerCase().includes(clubName.toLowerCase()));
          return found?.id || null;
        } catch (e) { return null; }
      })();

      if (clubId) {
        try {
          const payload = { attendance_date: new Date(date).toISOString(), roster };
          const resp = await fetch(`${API_BASE}/clubs/${clubId}/attendance`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
          });
          if (resp.ok) { alert('Attendance saved to server for ' + date); return; }
        } catch (e) { console.warn('Backend save failed, falling back to localStorage'); }
      }

      // Fallback to localStorage
      const key = attendanceKey(date);
      localStorage.setItem(key, JSON.stringify({ club: clubName, date, roster }));
      const indexKey = `clubAttendanceIndex__${clubName}`;
      const idx = JSON.parse(localStorage.getItem(indexKey) || '[]');
      if (!idx.includes(date)) { idx.push(date); localStorage.setItem(indexKey, JSON.stringify(idx)); }
      alert('Attendance saved for ' + date);
    });

    addBtn.addEventListener('click', () => {
      const name = root.querySelector('#new-student-name').value.trim();
      const roll = root.querySelector('#new-student-roll').value.trim();
      if (!name) { alert('Enter name'); return; }
      const node = document.createElement('div');
      node.className = 'attendance-row';
      node.innerHTML = `<label><input type=\"checkbox\" class=\"present-checkbox\" checked /><div style=\"display:flex;flex-direction:column;\"><strong>${name}</strong><small style=\"color:var(--muted-color)\">${roll} • -</small></div></label>`;
      listEl.prepend(node);
      root.querySelector('#new-student-name').value = '';
      root.querySelector('#new-student-roll').value = '';
    });

    // initial load
    loadFor(dateInput.value || formatDate(new Date()));
  }

  // initialize when modal content is inserted
  const observer = new MutationObserver((mutations) => {
    mutations.forEach(m => {
      m.addedNodes?.forEach(node => {
        if (node.nodeType === 1) {
          node.querySelectorAll('.club-attendance-root').forEach(root => renderAttendance(root));
        }
      });
    });
  });

  document.addEventListener('DOMContentLoaded', () => {
    // Render existing roots if any
    document.querySelectorAll('.club-attendance-root').forEach(root => renderAttendance(root));
    observer.observe(document.body, { childList: true, subtree: true });
  });
})();