/**
 * Frontend Authentication Manager
 * Handles login, registration, token persistence, role-based UI adaptation,
 * session lifecycle, and logout with backend token revocation.
 */

(function(window) {
    'use strict';

    const AuthManager = {
        currentUser: null,
        currentStudent: null,

        async init() {
            this.bindElements();
            this.setupEventListeners();

            // Check if a valid token exists in storage
            if (window.api && window.api.hasValidToken()) {
                try {
                    await this.verifyAndLoadProfile();
                } catch (err) {
                    console.warn('Initial session validation failed:', err.message);
                    this.showAuthModal('Your session has expired. Please sign in again.');
                }
            } else {
                this.showAuthModal();
            }
        },

        bindElements() {
            this.authModal = document.getElementById('auth-modal');
            this.loginForm = document.getElementById('login-form');
            this.registerForm = document.getElementById('register-form');
            this.tabLogin = document.getElementById('tab-btn-login');
            this.tabRegister = document.getElementById('tab-btn-register');
            this.loginError = document.getElementById('login-error');
            this.regError = document.getElementById('reg-error');
            this.regSuccess = document.getElementById('reg-success');
            this.loginSubmitBtn = document.getElementById('login-submit-btn');
            this.regSubmitBtn = document.getElementById('reg-submit-btn');
        },

        setupEventListeners() {
            // Tab switching
            this.tabLogin?.addEventListener('click', () => this.switchTab('login'));
            this.tabRegister?.addEventListener('click', () => this.switchTab('register'));

            // Show/Hide password toggles
            this.setupPasswordToggle('toggle-login-password', 'login-password');
            this.setupPasswordToggle('toggle-reg-password', 'reg-password');
            this.setupPasswordToggle('toggle-reg-confirm-password', 'reg-confirm-password');

            // Login submission
            this.loginForm?.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.handleLogin();
            });

            // Registration submission
            this.registerForm?.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.handleRegistration();
            });

            // Logout buttons
            document.querySelectorAll('.btn-logout-trigger').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    await this.handleLogout();
                });
            });
        },

        setupPasswordToggle(toggleId, inputId) {
            const toggle = document.getElementById(toggleId);
            const input = document.getElementById(inputId);
            if (!toggle || !input) return;

            toggle.addEventListener('click', (e) => {
                e.preventDefault();
                const isPassword = input.type === 'password';
                input.type = isPassword ? 'text' : 'password';
                const icon = toggle.querySelector('i');
                if (icon) {
                    icon.className = isPassword ? 'fas fa-eye-slash' : 'fas fa-eye';
                }
            });
        },

        switchTab(tab) {
            this.hideAlerts();
            if (tab === 'login') {
                this.tabLogin?.classList.add('active');
                this.tabRegister?.classList.remove('active');
                if (this.loginForm) this.loginForm.style.display = 'block';
                if (this.registerForm) this.registerForm.style.display = 'none';
            } else {
                this.tabRegister?.classList.add('active');
                this.tabLogin?.classList.remove('active');
                if (this.loginForm) this.loginForm.style.display = 'none';
                if (this.registerForm) this.registerForm.style.display = 'block';
            }
        },

        hideAlerts() {
            if (this.loginError) this.loginError.style.display = 'none';
            if (this.regError) this.regError.style.display = 'none';
            if (this.regSuccess) this.regSuccess.style.display = 'none';
        },

        showAuthModal(noticeMessage = null) {
            if (this.authModal) {
                this.authModal.style.display = 'flex';
                this.authModal.removeAttribute('aria-hidden');
            }
            const app = document.getElementById('app');
            if (app) {
                app.setAttribute('aria-hidden', 'true');
                app.style.filter = 'blur(4px)';
            }
            if (noticeMessage && this.loginError) {
                this.loginError.textContent = noticeMessage;
                this.loginError.style.display = 'block';
            }
            this.switchTab('login');
        },

        hideAuthModal() {
            if (this.authModal) {
                this.authModal.style.display = 'none';
                this.authModal.setAttribute('aria-hidden', 'true');
            }
            const app = document.getElementById('app');
            if (app) {
                app.removeAttribute('aria-hidden');
                app.style.filter = 'none';
            }
            this.hideAlerts();
        },

        async handleLogin() {
            const usernameInput = document.getElementById('login-username');
            const passwordInput = document.getElementById('login-password');
            const username = usernameInput ? usernameInput.value.trim() : '';
            const password = passwordInput ? passwordInput.value : '';

            if (!username || !password) {
                this.showError(this.loginError, 'Please enter both username and password.');
                return;
            }

            this.setButtonLoading(this.loginSubmitBtn, true, 'Signing in...');
            this.hideAlerts();

            try {
                // Step 1: Call actual backend login endpoint
                await window.api.login(username, password);

                // Step 2: Fetch verified user profile from backend
                await this.verifyAndLoadProfile();

                // Step 3: Success state
                this.hideAuthModal();
                if (passwordInput) passwordInput.value = '';
                this.showToast(`Welcome, ${this.currentUser.full_name}!`);

                // Broadcast auth event to reload components
                window.dispatchEvent(new CustomEvent('auth:login', { detail: this.currentUser }));
            } catch (err) {
                console.error('Login error:', err);
                const msg = err.message || 'Invalid username or password';
                this.showError(this.loginError, msg);
            } finally {
                this.setButtonLoading(this.loginSubmitBtn, false, 'Sign In');
            }
        },

        async handleRegistration() {
            const fullName = document.getElementById('reg-fullname')?.value.trim();
            const username = document.getElementById('reg-username')?.value.trim();
            const email = document.getElementById('reg-email')?.value.trim();
            const password = document.getElementById('reg-password')?.value;
            const confirm = document.getElementById('reg-confirm-password')?.value;

            if (!fullName || !username || !email || !password || !confirm) {
                this.showError(this.regError, 'Please complete all required fields.');
                return;
            }

            if (password !== confirm) {
                this.showError(this.regError, 'Passwords do not match.');
                return;
            }

            if (password.length < 8) {
                this.showError(this.regError, 'Password must be at least 8 characters long.');
                return;
            }

            this.setButtonLoading(this.regSubmitBtn, true, 'Creating Account...');
            this.hideAlerts();

            try {
                // Public self-registration permits only student role
                const payload = {
                    full_name: fullName,
                    username: username,
                    email: email,
                    password: password,
                    role: 'student'
                };

                const res = await window.api.register(payload);
                this.showSuccess(this.regSuccess, res.message || 'Registration successful! You may now sign in.');

                // Switch to login tab and prefill username after 1.5s
                setTimeout(() => {
                    this.switchTab('login');
                    const loginUserInput = document.getElementById('login-username');
                    if (loginUserInput) {
                        loginUserInput.value = username;
                        document.getElementById('login-password')?.focus();
                    }
                }, 1500);
            } catch (err) {
                console.error('Registration error:', err);
                this.showError(this.regError, err.message || 'Registration failed. Please check your details.');
            } finally {
                this.setButtonLoading(this.regSubmitBtn, false, 'Create Student Account');
            }
        },

        async handleLogout() {
            try {
                if (window.api && typeof window.api.logout === 'function') {
                    await window.api.logout();
                }
            } catch (err) {
                console.warn('Backend logout warning:', err.message);
            } finally {
                if (window.api && typeof window.api.clearToken === 'function') {
                    window.api.clearToken();
                }
                this.currentUser = null;
                this.currentStudent = null;
                if (typeof window !== 'undefined') {
                    window.currentUser = null;
                    window.currentStudent = null;
                }
                this.clearHydratedUI();
                this.showAuthModal('You have been signed out successfully.');
                this.showToast('Logged out');
                window.dispatchEvent(new CustomEvent('auth:logout'));
            }
        },

        handleSessionExpired() {
            if (window.api && typeof window.api.clearToken === 'function') {
                window.api.clearToken();
            }
            this.currentUser = null;
            this.currentStudent = null;
            if (typeof window !== 'undefined') {
                window.currentUser = null;
                window.currentStudent = null;
            }
            this.clearHydratedUI();
            this.showAuthModal('Your session has expired. Please sign in again.');
            this.showToast('Session expired. Please log in.');
        },

        async verifyAndLoadProfile() {
            const profile = await window.api.getProfile();
            if (!profile || !profile.username) {
                throw new Error('Unable to resolve user profile');
            }

            this.currentUser = profile;
            window.currentUser = profile;

            // If user is a student, fetch linked student details safely
            if (profile.role.toLowerCase() === 'student') {
                try {
                    if (profile.linked_student_id) {
                        const studentRecord = await window.api.get(`/students/${profile.linked_student_id}`);
                        if (studentRecord && studentRecord.id) {
                            this.currentStudent = studentRecord;
                            window.currentStudent = studentRecord;
                        }
                    } else {
                        // Check if student record exists matching username or name
                        const students = await window.api.get('/students');
                        if (Array.isArray(students)) {
                            const match = students.find(s => s.roll_no === profile.username || (s.name && s.name.toLowerCase() === (profile.full_name || '').toLowerCase()));
                            if (match) {
                                this.currentStudent = match;
                                window.currentStudent = match;
                            }
                        }
                    }
                } catch (e) {
                    console.debug('No specific student record linked or accessible');
                }
            }

            this.applyAuthentication(profile, this.currentStudent);
            this.hideAuthModal();
        },

        applyAuthentication(user, student = null) {
            const role = (user.role || 'student').toLowerCase();
            const fullName = user.full_name || user.username;
            const avatarUrl = `https://ui-avatars.com/api/?name=${encodeURIComponent(fullName)}&background=5B7EFF&color=fff&size=100`;
            const miniAvatarUrl = `https://ui-avatars.com/api/?name=${encodeURIComponent(fullName)}&background=5B7EFF&color=fff&size=40`;

            // 1. Top header user avatar
            document.querySelectorAll('.profile-btn img').forEach(img => {
                img.src = miniAvatarUrl;
                img.alt = fullName;
            });

            // 2. Sidebar mini profile
            const sidebarImg = document.querySelector('.sidebar .user-profile-mini img');
            if (sidebarImg) {
                sidebarImg.src = miniAvatarUrl;
                sidebarImg.alt = fullName;
            }

            const sidebarName = document.querySelector('.user-info-mini p');
            if (sidebarName) sidebarName.textContent = fullName;

            const sidebarRoleSpan = document.querySelector('.user-info-mini span');
            if (sidebarRoleSpan) {
                if (student) {
                    sidebarRoleSpan.textContent = `${student.department || 'CS'} ΓÇó Sem ${student.semester || 4}`;
                } else {
                    sidebarRoleSpan.textContent = role.toUpperCase();
                }
            }

            // Role badge in sidebar
            let roleBadge = document.getElementById('user-role-badge');
            if (!roleBadge && sidebarName) {
                roleBadge = document.createElement('span');
                roleBadge.id = 'user-role-badge';
                roleBadge.className = `badge-role badge-role-${role}`;
                sidebarName.appendChild(roleBadge);
            }
            if (roleBadge) {
                roleBadge.textContent = role.toUpperCase();
                roleBadge.className = `badge-role badge-role-${role}`;
            }

            // 3. Dashboard Student Profile Card
            const studentNameEl = document.getElementById('student-name');
            if (studentNameEl) studentNameEl.textContent = fullName;

            const studentAvatarEl = document.getElementById('student-avatar');
            if (studentAvatarEl) studentAvatarEl.src = avatarUrl;

            const studentBranchEl = document.getElementById('student-branch');
            const studentYearEl = document.getElementById('student-year');
            const studentRollEl = document.getElementById('student-roll');

            if (student) {
                if (studentBranchEl) studentBranchEl.textContent = student.department || 'Computer Science Engineering';
                if (studentYearEl) studentYearEl.textContent = `Semester ${student.semester || 4}`;
                if (studentRollEl) studentRollEl.textContent = student.roll_no || user.username;
            } else {
                if (studentBranchEl) studentBranchEl.textContent = role === 'faculty' ? 'Faculty Member' : (role === 'admin' ? 'System Administrator' : 'Staff Member');
                if (studentYearEl) studentYearEl.textContent = `Account ID: ${user.user_id}`;
                if (studentRollEl) studentRollEl.textContent = user.username;
            }

            // 4. Role-Aware UI Customization
            this.applyRoleRestrictions(role);
        },

        applyRoleRestrictions(role) {
            // QR Attendance Panels
            const facultyTab = document.querySelector('.role-tab[data-role="faculty"]');
            const studentTab = document.querySelector('.role-tab[data-role="student"]');
            const facultyPanel = document.getElementById('faculty-panel');
            const studentPanel = document.getElementById('student-panel');

            if (role === 'student') {
                if (facultyTab) facultyTab.style.display = 'none';
                if (studentTab) {
                    studentTab.style.display = 'flex';
                    studentTab.classList.add('active');
                }
                if (facultyPanel) facultyPanel.classList.remove('active');
                if (studentPanel) studentPanel.classList.add('active');

                // Schedule management: hide announcement authoring for students
                const annForm = document.getElementById('announcement-form-container');
                if (annForm) annForm.style.display = 'none';
            } else if (role === 'faculty') {
                if (facultyTab) {
                    facultyTab.style.display = 'flex';
                    facultyTab.classList.add('active');
                }
                if (studentTab) {
                    studentTab.classList.remove('active');
                }
                if (facultyPanel) facultyPanel.classList.add('active');
                if (studentPanel) studentPanel.classList.remove('active');

                // Prefill faculty QR session form with verified credentials
                const facIdInput = document.getElementById('faculty-id');
                if (facIdInput) facIdInput.value = this.currentUser.username;
                const facNameInput = document.getElementById('faculty-name');
                if (facNameInput) facNameInput.value = this.currentUser.full_name;

                const annForm = document.getElementById('announcement-form-container');
                if (annForm) annForm.style.display = 'block';
            } else {
                // Admin / Staff
                if (facultyTab) facultyTab.style.display = 'flex';
                if (studentTab) studentTab.style.display = 'flex';
                const annForm = document.getElementById('announcement-form-container');
                if (annForm) annForm.style.display = 'block';
            }
        },

        clearHydratedUI() {
            const studentNameEl = document.getElementById('student-name');
            if (studentNameEl) studentNameEl.textContent = 'Guest User';
            const studentBranchEl = document.getElementById('student-branch');
            if (studentBranchEl) studentBranchEl.textContent = 'Not Signed In';
            const studentRollEl = document.getElementById('student-roll');
            if (studentRollEl) studentRollEl.textContent = '---';
            const sidebarName = document.querySelector('.user-info-mini p');
            if (sidebarName) sidebarName.textContent = 'Sign In Required';
            const roleBadge = document.getElementById('user-role-badge');
            if (roleBadge) roleBadge.remove();
        },

        setButtonLoading(btn, isLoading, text) {
            if (!btn) return;
            btn.disabled = isLoading;
            const span = btn.querySelector('span');
            const icon = btn.querySelector('i');
            if (isLoading) {
                if (span) span.textContent = text;
                if (icon) icon.className = 'fas fa-spinner fa-spin';
            } else {
                if (span) span.textContent = text;
                if (icon) {
                    icon.className = btn.id.includes('login') ? 'fas fa-sign-in-alt' : 'fas fa-user-plus';
                }
            }
        },

        showError(el, msg) {
            if (!el) return;
            el.textContent = msg;
            el.style.display = 'block';
        },

        showSuccess(el, msg) {
            if (!el) return;
            el.textContent = msg;
            el.style.display = 'block';
        },

        showToast(message) {
            const toast = document.createElement('div');
            toast.className = 'auth-toast';
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('hide');
                setTimeout(() => toast.remove(), 400);
            }, 3000);
        }
    };

    window.AuthManager = AuthManager;

    document.addEventListener('DOMContentLoaded', () => {
        AuthManager.init();
    });

})(window);
