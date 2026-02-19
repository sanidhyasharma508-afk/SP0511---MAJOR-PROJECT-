/* Profile Edit - adds Edit Profile modal, image upload, and persistence (localStorage)
   Does NOT alter existing UI structure; only wires functionality and stores data locally.
*/
(function() {
  const STORAGE_KEY = 'studentProfile';

  function $(sel, ctx=document) { return ctx.querySelector(sel); }

  function loadProfile() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch(e) { return null; }
  }

  function saveProfile(profile) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile)); } catch(e) {}
  }

  function applyProfile(profile) {
    if (!profile) return;
    const avatar = profile.avatar || '';
    if (avatar) {
      $('#student-avatar').src = avatar;
      const sidebarImg = document.querySelector('.sidebar .user-profile-mini img');
      if (sidebarImg) sidebarImg.src = avatar;
      const profileBtnImg = document.querySelector('.profile-btn img');
      if (profileBtnImg) profileBtnImg.src = avatar;
    }
    if (profile.name) $('#student-name').textContent = profile.name;
    if (profile.branch) $('#student-branch').textContent = profile.branch;
    if (profile.roll) $('#student-roll').textContent = profile.roll;

    // Sidebar mini info
    const userInfoP = document.querySelector('.user-info-mini p');
    const userInfoSpan = document.querySelector('.user-info-mini span');
    if (userInfoP) userInfoP.textContent = profile.name || userInfoP.textContent;
    if (userInfoSpan) userInfoSpan.textContent = `${profile.branch || ''} • ${profile.section || ''}`.trim();
  }

  function openModal() { $('#profile-edit-modal').style.display = 'flex'; }
  function closeModal() { $('#profile-edit-modal').style.display = 'none'; }

  document.addEventListener('DOMContentLoaded', () => {
    // Populate section dropdown (A-Z then 1-9)
    const sectionSelect = $('#edit-section');
    if (sectionSelect && sectionSelect.children.length === 0) {
      for (let i = 0; i < 26; i++) {
        const opt = document.createElement('option'); opt.value = String.fromCharCode(65 + i); opt.textContent = String.fromCharCode(65 + i); sectionSelect.appendChild(opt);
      }
      for (let n = 1; n <= 9; n++) {
        const opt = document.createElement('option'); opt.value = String(n); opt.textContent = String(n); sectionSelect.appendChild(opt);
      }
    }

    // Load stored profile
    const stored = loadProfile();
    if (stored) {
      // Fill form defaults
      $('#edit-name').value = stored.name || '';
      $('#edit-branch').value = stored.branch || '';
      $('#edit-roll').value = stored.roll || '';
      $('#edit-section').value = stored.section || ($('#edit-section option')[0]?.value || 'A');
      if (stored.avatar) {
        $('#profile-pic-preview').src = stored.avatar; $('#profile-pic-preview').style.display = 'block';
      }
      applyProfile(stored);
    }

    // Open modal when Edit Profile button clicked
    const editBtn = document.querySelector('.student-profile-card .btn-icon[title="Edit Profile"]');
    editBtn?.addEventListener('click', (e) => { e.preventDefault(); openModal(); });

    // Modal close handlers
    document.querySelectorAll('#profile-edit-modal .modal-close').forEach(btn => btn.addEventListener('click', closeModal));

    // File preview
    $('#profile-pic-input')?.addEventListener('change', (ev) => {
      const file = ev.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        $('#profile-pic-preview').src = reader.result;
        $('#profile-pic-preview').style.display = 'block';
      };
      reader.readAsDataURL(file);
    });

    // Save profile
    $('#profile-edit-form')?.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const name = $('#edit-name').value.trim();
      const branch = $('#edit-branch').value.trim();
      const roll = $('#edit-roll').value.trim();
      const section = $('#edit-section').value;
      const avatarEl = $('#profile-pic-preview');
      const avatar = avatarEl && avatarEl.src ? avatarEl.src : null;

      const profile = { name, branch, roll, section, avatar };
      saveProfile(profile);
      applyProfile(profile);
      showSavedToast('Profile updated');
      closeModal();
    });

    function showSavedToast(msg) {
      const el = document.createElement('div');
      el.className = 'saved-toast';
      el.textContent = msg;
      el.style.cssText = 'position:fixed;bottom:20px;right:20px;background:rgba(0,0,0,0.8);color:#fff;padding:10px 14px;border-radius:8px;z-index:2000;';
      document.body.appendChild(el);
      setTimeout(() => el.remove(), 1800);
    }
  });
})();