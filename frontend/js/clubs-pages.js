/* Club pages modal, activities & membership handling
   - Interacts directly with backend /clubs and /clubs/{id}/memberships
   - Persists memberships and activities in database with JWT authentication
   - No silent fallbacks to localStorage
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
    },
    'Coding Club': {
      displayName: 'Coding Club',
      hero: 'https://images.unsplash.com/photo-1515879218367-8466d910aaa4?w=1200&h=800&fit=crop',
      description: 'MBM University coding & competitive programming society.'
    }
  };

  function getAuthHeaders(headers = {}) {
    const token = localStorage.getItem('auth_token');
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...headers
    };
  }

  function showToast(msg, type = 'success') {
    const n = document.createElement('div');
    n.textContent = msg;
    const bg = type === 'error' ? 'rgba(214, 48, 49, 0.95)' : '#0b1a12';
    const textCol = type === 'error' ? '#ffffff' : '#bfffe4';
    n.style.cssText = `position:fixed;bottom:20px;left:20px;background:${bg};color:${textCol};padding:10px 16px;border-radius:8px;z-index:2200;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.3);`;
    document.body.appendChild(n);
    setTimeout(() => {
      n.style.opacity = '0';
      n.style.transition = 'opacity 0.3s ease';
      setTimeout(() => n.remove(), 300);
    }, 2800);
  }

  async function getClubIdByName(name) {
    const API_BASE = window.API_BASE_URL || '/api';
    try {
      const res = await fetch(`${API_BASE}/clubs`, { headers: getAuthHeaders() });
      if (!res.ok) return null;
      const clubs = await res.json();
      const found = clubs.find(c => 
        c.name.toLowerCase() === name.toLowerCase() ||
        c.name.toLowerCase().includes(name.toLowerCase()) || 
        name.toLowerCase().includes(c.name.toLowerCase())
      );
      return found ? found.id : null;
    } catch (e) {
      return null;
    }
  }

  async function openClubModal(title, clubIdParam = null) {
    const info = CLUB_DATA[title] || CLUB_DATA[title.split(' - ')[0]] || { displayName: title, hero: '', description: '' };
    const modal = document.getElementById('club-page-modal');
    const container = document.getElementById('club-page-content');
    const API_BASE = window.API_BASE_URL || '/api';

    const clubId = clubIdParam || await getClubIdByName(title);

    container.innerHTML = `
      <div class="club-hero">
        <img src="${info.hero || 'https://images.unsplash.com/photo-1504198453319-5ce911bafcde?w=800&h=600&fit=crop'}" alt="${info.displayName}">
        <div>
          <h2>${info.displayName}</h2>
          <p style="margin:6px 0 0; color:var(--muted-color)">${info.description || ''}</p>
          <div style="margin-top:10px; display:flex; gap:10px; align-items:center;">
            <button id="club-back-btn" class="btn btn-outline">← Back to Clubs</button>
            ${clubId ? `<button id="modal-club-join-btn" class="btn btn-primary" data-club-id="${clubId}">Join Club</button>` : ''}
          </div>
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
            <h4>Create Event / Activity</h4>
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

    // Wire tab buttons
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

    // Join button in modal
    const modalJoinBtn = container.querySelector('#modal-club-join-btn');
    if (modalJoinBtn && clubId) {
      checkMembershipStatus(clubId, modalJoinBtn);
      modalJoinBtn.addEventListener('click', () => toggleJoinClub(clubId, modalJoinBtn));
    }

    // Create event form (backend only)
    container.querySelector('#club-create-event-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const eventTitle = container.querySelector('#event-title').value.trim();
      const eventDate = container.querySelector('#event-date').value;
      const eventTime = container.querySelector('#event-time').value;
      const eventDesc = container.querySelector('#event-desc').value.trim();

      if (!clubId) {
        showToast('Club identifier not resolved. Cannot create event.', 'error');
        return;
      }

      try {
        const payload = {
          club_id: clubId,
          title: eventTitle,
          description: eventDesc,
          activity_type: 'Event',
          start_date: new Date(eventDate + (eventTime ? 'T' + eventTime : 'T09:00:00')).toISOString(),
          location: 'Campus',
          expected_participants: 0
        };
        const resp = await fetch(`${API_BASE}/clubs/${clubId}/activities`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(payload)
        });

        if (resp.ok) {
          showToast('Event created successfully');
          renderEventsList(container.querySelector('#club-events-list'), clubId);
          container.querySelector('#club-create-event-form').reset();
        } else {
          const err = await resp.json().catch(() => ({}));
          showToast(err.detail || 'Failed to create event. Advisor/Staff role required.', 'error');
        }
      } catch (e) {
        showToast(`Request failed: ${e.message}`, 'error');
      }
    });

    // Today's meet form (backend only)
    container.querySelector('#club-today-meet-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const loc = container.querySelector('#meet-location').value.trim();
      const meetTime = container.querySelector('#meet-time').value;
      const notes = container.querySelector('#meet-notes').value.trim();

      if (!clubId) {
        showToast('Club identifier not resolved. Cannot schedule meet.', 'error');
        return;
      }

      try {
        const todayStr = new Date().toISOString().split('T')[0];
        const startIso = new Date(todayStr + (meetTime ? 'T' + meetTime : 'T17:00:00')).toISOString();
        const payload = {
          club_id: clubId,
          title: `Meet - ${loc || 'Campus'}`,
          description: notes,
          activity_type: 'Meeting',
          start_date: startIso,
          location: loc || 'Campus',
          expected_participants: 0
        };
        const resp = await fetch(`${API_BASE}/clubs/${clubId}/activities`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(payload)
        });

        if (resp.ok) {
          showToast('Meet scheduled successfully');
          renderEventsList(container.querySelector('#club-meet-list'), clubId, 'Meeting');
          container.querySelector('#club-today-meet-form').reset();
        } else {
          const err = await resp.json().catch(() => ({}));
          showToast(err.detail || 'Failed to schedule meet. Advisor/Staff role required.', 'error');
        }
      } catch (e) {
        showToast(`Request failed: ${e.message}`, 'error');
      }
    });

    // Render activities from backend
    if (clubId) {
      renderEventsList(container.querySelector('#club-events-list'), clubId, 'Event');
      renderEventsList(container.querySelector('#club-meet-list'), clubId, 'Meeting');
    }

    // Mount attendance UI
    const attendanceContainer = container.querySelector('#club-attendance-ui');
    attendanceContainer.innerHTML = `<div data-club="${info.displayName}" class="club-attendance-root"></div>`;

    document.getElementById('club-page-modal').style.display = 'flex';
  }

  async function renderEventsList(el, clubId, typeFilter = null) {
    if (!el || !clubId) return;
    const API_BASE = window.API_BASE_URL || '/api';
    try {
      const resp = await fetch(`${API_BASE}/clubs/${clubId}/activities`, {
        headers: getAuthHeaders()
      });
      if (resp.ok) {
        let items = await resp.json();
        if (typeFilter) {
          items = items.filter(it => it.activity_type === typeFilter);
        }
        if (!items.length) {
          el.innerHTML = '<p style="color:var(--muted-color); padding: 8px 0;">No activities scheduled yet.</p>';
          return;
        }
        el.innerHTML = items.map(it => `
          <div style="padding:10px 12px;border-radius:8px;background:var(--muted-bg);margin-bottom:8px;">
            <strong>${it.title}</strong>
            <div style="font-size:12px;color:var(--muted-color)">
              ${new Date(it.start_date).toLocaleDateString()} ${it.start_date ? '• ' + new Date(it.start_date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}
              ${it.location ? ' • ' + it.location : ''}
            </div>
            <div style="margin-top:6px;font-size:13px;">${it.description || ''}</div>
          </div>
        `).join('');
      } else {
        el.innerHTML = '<p style="color:var(--muted-color)">Unable to load activities.</p>';
      }
    } catch (e) {
      el.innerHTML = '<p style="color:var(--muted-color)">Unable to connect to server.</p>';
    }
  }

  async function checkMembershipStatus(clubId, btn) {
    const token = localStorage.getItem('auth_token');
    if (!token) return;
    const API_BASE = window.API_BASE_URL || '/api';
    try {
      const resp = await fetch(`${API_BASE}/clubs/my-memberships`, { headers: getAuthHeaders() });
      if (resp.ok) {
        const memberships = await resp.json();
        const isMember = memberships.some(m => m.club_id === Number(clubId));
        if (isMember) {
          btn.dataset.isMember = 'true';
          btn.textContent = 'Leave Club';
          btn.className = 'btn btn-outline';
        } else {
          btn.dataset.isMember = 'false';
          btn.textContent = 'Join Club';
          btn.className = 'btn btn-primary';
        }
      }
    } catch (e) {}
  }

  async function toggleJoinClub(clubId, btn) {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      showToast('Please log in to join clubs', 'error');
      return;
    }
    const isMember = btn.dataset.isMember === 'true';
    const action = isMember ? 'leave' : 'join';
    const API_BASE = window.API_BASE_URL || '/api';
    try {
      btn.disabled = true;
      const resp = await fetch(`${API_BASE}/clubs/${clubId}/${action}`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (resp.ok) {
        if (action === 'join') {
          btn.dataset.isMember = 'true';
          btn.textContent = 'Leave Club';
          btn.className = btn.classList.contains('btn-small') ? 'btn btn-small btn-outline club-join-btn' : 'btn btn-outline';
          showToast('Joined club successfully!');
        } else {
          btn.dataset.isMember = 'false';
          btn.textContent = 'Join Club';
          btn.className = btn.classList.contains('btn-small') ? 'btn btn-small btn-primary club-join-btn' : 'btn btn-primary';
          showToast('Left club');
        }
        loadMyMemberships();
      } else {
        const err = await resp.json().catch(() => ({}));
        showToast(err.detail || `Failed to ${action} club`, 'error');
      }
    } catch (e) {
      showToast(`Network error: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
    }
  }

  async function loadMyMemberships() {
    const token = localStorage.getItem('auth_token');
    if (!token) return;
    const API_BASE = window.API_BASE_URL || '/api';
    try {
      const resp = await fetch(`${API_BASE}/clubs/my-memberships`, { headers: getAuthHeaders() });
      if (!resp.ok) return;
      const memberships = await resp.json();
      const memberClubIds = new Set(memberships.map(m => m.club_id));

      document.querySelectorAll('.club-card').forEach(card => {
        const clubId = card.dataset.clubId;
        const btn = card.querySelector('.club-join-btn');
        if (btn && clubId) {
          if (memberClubIds.has(Number(clubId))) {
            btn.dataset.isMember = 'true';
            btn.textContent = 'Leave Club';
            btn.className = 'btn btn-small btn-outline club-join-btn';
          } else {
            btn.dataset.isMember = 'false';
            btn.textContent = 'Join Club';
            btn.className = 'btn btn-small btn-primary club-join-btn';
          }
        }
      });

      // Update dashboard My Clubs card if present
      const myClubsPreview = document.querySelector('.my-clubs-card .club-preview');
      if (myClubsPreview && memberships.length > 0) {
        myClubsPreview.innerHTML = memberships.map(m => `
          <div class="club-item">
            <div class="club-badge" style="background: linear-gradient(135deg, #5B7EFF 0%, #3B5FE8 100%);">
              <i class="fas fa-users"></i>
            </div>
            <div class="club-details">
              <p class="club-name">${m.club_name || 'Club #' + m.club_id}</p>
              <p class="club-event">${m.role || 'Member'} • Joined ${new Date(m.joined_at).toLocaleDateString()}</p>
            </div>
          </div>
        `).join('');
      }
    } catch (e) {
      console.debug('Failed to load memberships:', e);
    }
  }

  function closeClubModal() {
    document.getElementById('club-page-modal').style.display = 'none';
  }

  document.addEventListener('DOMContentLoaded', async () => {
    // Match club cards to real database IDs
    const API_BASE = window.API_BASE_URL || '/api';
    let dbClubs = [];
    try {
      const res = await fetch(`${API_BASE}/clubs`);
      if (res.ok) dbClubs = await res.json();
    } catch (e) {}

    document.querySelectorAll('.club-card').forEach(card => {
      card.style.cursor = 'pointer';
      const title = card.querySelector('h4')?.textContent?.trim() || 'Club';
      const matchedClub = dbClubs.find(c => 
        c.name.toLowerCase() === title.toLowerCase() ||
        c.name.toLowerCase().includes(title.toLowerCase()) || 
        title.toLowerCase().includes(c.name.toLowerCase())
      );
      if (matchedClub) {
        card.dataset.clubId = matchedClub.id;
      }

      // Add click handler to card to open modal
      card.addEventListener('click', (e) => {
        if (e.target.closest('button')) return; // ignore join button click
        openClubModal(title, card.dataset.clubId);
      });

      // Wire join button
      const joinBtn = card.querySelector('button');
      if (joinBtn) {
        joinBtn.classList.add('club-join-btn');
        joinBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const cid = card.dataset.clubId;
          if (!cid) {
            showToast('Club identifier not found', 'error');
            return;
          }
          toggleJoinClub(cid, joinBtn);
        });
      }
    });

    // Close handlers
    document.querySelectorAll('#club-page-modal .modal-close').forEach(btn => {
      btn.addEventListener('click', closeClubModal);
    });

    // Initial membership load
    loadMyMemberships();
  });
})();
