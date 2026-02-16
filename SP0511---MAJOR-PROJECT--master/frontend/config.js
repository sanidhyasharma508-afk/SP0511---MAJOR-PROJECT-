// Frontend Configuration
const CONFIG = {
    // API Configuration
    API: {
        BASE_URL: 'http://localhost:8000/api',
        TIMEOUT: 10000,
        RETRY_ATTEMPTS: 3
    },

    // Authentication
    AUTH: {
        TOKEN_KEY: 'auth_token',
        REFRESH_TOKEN_KEY: 'refresh_token',
        TOKEN_EXPIRY_KEY: 'token_expiry'
    },

    // Routes
    ROUTES: {
        LOGIN: '/auth/login',
        LOGOUT: '/auth/logout',
        PROFILE: '/auth/me',
        STUDENTS: '/students',
        ATTENDANCE: '/attendance',
        CLUBS: '/clubs',
        DASHBOARD: '/dashboard/summary',
        ANALYTICS: '/analytics/reports',
        AGENTS: '/ai/agents'
    },

    // UI Configuration
    UI: {
        ITEMS_PER_PAGE: 10,
        TOAST_DURATION: 3000,
        MODAL_ANIMATION_DURATION: 300
    },

    // Feature Flags
    FEATURES: {
        ENABLE_AI_AGENTS: true,
        ENABLE_ANALYTICS: true,
        ENABLE_REAL_TIME_UPDATES: true,
        ENABLE_NOTIFICATIONS: true
    },

    // Environment
    ENVIRONMENT: 'development',
    DEBUG: true
};

// API Helper Functions
class APIClient {
    constructor(config = CONFIG) {
        this.config = config;
        this.baseURL = config.API.BASE_URL;
    }

    // Get stored token
    getToken() {
        return localStorage.getItem(this.config.AUTH.TOKEN_KEY);
    }

    // Set token
    setToken(token) {
        localStorage.setItem(this.config.AUTH.TOKEN_KEY, token);
    }

    // Clear token
    clearToken() {
        localStorage.removeItem(this.config.AUTH.TOKEN_KEY);
        localStorage.removeItem(this.config.AUTH.REFRESH_TOKEN_KEY);
    }

    // Make API request
    async request(method, endpoint, data = null, options = {}) {
        try {
            const url = `${this.baseURL}${endpoint}`;
            const headers = {
                'Content-Type': 'application/json',
                ...options.headers
            };

            // Add auth token if available
            const token = this.getToken();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const config = {
                method,
                headers,
                timeout: this.config.API.TIMEOUT
            };

            if (data) {
                config.body = JSON.stringify(data);
            }

            const response = await fetch(url, config);
            const responseData = await response.json();

            if (!response.ok) {
                throw new Error(responseData.message || `HTTP ${response.status}`);
            }

            return responseData;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // GET request
    get(endpoint, options = {}) {
        return this.request('GET', endpoint, null, options);
    }

    // POST request
    post(endpoint, data, options = {}) {
        return this.request('POST', endpoint, data, options);
    }

    // PUT request
    put(endpoint, data, options = {}) {
        return this.request('PUT', endpoint, data, options);
    }

    // DELETE request
    delete(endpoint, options = {}) {
        return this.request('DELETE', endpoint, null, options);
    }

    // Login
    async login(email, password) {
        const response = await this.post(this.config.ROUTES.LOGIN, { email, password });
        if (response.data?.token) {
            this.setToken(response.data.token);
        }
        return response;
    }

    // Logout
    async logout() {
        this.clearToken();
        return this.post(this.config.ROUTES.LOGOUT, {});
    }

    // Get current user
    getProfile() {
        return this.get(this.config.ROUTES.PROFILE);
    }

    // Get students
    getStudents(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(this.config.ROUTES.STUDENTS + (query ? `?${query}` : ''));
    }

    // Get attendance
    getAttendance(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(this.config.ROUTES.ATTENDANCE + (query ? `?${query}` : ''));
    }

    // Get clubs
    getClubs(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(this.config.ROUTES.CLUBS + (query ? `?${query}` : ''));
    }

    // Get dashboard summary
    getDashboard() {
        return this.get(this.config.ROUTES.DASHBOARD);
    }

    // Get analytics
    getAnalytics(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(this.config.ROUTES.ANALYTICS + (query ? `?${query}` : ''));
    }
}

// Initialize API client
const api = new APIClient(CONFIG);

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CONFIG, APIClient, api };
}
