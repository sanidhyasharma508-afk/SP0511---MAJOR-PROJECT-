/**
 * Frontend Security & Token Management Test Suite
 * Executed with Node.js built-in test runner: node --test
 *
 * Verifies:
 * 1. DOMUtils.escapeHtml escapes dangerous HTML characters to prevent DOM XSS.
 * 2. DOMUtils.isSafeUrl and sanitizeUrl reject javascript:, data:, and vbscript: URIs.
 * 3. APIClient manages token storage, refresh tokens, and token clearing cleanly.
 * 4. APIClient handles 401 Unauthorized vs 403 Forbidden correctly without unintended logouts.
 * 5. Static AST / source inspection verifies verified XSS sink locations in frontend files
 *    now use safe textContent or DOM creation APIs.
 */

const { describe, it, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// Import config and DOMUtils
const { CONFIG, DOMUtils, APIClient } = require('../config.js');

// Mock localStorage and sessionStorage for Node environment
class MockStorage {
    constructor() {
        this.store = {};
    }
    getItem(key) {
        return Object.prototype.hasOwnProperty.call(this.store, key) ? this.store[key] : null;
    }
    setItem(key, value) {
        this.store[key] = String(value);
    }
    removeItem(key) {
        delete this.store[key];
    }
    clear() {
        this.store = {};
    }
}

global.localStorage = new MockStorage();
global.sessionStorage = new MockStorage();

describe('Frontend Security: DOMUtils & XSS Prevention', () => {
    it('DOMUtils.escapeHtml should encode <, >, &, ", and \'', () => {
        const payload = '<script>alert("XSS & Injection \'test\'")</script>';
        const escaped = DOMUtils.escapeHtml(payload);
        assert.ok(!escaped.includes('<script>'), 'Must not contain unescaped <script>');
        assert.ok(!escaped.includes('</script>'), 'Must not contain unescaped </script>');
        assert.ok(!escaped.includes('"'), 'Must not contain unescaped double quotes');
        assert.ok(!escaped.includes("'"), 'Must not contain unescaped single quotes');
        assert.equal(
            escaped,
            '&lt;script&gt;alert(&quot;XSS &amp; Injection &#x27;test&#x27;&quot;)&lt;/script&gt;'
        );
    });

    it('DOMUtils.escapeHtml should handle null, undefined, and non-string values safely', () => {
        assert.equal(DOMUtils.escapeHtml(null), '');
        assert.equal(DOMUtils.escapeHtml(undefined), '');
        assert.equal(DOMUtils.escapeHtml(12345), '12345');
        assert.equal(DOMUtils.escapeHtml(0), '0');
        assert.equal(DOMUtils.escapeHtml(false), 'false');
    });

    it('DOMUtils.isSafeUrl should reject dangerous URL schemes', () => {
        assert.equal(DOMUtils.isSafeUrl('javascript:alert(1)'), false);
        assert.equal(DOMUtils.isSafeUrl('JAVASCRIPT:alert(1)'), false);
        assert.equal(DOMUtils.isSafeUrl(' javascript:void(0)'), false);
        assert.equal(DOMUtils.isSafeUrl('data:text/html,<script>alert(1)</script>'), false);
        assert.equal(DOMUtils.isSafeUrl('vbscript:msgbox(1)'), false);
    });

    it('DOMUtils.isSafeUrl should allow safe relative and absolute web URLs', () => {
        assert.equal(DOMUtils.isSafeUrl('/dashboard'), true);
        assert.equal(DOMUtils.isSafeUrl('./attendance'), true);
        assert.equal(DOMUtils.isSafeUrl('../profile'), true);
        assert.equal(DOMUtils.isSafeUrl('#section-schedule'), true);
        assert.equal(DOMUtils.isSafeUrl('https://campus.mbm.edu/api/events'), true);
        assert.equal(DOMUtils.isSafeUrl('http://localhost:3000'), true);
    });

    it('DOMUtils.sanitizeUrl should return fallback when URL is unsafe', () => {
        assert.equal(DOMUtils.sanitizeUrl('javascript:evil()', '#safe'), '#safe');
        assert.equal(DOMUtils.sanitizeUrl('https://valid.edu', '#safe'), 'https://valid.edu');
    });
});

describe('Frontend Authentication: Token Storage & Lifecycle', () => {
    let client;

    beforeEach(() => {
        global.localStorage.clear();
        global.sessionStorage.clear();
        client = new APIClient(CONFIG);
    });

    it('should set and get tokens in localStorage without exposing them in URLs', () => {
        client.setToken('test-access-token-12345');
        assert.equal(client.getToken(), 'test-access-token-12345');
        assert.equal(global.localStorage.getItem(CONFIG.AUTH.TOKEN_KEY), 'test-access-token-12345');
        // Ensure legacy key is also kept in sync
        assert.equal(global.localStorage.getItem('access_token'), 'test-access-token-12345');
    });

    it('clearToken should purge all tokens and expiry keys from local and session storage', () => {
        client.setToken('jwt-access-token');
        client.setRefreshToken('jwt-refresh-token');
        global.localStorage.setItem(CONFIG.AUTH.TOKEN_EXPIRY_KEY, '9999999999');
        global.sessionStorage.setItem(CONFIG.AUTH.TOKEN_KEY, 'jwt-session-token');

        client.clearToken();

        assert.equal(client.getToken(), null);
        assert.equal(client.getRefreshToken(), null);
        assert.equal(global.localStorage.getItem(CONFIG.AUTH.TOKEN_KEY), null);
        assert.equal(global.localStorage.getItem('access_token'), null);
        assert.equal(global.localStorage.getItem(CONFIG.AUTH.REFRESH_TOKEN_KEY), null);
        assert.equal(global.localStorage.getItem(CONFIG.AUTH.TOKEN_EXPIRY_KEY), null);
        assert.equal(global.sessionStorage.getItem(CONFIG.AUTH.TOKEN_KEY), null);
    });

    it('hasValidToken should detect expired tokens and clear them when no refresh token exists', () => {
        client.setToken('expired-token');
        global.localStorage.setItem(CONFIG.AUTH.TOKEN_EXPIRY_KEY, String(Date.now() - 5000)); // expired 5s ago

        const isValid = client.hasValidToken();
        assert.equal(isValid, false);
        assert.equal(client.getToken(), null, 'Expired token without refresh token must be cleared');
    });
});

describe('Frontend Source Code Verification: Remediation of Verified XSS Sinks', () => {
    it('dashboard-analytics.js must not interpolate risk reasons into innerHTML', () => {
        const filePath = path.join(__dirname, '..', 'js', 'dashboard-analytics.js');
        const code = fs.readFileSync(filePath, 'utf-8');

        // Check that old vulnerable line is removed
        assert.ok(
            !code.includes('textEl.innerHTML = `<strong>Attention:</strong> ${primaryReason}`'),
            'Must not concatenate primaryReason into innerHTML'
        );
        // Verify safe DOM pattern is present
        assert.ok(
            code.includes('strongEl.textContent = \'Attention: \''),
            'Must use textContent for Attention prefix'
        );
        assert.ok(
            code.includes('textEl.appendChild(document.createTextNode(primaryReason))'),
            'Must use createTextNode for primaryReason'
        );
    });

    it('schedule-management.js must not inject unescaped announcements or broken escapeHtml', () => {
        const filePath = path.join(__dirname, '..', 'js', 'schedule-management.js');
        const code = fs.readFileSync(filePath, 'utf-8');

        // Verify broken escapeHtml was replaced
        assert.ok(
            !code.includes('return text.replace(/\'/g, "&#x27;").replace(/\"/g, "&quot;");'),
            'Broken 2-character escapeHtml must be removed'
        );
        assert.ok(
            code.includes('.replace(/&/g, \'&amp;\')'),
            'escapeHtml must escape & to &amp;'
        );
        assert.ok(
            code.includes('.replace(/</g, \'&lt;\')'),
            'escapeHtml must escape < to &lt;'
        );

        // Verify announcements use safe DOM creation
        assert.ok(
            code.includes('titleEl.textContent = announcement.title'),
            'Announcements must set title via textContent'
        );
        assert.ok(
            code.includes('contentEl.textContent = announcement.content'),
            'Announcements must set content via textContent'
        );
    });

    it('qr-attendance.js must not inject unescaped student names or scan results', () => {
        const filePath = path.join(__dirname, '..', 'js', 'qr-attendance.js');
        const code = fs.readFileSync(filePath, 'utf-8');

        assert.ok(
            code.includes('h4.textContent = record.subject_name'),
            'Recent attendance list must use textContent for subject_name'
        );
        assert.ok(
            code.includes('msgDiv.textContent = message'),
            'Scan results must use textContent for message'
        );
        assert.ok(
            code.includes('tdName.textContent = record.student_name'),
            'Live attendance table must use textContent for student_name'
        );
    });

    it('club-attendance.js must not inject unescaped student rosters', () => {
        const filePath = path.join(__dirname, '..', 'js', 'club-attendance.js');
        const code = fs.readFileSync(filePath, 'utf-8');

        assert.ok(
            code.includes('strong.textContent = s.name'),
            'Club attendance roster must set student name via textContent'
        );
        assert.ok(
            code.includes('small.textContent = `${rollStr} • ${secStr}`'),
            'Club attendance roster must set meta via textContent'
        );
    });

    it('clubs-pages.js must not inject unescaped club activities', () => {
        const filePath = path.join(__dirname, '..', 'js', 'clubs-pages.js');
        const code = fs.readFileSync(filePath, 'utf-8');

        assert.ok(
            code.includes('titleStrong.textContent = it.title'),
            'Club activities must set title via textContent'
        );
        assert.ok(
            code.includes('descDiv.textContent = it.description'),
            'Club activities must set description via textContent'
        );
    });
});
