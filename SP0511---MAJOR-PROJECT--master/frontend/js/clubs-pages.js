/* Club pages modal & tab handling
   - Opens club-specific page when any .club-card is clicked
   - Provides tabs: Create Event, Organise Today's Meet, Attendance (attendance managed by club-attendance.js)
*/
(function() {
  const CLUB_DATA = {
    'Music Club': {
      displayName: 'Sargam',
      hero: 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=1200&h=800&fit=crop',
      gallery: [
        'https://images.unsplash.com/photo-1508973376-1e39b1d9b3e7?w=800&h=500&fit=crop',
        'https://images.unsplash.com/photo-1511379938547-c1f69419868d?w=800&h=500&fit=crop'
      ],
      description: 'Sargam — MBM University music society. Live gigs, workshops, and studio sessions.'
    },
    'Music Club – Sargam': {
      displayName: 'Sargam',
      hero: 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=1200&h=800&fit=crop',
      gallery: [],
      description: 'Sargam — MBM University music society. Live gigs and workshops.'
    },
    'Dance Club': {
      displayName: 'Zenith',
      hero: 'https://images.unsplash.com/photo-1512436991641-6745cdb1723f?w=1200&h=800&fit=crop',
      description: 'Zenith — energetic dance team performing across events.'
    },
    'Photography Club': {
      displayName: 'Pixellens',
      hero: 'https://images.unsplash.com/photo-1504198453319-5ce911bafcde?w=1200&h=800&fit=crop',
      description: 'Pixellens — capture moments and learn photography skills.'
    },
    'Arts & Culture': {
      displayName: 'Kalakriti',
      hero: 'https://images.unsplash.com/photo-1513364776144-60967b0f800f?w=1200&h=800&fit=crop',
      description: 'Kalakriti — painting, sketching, and cultural showcases.'
    }
  };

  function $(sel, ctx=document){ return ctx.querySelector(sel); }

  function openClubModal(title) {
    const info = CLUB_DATA[title] || CLUB_DATA[title.split(' - ')[0]] || { displayName: title, hero: '', description: '' };
    const modal = document.getElementById('club-page-modal');
    const container = document.getElementById('club-page-content');

    container.innerHTML = `
      <div class="club-hero">
        <img src="${info.hero || 'https://images.unsplash.com/photo-1504198453319-5ce911bafcde?w=800&h=600&fit=crop'}" alt="${info.displayName}">
        <div>
          <h2>${info.displayName}</h2>
          <p style="margin:6px 0 0; color:var(--muted-color)">${info.description || ''}</p>
          <div style="margin-top:8px"><button id="club-back-btn" class="btn btn-outline">← Back to Clubs</button></div>
        </div>
      </div>
      <div class="club-tabs">
        <button data-tab="create-event" class="active">Create Event</button>
        <button data-tab="todays-meet">Organise Today's Meet</button>
        <button data-tab="club-attendance">Attendance</button>
      </div>
      <div class="club-body">
        <div class="club-column" id="club-panel-left">
          <div id="tab-create-event" class="tab-panel">
            <h4>Create Event</h4>
            <form id="club-create-event-form">
              <input id="event-title" placeholder="Event title" required />
              <input id="event-date" type="date" required />
              <input id="event-time" type="time" />
              <textarea id="event-desc" placeholder="Short description"></textarea>
              <button class="btn btn-primary" type="submit">Create Event</button>
            </form>
            <div id="club-events-list" style="margin-top:12px"></div>
          </div>

          <div id="tab-todays-meet" class="tab-panel" style="display:none">
            <h4>Organise Today's Meet</h4>
            <form id="club-today-meet-form">
              <input id="meet-location" placeholder="Location (e.g., Room 101)" />
              <input id="meet-time" type="time" />
              <textarea id="meet-notes" placeholder="Notes / agenda"></textarea>
              <button class="btn btn-primary" type="submit">Schedule Meet</button>
            </form>
            <div id="club-meet-list" style="margin-top:12px"></div>
          </div>
        </div>
        <div class="club-column">
          <div id="tab-attendance" class="tab-panel club-attendance" style="display:block">
            <h4>Attendance</h4>
            <div id="club-attendance-ui"></div>
          </div>
        </div>
      </div>
    `;

    // wire tab buttons
    container.querySelectorAll('.club-tabs button').forEach(btn => {
      btn.addEventListener('click', () => {
        container.querySelectorAll('.club-tabs button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        container.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
        const el = container.querySelector(`#tab-${tab.replace(/\s+/g,'-')}`) || container.querySelector(`#tab-${tab}`);
        if (el) el.style.display = 'block';
      });
    });

    // Back to clubs
    container.querySelector('#club-back-btn')?.addEventListener('click', () => closeClubModal());

    // Create event form
    container.querySelector('#club-create-event-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const title = container.querySelector('#event-title').value.trim();
      const date = container.querySelector('#event-date').value;
      const time = container.querySelector('#event-time').value;
      const desc = container.querySelector('#event-desc').value.trim();
      const eventsKey = `club_events__${info.displayName}`;

      // Try backend first
      const API_BASE = window.API_BASE_URL || 'http://localhost:8000';
      const clubId = await getClubIdByName(info.displayName);
      if (clubId) {
        try {
          const payload = {
            club_id: clubId,
            title,
            description: desc,
            activity_type: 'Event',
            start_date: new Date(date + (time ? 'T' + time : '')).toISOString(),
            location: '',
            expected_participants: 0
          };
          const resp = await fetch(`${API_BASE}/clubs/${clubId}/activities`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if (resp.ok) {
            showToast('Event created (server)');
            renderEventsList(eventsKey, container.querySelector('#club-events-list'), info.displayName);
            container.querySelector('#club-create-event-form').reset();
            return;
          }
        } catch (e) {
          console.warn('Backend create event failed, falling back to localStorage');
        }
      }

      // Fallback to localStorage (demo)
      const existing = JSON.parse(localStorage.getItem(eventsKey) || '[]');
      existing.unshift({ title, date, time, desc, created_at: new Date().toISOString() });
      localStorage.setItem(eventsKey, JSON.stringify(existing));
      renderEventsList(eventsKey, container.querySelector('#club-events-list'), info.displayName);
      showToast('Event created');
      container.querySelector('#club-create-event-form').reset();
    });

    // Today's meet form
    container.querySelector('#club-today-meet-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const loc = container.querySelector('#meet-location').value.trim();
      const time = container.querySelector('#meet-time').value;
      const notes = container.querySelector('#meet-notes').value.trim();
      const key = `club_meets__${info.displayName}`;

      // Try backend: create a ClubActivity with type 'Meeting'
      const API_BASE = window.API_BASE_URL || 'http://localhost:8000';
      const clubId = await getClubIdByName(info.displayName);
      if (clubId) {
        try {
          const startIso = new Date().toISOString();
          const payload = {
            club_id: clubId,
            title: `Meet - ${loc || 'On Campus'}`,
            description: notes,
            activity_type: 'Meeting',
            start_date: startIso,
            location: loc || undefined,
            expected_participants: 0
          };
          const resp = await fetch(`${API_BASE}/clubs/${clubId}/activities`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
          });
          if (resp.ok) {
            showToast('Meet scheduled (server)');
            renderMeetsList(key, container.querySelector('#club-meet-list'));
            container.querySelector('#club-today-meet-form').reset();
            return;
          }
        } catch (e) {
          console.warn('Backend meet schedule failed, falling back to localStorage');
        }
      }

      const arr = JSON.parse(localStorage.getItem(key) || '[]');
      arr.unshift({ loc, time, notes, at: new Date().toISOString() });
      localStorage.setItem(key, JSON.stringify(arr));
      renderMeetsList(key, container.querySelector('#club-meet-list'));
      showToast('Meet scheduled');
      container.querySelector('#club-today-meet-form').reset();
    });

    // Render lists
    renderEventsList(`club_events__${info.displayName}`, container.querySelector('#club-events-list'), info.displayName);
    renderMeetsList(`club_meets__${info.displayName}`, container.querySelector('#club-meet-list'));

    // Mount attendance UI (club-attendance.js will handle behavior if present)
    const attendanceContainer = container.querySelector('#club-attendance-ui');
    attendanceContainer.innerHTML = `<div data-club="${info.displayName}" class="club-attendance-root"></div>`;
    // let club-attendance script detect and bind to .club-attendance-root

    // Show modal
    document.getElementById('club-page-modal').style.display = 'flex';
  }

  async function getClubIdByName(name) {
    const API_BASE = window.API_BASE_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${API_BASE}/clubs`);
      if (!res.ok) return null;
      const clubs = await res.json();
      const found = clubs.find(c => c.name.toLowerCase().includes(name.toLowerCase()) || name.toLowerCase().includes(c.name.toLowerCase()));
      return found ? found.id : null;
    } catch (e) {
      return null;
    }
  }

  async function renderEventsList(key, el, clubName) {
    if (!el) return;
    const API_BASE = window.API_BASE_URL || 'http://localhost:8000';
    const clubId = await getClubIdByName(clubName || key.replace('club_events__',''));

    if (clubId) {
      // fetch from backend
      try {
        const resp = await fetch(`${API_BASE}/clubs/${clubId}/activities`);
        if (resp.ok) {
          const items = await resp.json();
          if (!items.length) { el.innerHTML = '<p style="color:var(--muted-color)">No events yet.</p>'; return; }
          el.innerHTML = items.map(it => `
            <div style="padding:8px 10px;border-radius:8px;background:var(--muted-bg);margin-bottom:8px;">
              <strong>${it.title}</strong>
              <div style="font-size:12px;color:var(--muted-color)">${new Date(it.start_date).toLocaleDateString()} ${it.start_date ? '• ' + new Date(it.start_date).toLocaleTimeString() : ''}</div>
              <div style="margin-top:6px">${it.description || ''}</div>
            </div>
          `).join('');
          return;
        }
      } catch (e) {
        /* fall back to localStorage */
      }
    }

    const items = JSON.parse(localStorage.getItem(key) || '[]');
    if (!items.length) { el.innerHTML = '<p style="color:var(--muted-color)">No events yet.</p>'; return; }
    el.innerHTML = items.map(it => `
      <div style="padding:8px 10px;border-radius:8px;background:var(--muted-bg);margin-bottom:8px;">
        <strong>${it.title}</strong>
        <div style="font-size:12px;color:var(--muted-color)">${it.date} ${it.time ? '• ' + it.time : ''}</div>
        <div style="margin-top:6px">${it.desc || ''}</div>
      </div>
    `).join('');
  }

  function renderMeetsList(key, el) {
    const items = JSON.parse(localStorage.getItem(key) || '[]');
    if (!el) return;
    if (!items.length) { el.innerHTML = '<p style="color:var(--muted-color)">No meets scheduled.</p>'; return; }
    el.innerHTML = items.map(it => `
      <div style="padding:8px 10px;border-radius:8px;background:var(--muted-bg);margin-bottom:8px;">
        <div><strong>${it.loc || '(location)'}</strong> ${it.time ? ' • ' + it.time : ''}</div>
        <div style="font-size:12px;color:var(--muted-color)">${it.notes || ''}</div>
      </div>
    `).join('');
  }

  function closeClubModal() { document.getElementById('club-page-modal').style.display = 'none'; }

  function showToast(msg) {
    const n = document.createElement('div'); n.textContent = msg; n.style.cssText = 'position:fixed;bottom:20px;left:20px;background:#0b1a12;color:#bfffe4;padding:8px 12px;border-radius:8px;z-index:2200;';
    document.body.appendChild(n); setTimeout(() => n.remove(), 2000);
  }

  document.addEventListener('DOMContentLoaded', () => {
    // Attach click to every club-card
    document.querySelectorAll('.club-card').forEach(card => {
      card.style.cursor = 'pointer';
      card.addEventListener('click', (e) => {
        const title = card.querySelector('h4')?.textContent?.trim() || 'Club';
        openClubModal(title);
      });
    });

    // Close handlers
    document.querySelectorAll('#club-page-modal .modal-close').forEach(btn => btn.addEventListener('click', () => { document.getElementById('club-page-modal').style.display = 'none'; }));
  });
})();