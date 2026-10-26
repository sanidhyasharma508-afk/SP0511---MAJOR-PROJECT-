// Frontend Configuration
const CONFIG = {
    API: {
        BASE_URL: '/api',
        TIMEOUT: 10000
    },
    AUTH: {
        TOKEN_KEY: 'auth_token',
        REFRESH_TOKEN_KEY: 'refresh_token',
        TOKEN_EXPIRY_KEY: 'token_expiry'
    },
    ROUTES: {
        LOGIN: '/v1/auth/login',
        LOGOUT: '/v1/auth/logout',
        PROFILE: '/v1/auth/profile',
        REGISTER: '/v1/auth/register',
        REFRESH: '/v1/auth/refresh',
        STUDY_TASKS: '/v1/study-tasks',
        STUDENTS: '/students',
        ATTENDANCE: '/attendance',
        CLUBS: '/clubs',
        EVENTS: '/events',
        COMPLAINTS: '/complaints',
        DASHBOARD: '/dashboard/summary',
        STUDENT_DASHBOARD: '/dashboard/student/me',
        ACADEMIC_RISK: '/risk/my-risk',
        SCHEDULES: '/schedules/my-schedule',
        ANALYTICS: '/analytics/complaint-heatmap',
        AGENTS: '/agents/'
    },
    UI: {
        ITEMS_PER_PAGE: 10,
        TOAST_DURATION: 3000,
        MODAL_ANIMATION_DURATION: 300
    },
    FEATURES: {
        ENABLE_AI_AGENTS: true,
        ENABLE_ANALYTICS: true,
        ENABLE_REAL_TIME_UPDATES: true,
        ENABLE_NOTIFICATIONS: true
    },
    ENVIRONMENT: 'development',
    DEBUG: true
};

/**
 * Safe DOM and URL utility functions to prevent Cross-Site Scripting (XSS)
 */
const DOMUtils = {
    /**
     * Escape HTML special characters for safe insertion into markup
     */
    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const str = String(text);
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;');
    },

    /**
     * Validate whether a URL uses a safe scheme (http, https, or relative path)
     * strictly disallowing javascript:, data:, and vbscript: URIs.
     */
    isSafeUrl(url) {
        if (!url || typeof url !== 'string') return false;
        const trimmed = url.trim();
        const lower = trimmed.toLowerCase();
        if (lower.startsWith('javascript:') || lower.startsWith('data:') || lower.startsWith('vbscript:')) {
            return false;
        }
        if (trimmed.startsWith('/') || trimmed.startsWith('./') || trimmed.startsWith('../') || trimmed.startsWith('#')) {
            return true;
        }
        try {
            const parsed = new URL(trimmed, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
            return parsed.protocol === 'http:' || parsed.protocol === 'https:';
        } catch (e) {
            return false;
        }
    },

    /**
     * Return safe sanitized URL or a safe fallback
     */
    sanitizeUrl(url, fallback = '#') {
        return this.isSafeUrl(url) ? url.trim() : fallback;
    }
};

class APIClient {
    constructor(config = CONFIG) {
        this.config = config;
        this.baseURL = config.API.BASE_URL.replace(/\/+$/, '');
    }

    getToken() {
        if (typeof localStorage === 'undefined') return null;
        return localStorage.getItem(this.config.AUTH.TOKEN_KEY) || localStorage.getItem('access_token');
    }

    setToken(token) {
        if (typeof localStorage === 'undefined') return;
        localStorage.setItem(this.config.AUTH.TOKEN_KEY, token);
        localStorage.setItem('access_token', token);
    }

    getRefreshToken() {
        if (typeof localStorage === 'undefined') return null;
        return localStorage.getItem(this.config.AUTH.REFRESH_TOKEN_KEY);
    }

    setRefreshToken(token) {
        if (typeof localStorage === 'undefined') return;
        localStorage.setItem(this.config.AUTH.REFRESH_TOKEN_KEY, token);
    }

    hasValidToken() {
        const token = this.getToken();
        if (!token) return false;
        if (typeof localStorage === 'undefined') return true;
        const expiry = localStorage.getItem(this.config.AUTH.TOKEN_EXPIRY_KEY);
        if (expiry && Date.now() > parseInt(expiry, 10)) {
            if (this.getRefreshToken()) {
                return true;
            }
            this.clearToken();
            return false;
        }
        return true;
    }

    clearToken() {
        if (typeof localStorage !== 'undefined') {
            localStorage.removeItem(this.config.AUTH.TOKEN_KEY);
            localStorage.removeItem('access_token');
            localStorage.removeItem(this.config.AUTH.REFRESH_TOKEN_KEY);
            localStorage.removeItem(this.config.AUTH.TOKEN_EXPIRY_KEY);
        }
        if (typeof sessionStorage !== 'undefined') {
            sessionStorage.removeItem(this.config.AUTH.TOKEN_KEY);
            sessionStorage.removeItem('access_token');
            sessionStorage.removeItem(this.config.AUTH.REFRESH_TOKEN_KEY);
            sessionStorage.removeItem(this.config.AUTH.TOKEN_EXPIRY_KEY);
        }
    }

    /**
     * Refresh expired access token using stored refresh token
     */
    async refreshToken() {
        const refreshTok = this.getRefreshToken();
        if (!refreshTok) return null;

        const refreshUrl = `${this.baseURL}/${this.config.ROUTES.REFRESH.replace(/^\/+/, '')}`;
        try {
            const resp = await fetch(refreshUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshTok })
            });

            if (resp.ok) {
                const data = await resp.json();
                if (data.access_token) {
                    this.setToken(data.access_token);
                    if (data.expires_in) {
                        localStorage.setItem(
                            this.config.AUTH.TOKEN_EXPIRY_KEY,
                            String(Date.now() + data.expires_in * 1000)
                        );
                    }
                    return data.access_token;
                }
            }
        } catch (e) {
            console.debug('Token refresh request failed');
        }
        return null;
    }

    async request(method, endpoint, data = null, options = {}, isRetry = false) {
        const url = `${this.baseURL}/${endpoint.replace(/^\/+/, '')}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        const token = this.getToken();
        if (token) {
            headers.Authorization = `Bearer ${token}`;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.config.API.TIMEOUT);
        const requestConfig = {
            method,
            headers,
            signal: options.signal || controller.signal
        };
        if (data !== null && data !== undefined) {
            requestConfig.body = JSON.stringify(data);
        }

        let response;
        try {
            response = await fetch(url, requestConfig);
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(`Request timed out after ${this.config.API.TIMEOUT}ms`);
            }
            throw new Error(`Network failure: ${error.message}`);
        } finally {
            clearTimeout(timeoutId);
        }

        // Handle 401 Unauthorized with automatic refresh token attempt
        if (response.status === 401 && !isRetry && !endpoint.includes('login') && !endpoint.includes('register') && !endpoint.includes('refresh')) {
            const newToken = await this.refreshToken();
            if (newToken) {
                return this.request(method, endpoint, data, options, true);
            }

            this.clearToken();
            if (typeof window !== 'undefined' && window.AuthManager && typeof window.AuthManager.handleSessionExpired === 'function') {
                window.AuthManager.handleSessionExpired();
            }
        }

        const responseData = response.status === 204
            ? null
            : await response.json().catch(() => null);

        if (!response.ok) {
            let errorMsg = responseData?.detail || responseData?.message;
            if (!errorMsg) {
                if (response.status === 403) {
                    errorMsg = 'Access denied: You do not have permission to access this resource.';
                } else if (response.status === 401) {
                    errorMsg = 'Authentication required. Please sign in.';
                } else {
                    errorMsg = `HTTP ${response.status}`;
                }
            }

            const formattedMsg = typeof errorMsg === 'string' 
                ? errorMsg 
                : (Array.isArray(errorMsg) ? errorMsg.map(e => e.msg || e).join(', ') : JSON.stringify(errorMsg));

            throw new Error(formattedMsg);
        }
        return responseData;
    }

    get(endpoint, options = {}) {
        return this.request('GET', endpoint, null, options);
    }

    post(endpoint, data, options = {}) {
        return this.request('POST', endpoint, data, options);
    }

    put(endpoint, data, options = {}) {
        return this.request('PUT', endpoint, data, options);
    }

    delete(endpoint, options = {}) {
        return this.request('DELETE', endpoint, null, options);
    }

    async login(username, password) {
        const response = await this.post(this.config.ROUTES.LOGIN, { username, password });
        if (response?.access_token) {
            this.setToken(response.access_token);
            if (response.refresh_token) {
                this.setRefreshToken(response.refresh_token);
            }
            if (response.expires_in) {
                localStorage.setItem(
                    this.config.AUTH.TOKEN_EXPIRY_KEY,
                    String(Date.now() + response.expires_in * 1000)
                );
            }
        }
        return response;
    }

    async register(userData) {
        return this.post(this.config.ROUTES.REGISTER, userData);
    }

    async logout() {
        const token = this.getToken();
        try {
            if (token) {
                return await this.post(this.config.ROUTES.LOGOUT, { token });
            }
        } finally {
            this.clearToken();
        }
    }

    getProfile() {
        return this.get(this.config.ROUTES.PROFILE);
    }

    updateProfile(profileData) {
        return this.put(this.config.ROUTES.PROFILE, profileData);
    }

    getStudyTasks(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(this.config.ROUTES.STUDY_TASKS + (query ? `?${query}` : ''));
    }

    createStudyTask(taskData) {
        return this.post(this.config.ROUTES.STUDY_TASKS, taskData);
    }

    updateStudyTask(taskId, taskData) {
        return this.put(`${this.config.ROUTES.STUDY_TASKS}/${taskId}`, taskData);
    }

    toggleStudyTask(taskId) {
        return this.request('PATCH', `${this.config.ROUTES.STUDY_TASKS}/${taskId}/complete`);
    }

    deleteStudyTask(taskId) {
        return this.delete(`${this.config.ROUTES.STUDY_TASKS}/${taskId}`);
    }

    getStudents(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(this.config.ROUTES.STUDENTS + (query ? `?${query}` : ''));
    }

    getAttendance(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(this.config.ROUTES.ATTENDANCE + (query ? `?${query}` : ''));
    }

    getClubs(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(this.config.ROUTES.CLUBS + (query ? `?${query}` : ''));
    }

    getDashboard() {
        return this.get(this.config.ROUTES.DASHBOARD);
    }

    getAnalytics(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(this.config.ROUTES.ANALYTICS + (query ? `?${query}` : ''));
    }
}

const api = new APIClient(CONFIG);

if (typeof window !== 'undefined') {
    window.CONFIG = CONFIG;
    window.DOMUtils = DOMUtils;
    window.api = api;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CONFIG, DOMUtils, APIClient, api };
}
