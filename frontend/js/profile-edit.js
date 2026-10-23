/* Profile Edit - Persistent Student Profile Management
   Integrates directly with backend /api/v1/auth/profile.
   Enforces that students cannot modify privileged fields such as roll number.
*/
(function() {
  function $(sel, ctx=document) { return ctx.querySelector(sel); }

  function applyProfile(profile) {
    if (!profile) return;
    const name = profile.full_name || profile.name || '';
    const branch = profile.department || profile.branch || '';
    const roll = profile.roll_no || profile.roll || profile.username || '';
    const section = profile.section || '';
    const avatar = profile.avatar || '';

    if (avatar) {
      const studentAvatar = $('#student-avatar');
      if (studentAvatar) studentAvatar.src = avatar;
      const sidebarImg = document.querySelector('.sidebar .user-profile-mini img');
      if (sidebarImg) sidebarImg.src = avatar;
      const profileBtnImg = document.querySelector('.profile-btn img');
      if (profileBtnImg) profileBtnImg.src = avatar;
    }

    if (name) {
      const studentName = $('#student-name');
      if (studentName) studentName.textContent = name;
      const userInfoP = document.querySelector('.user-info-mini p');
      if (userInfoP) userInfoP.textContent = name;
    }

    if (branch) {
      const studentBranch = $('#student-branch');
      if (studentBranch) studentBranch.textContent = branch;
    }

    if (roll) {
      const studentRoll = $('#student-roll');
      if (studentRoll) studentRoll.textContent = roll;
    }

    const userInfoSpan = document.querySelector('.user-info-mini span');
    if (userInfoSpan) {
      const parts = [];
      if (branch) parts.push(branch);
      if (section && section !== '_') parts.push(`Sec ${section}`);
      userInfoSpan.textContent = parts.length > 0 ? parts.join(' • ') : (profile.role ? profile.role.toUpperCase() : 'Student');
    }
  }

  function openModal() {
    const modal = $('#profile-edit-modal');
    if (modal) modal.style.display = 'flex';
  }

  function closeModal() {
    const modal = $('#profile-edit-modal');
    if (modal) modal.style.display = 'none';
  }

  function showToast(msg, type = 'success') {
    const el = document.createElement('div');
    el.className = `saved-toast toast-${type}`;
    el.textContent = msg;
    const bg = type === 'error' ? 'rgba(214, 48, 49, 0.95)' : 'rgba(20, 30, 45, 0.92)';
    el.style.cssText = `position:fixed;bottom:24px;right:24px;background:${bg};color:#fff;padding:12px 18px;border-radius:8px;font-size:14px;box-shadow:0 4px 14px rgba(0,0,0,0.25);z-index:9999;transition:opacity 0.3s ease;`;
    document.body.appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 300);
    }, 2800);
  }

  document.addEventListener('DOMContentLoaded', () => {
    // Populate section dropdown (A-Z then 1-9)
    const sectionSelect = $('#edit-section');
    if (sectionSelect && sectionSelect.children.length === 0) {
      for (let i = 0; i < 26; i++) {
        const opt = document.createElement('option');
        const letter = String.fromCharCode(65 + i);
        opt.value = letter;
        opt.textContent = `Section ${letter}`;
        sectionSelect.appendChild(opt);
      }
      for (let n = 1; n <= 9; n++) {
        const opt = document.createElement('option');
        opt.value = String(n);
        opt.textContent = `Section ${n}`;
        sectionSelect.appendChild(opt);
      }
    }

    // Populate form with current user/student profile from API
    async function populateForm() {
      let profile = null;
      if (window.api && window.api.hasValidToken()) {
        try {
          profile = await window.api.getProfile();
          if (profile) {
            if (window.currentUser) {
              window.currentUser.full_name = profile.full_name;
              window.currentUser.email = profile.email;
              window.currentUser.avatar = profile.avatar;
            }
            if (window.currentStudent) {
              window.currentStudent.name = profile.full_name;
              window.currentStudent.department = profile.department;
              window.currentStudent.section = profile.section;
              window.currentStudent.roll_no = profile.roll_no;
            }
          }
        } catch (err) {
          console.debug('Failed to fetch profile from API, falling back to cached user state:', err.message);
        }
      }

      const user = window.currentUser;
      const student = window.currentStudent;

      const name = profile?.full_name || student?.name || user?.full_name || user?.username || '';
      const branch = profile?.department || student?.department || '';
      const roll = profile?.roll_no || student?.roll_no || user?.username || '';
      const section = profile?.section || student?.section || 'A';
      const avatar = profile?.avatar || user?.avatar || '';

      const editName = $('#edit-name');
      const editBranch = $('#edit-branch');
      const editRoll = $('#edit-roll');
      const editSection = $('#edit-section');
      const picPreview = $('#profile-pic-preview');

      if (editName) editName.value = name;
      if (editBranch) editBranch.value = branch;
      if (editRoll) {
        editRoll.value = roll;
        // Lock roll number for students
        const isStudent = (profile?.role || user?.role || 'student').toLowerCase() === 'student';
        if (isStudent) {
          editRoll.readOnly = true;
          editRoll.style.backgroundColor = 'rgba(0,0,0,0.06)';
          editRoll.style.cursor = 'not-allowed';
          editRoll.title = 'Roll numbers are institutional IDs and cannot be modified by students';
        } else {
          editRoll.readOnly = false;
          editRoll.style.backgroundColor = '';
          editRoll.style.cursor = '';
          editRoll.title = '';
        }
      }
      if (editSection && section) editSection.value = section;

      if (avatar && picPreview) {
        picPreview.src = avatar;
        picPreview.style.display = 'block';
      }

      if (profile) {
        applyProfile(profile);
      }
    }

    populateForm();
    window.addEventListener('auth:login', populateForm);
    window.addEventListener('auth:ready', populateForm);

    // Open modal when Edit Profile button clicked
    const editBtn = document.querySelector('.student-profile-card .btn-icon[title="Edit Profile"]');
    editBtn?.addEventListener('click', (e) => {
      e.preventDefault();
      populateForm();
      openModal();
    });

    // Modal close handlers
    document.querySelectorAll('#profile-edit-modal .modal-close').forEach(btn => {
      btn.addEventListener('click', closeModal);
    });

    // File preview
    $('#profile-pic-input')?.addEventListener('change', (ev) => {
      const file = ev.target.files?.[0];
      if (!file) return;
      if (file.size > 2 * 1024 * 1024) {
        showToast('Image file too large (max 2MB)', 'error');
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const preview = $('#profile-pic-preview');
        if (preview) {
          preview.src = reader.result;
          preview.style.display = 'block';
        }
      };
      reader.readAsDataURL(file);
    });

    // Save profile form submission
    $('#profile-edit-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault();

      const submitBtn = $('#profile-edit-form button[type="submit"]');
      const originalText = submitBtn ? submitBtn.textContent : 'Save';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';
      }

      const name = $('#edit-name')?.value.trim() || '';
      const branch = $('#edit-branch')?.value.trim() || '';
      const section = $('#edit-section')?.value || 'A';
      const picPreview = $('#profile-pic-preview');
      const avatar = picPreview && picPreview.src && !picPreview.src.includes('ui-avatars.com') ? picPreview.src : null;

      const payload = {
        full_name: name,
        department: branch,
        section: section,
      };

      if (avatar) {
        payload.avatar = avatar;
      }

      try {
        if (!window.api || !window.api.hasValidToken()) {
          throw new Error('Please sign in to save your profile');
        }

        const savedProfile = await window.api.updateProfile(payload);

        // Update local session caches
        if (window.currentUser) {
          window.currentUser.full_name = savedProfile.full_name;
          window.currentUser.email = savedProfile.email;
          if (savedProfile.avatar) window.currentUser.avatar = savedProfile.avatar;
        }
        if (window.currentStudent) {
          window.currentStudent.name = savedProfile.full_name;
          window.currentStudent.department = savedProfile.department;
          window.currentStudent.section = savedProfile.section;
          window.currentStudent.roll_no = savedProfile.roll_no;
        }

        applyProfile(savedProfile);
        window.dispatchEvent(new CustomEvent('auth:profile-updated', { detail: savedProfile }));

        showToast('Profile updated successfully');
        closeModal();
      } catch (err) {
        console.error('Failed to update profile:', err);
        showToast(err.message || 'Failed to update profile', 'error');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
        }
      }
    });
  });
})();