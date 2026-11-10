import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { test } from 'node:test';
import { pathToFileURL } from 'node:url';
const { NeighborrowApi, ApiError } = await import(pathToFileURL(process.env.API_CLIENT_MODULE));
const user = { id: 1, email: 'one@example.com', first_name: 'One', last_name: '', address: '', phone: '', social_url: '', residential_complex: null, is_resident_verified: false };
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

test('login attaches bearer token and logout clears in-memory session', async () => {
  let current;
  const api = new NeighborrowApi('http://api.test/api/v1', async (url, options) => {
    if (url.endsWith('/auth/login')) { assert.equal(options.headers.Authorization, undefined); return json({ access: 'access-1', refresh: 'refresh-1', user }); }
    assert.equal(options.headers.Authorization, 'Bearer access-1');
    if (url.endsWith('/auth/logout')) { assert.equal(JSON.parse(options.body).refresh, 'refresh-1'); return new Response(null, { status: 204 }); }
    return json(user);
  });
  api.subscribe(value => { current = value; });
  await api.login('one@example.com', 'test-password');
  assert.equal(current.id, 1);
  assert.equal((await api.request('/auth/me')).email, user.email);
  await api.logout();
  assert.equal(current, null);
});

test('residence confirmation updates the current user without a second login', async () => {
  let current;
  const enteredCode = randomBytes(16).toString('hex');
  const verified = { ...user, residential_complex: { id: 7, name: 'North Court' }, is_resident_verified: true };
  const api = new NeighborrowApi('http://api.test/api/v1', async (url, options) => {
    if (url.endsWith('/auth/login')) return json({ access: 'access-1', refresh: 'refresh-1', user });
    assert.equal(options.headers.Authorization, 'Bearer access-1');
    assert.equal(url.endsWith('/auth/residential-complex/verify'), true);
    assert.deepEqual(JSON.parse(options.body), { residential_complex: 7, code: enteredCode });
    return json(verified);
  });
  api.subscribe(value => { current = value; });
  await api.login(user.email, 'test-password');
  await api.verifyResidence(7, enteredCode);
  assert.equal(current.is_resident_verified, true);
  assert.equal(current.residential_complex.name, 'North Court');
});

test('simultaneous 401 responses share one refresh and use rotated tokens', async () => {
  let refreshes = 0;
  const api = new NeighborrowApi('http://api.test/api/v1', async (url, options) => {
    if (url.endsWith('/auth/login')) return json({ access: 'old', refresh: 'refresh-old', user });
    if (url.endsWith('/auth/refresh')) { refreshes++; await new Promise(resolve => setTimeout(resolve, 10)); return json({ access: 'new', refresh: 'refresh-new' }); }
    return options.headers.Authorization === 'Bearer old' ? json({ detail: 'expired' }, 401) : json({ ok: true });
  });
  await api.login(user.email, 'test-password');
  const results = await Promise.all([api.request('/auth/me'), api.request('/activity')]);
  assert.equal(refreshes, 1);
  assert(results.every(x => x.ok));
});

test('logout body uses the newly rotated refresh token after access expires', async () => {
  const refreshes = [];
  const api = new NeighborrowApi('http://api.test/api/v1', async (url, options) => {
    if (url.endsWith('/auth/login')) return json({ access: 'old', refresh: 'r1', user });
    if (url.endsWith('/auth/refresh')) return json({ access: 'new', refresh: 'r2' });
    refreshes.push(JSON.parse(options.body).refresh);
    return options.headers.Authorization === 'Bearer old' ? json({ detail: 'expired' }, 401) : new Response(null, { status: 204 });
  });
  await api.login(user.email, 'test-password'); await api.logout();
  assert.deepEqual(refreshes, ['r1', 'r2']);
});

test('failed refresh clears session instead of looping', async () => {
  let current, refreshes = 0;
  const api = new NeighborrowApi('http://api.test/api/v1', async url => {
    if (url.endsWith('/auth/login')) return json({ access: 'old', refresh: 'bad', user });
    if (url.endsWith('/auth/refresh')) refreshes++;
    return json({ detail: 'Invalid token' }, 401);
  });
  api.subscribe(value => { current = value; });
  await api.login(user.email, 'test-password');
  await assert.rejects(api.request('/auth/me'), e => e instanceof ApiError && e.status === 401);
  assert.equal(current, null); assert.equal(refreshes, 1);
});

test('clearing the session during refresh cannot restore it', async () => {
  let resolveRefresh, notifyRefresh;
  const started = new Promise(resolve => { notifyRefresh = resolve; });
  const api = new NeighborrowApi('http://api.test/api/v1', async url => {
    if (url.endsWith('/auth/login')) return json({ access: 'old', refresh: 'r1', user });
    if (url.endsWith('/auth/refresh')) { notifyRefresh(); return new Promise(resolve => { resolveRefresh = resolve; }); }
    return json({ detail: 'expired' }, 401);
  });
  let current; api.subscribe(value => { current = value; });
  await api.login(user.email, 'test-password');
  const request = api.request('/auth/me');
  await started; api.clearSession(); resolveRefresh(json({ access: 'new', refresh: 'r2' }));
  await assert.rejects(request, e => e.name === 'AbortError'); assert.equal(current, null);
});

test('validation errors keep field names and do not retry mutations', async () => {
  let count = 0;
  const api = new NeighborrowApi('http://api.test/api/v1', async () => { count++; return json({ title: ['This field may not be blank.'] }, 400); });
  await assert.rejects(api.request('/listings', { method: 'POST', body: {} }), e => e.status === 400 && e.message.includes('title'));
  assert.equal(count, 1);
});

test('residential complex code errors are visible', async () => {
  const api = new NeighborrowApi('http://api.test/api/v1', async () => json({ code: ['Incorrect code for the selected residential complex.'] }, 400));
  await assert.rejects(api.request('/auth/residential-complex/verify', { method: 'POST', body: { residential_complex: 2, code: 'wrong' } }),
    error => error instanceof ApiError && error.message.includes('Incorrect code'));
});

test('absolute URLs are rejected and abort stops requests', async () => {
  let count = 0;
  const api = new NeighborrowApi('http://api.test/api/v1', async () => { count++; return json({}); });
  await assert.rejects(api.request('https://another.example/'));
  await assert.rejects(api.request('//another.example/'));
  const controller = new AbortController(); controller.abort();
  await assert.rejects(api.request('/listings', { signal: controller.signal }), e => e.name === 'AbortError');
  assert.equal(count, 0);
});
