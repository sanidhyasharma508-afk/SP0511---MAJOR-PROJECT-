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

class APIClient {
    constructor(config = CONFIG) {
        this.config = config;
        this.baseURL = config.API.BASE_URL.replace(/\/+$/, '');
    }

    getToken() {
        return localStorage.getItem(this.config.AUTH.TOKEN_KEY);
    }

    setToken(token) {
        localStorage.setItem(this.config.AUTH.TOKEN_KEY, token);
    }

    hasValidToken() {
        const token = this.getToken();
        if (!token) return false;
        const expiry = localStorage.getItem(this.config.AUTH.TOKEN_EXPIRY_KEY);
        if (expiry && Date.now() > parseInt(expiry, 10)) {
            this.clearToken();
            return false;
        }
        return true;
    }

    clearToken() {
        localStorage.removeItem(this.config.AUTH.TOKEN_KEY);
        localStorage.removeItem(this.config.AUTH.REFRESH_TOKEN_KEY);
        localStorage.removeItem(this.config.AUTH.TOKEN_EXPIRY_KEY);
    }

    async request(method, endpoint, data = null, options = {}) {
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

        const responseData = response.status === 204
            ? null
            : await response.json().catch(() => null);

        if (!response.ok) {
            const errorMsg = responseData?.detail || responseData?.message || `HTTP ${response.status}`;
            const formattedMsg = typeof errorMsg === 'string' 
                ? errorMsg 
                : (Array.isArray(errorMsg) ? errorMsg.map(e => e.msg || e).join(', ') : JSON.stringify(errorMsg));

            // On 401 Unauthorized for protected endpoints (excluding login/register attempts)
            if (response.status === 401 && !endpoint.includes('login') && !endpoint.includes('register')) {
                this.clearToken();
                if (typeof window !== 'undefined' && window.AuthManager && typeof window.AuthManager.handleSessionExpired === 'function') {
                    window.AuthManager.handleSessionExpired();
                }
            }

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
                localStorage.setItem(this.config.AUTH.REFRESH_TOKEN_KEY, response.refresh_token);
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
    window.api = api;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CONFIG, APIClient, api };
}
