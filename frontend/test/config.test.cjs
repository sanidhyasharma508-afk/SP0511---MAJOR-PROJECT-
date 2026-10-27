const assert = require('node:assert/strict');
const { afterEach, test } = require('node:test');
const { APIClient, CONFIG } = require('../config.js');

const values = new Map();
global.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key)
};

afterEach(() => {
    values.clear();
    global.fetch = undefined;
});

test('login sends backend credentials and stores access and refresh tokens', async () => {
    let request;
    global.fetch = async (url, options) => {
        request = { url, options };
        return {
            ok: true,
            status: 200,
            json: async () => ({
                access_token: 'access-token',
                refresh_token: 'refresh-token',
                expires_in: 1800
            })
        };
    };

    const client = new APIClient(CONFIG);
    const result = await client.login('admin', 'admin123');

    assert.equal(request.url, '/api/v1/auth/login');
    assert.deepEqual(JSON.parse(request.options.body), {
        username: 'admin',
        password: 'admin123'
    });
    assert.equal(client.getToken(), 'access-token');
    assert.equal(values.get(CONFIG.AUTH.REFRESH_TOKEN_KEY), 'refresh-token');
    assert.equal(result.expires_in, 1800);
});

test('requests use the bearer token and surface API error details', async () => {
    values.set(CONFIG.AUTH.TOKEN_KEY, 'access-token');
    let request;
    global.fetch = async (url, options) => {
        request = { url, options };
        return {
            ok: false,
            status: 401,
            json: async () => ({ detail: 'Not authorized' })
        };
    };

    const client = new APIClient(CONFIG);
    await assert.rejects(client.get('/students'), /Not authorized/);
    assert.equal(request.url, '/api/students');
    assert.equal(request.options.headers.Authorization, 'Bearer access-token');
});

test('delete handles a successful no-content response', async () => {
    global.fetch = async () => ({ ok: true, status: 204 });
    const client = new APIClient(CONFIG);
    assert.equal(await client.delete('/students/1'), null);
});
