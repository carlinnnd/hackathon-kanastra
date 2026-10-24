const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { webcrypto } = require('node:crypto');
const ts = require('../node_modules/typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/services/auth.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const values = new Map();
const storage = { getItem: k => values.get(k) ?? null, setItem: (k, v) => values.set(k, v), removeItem: k => values.delete(k) };
globalThis.crypto = webcrypto;
globalThis.sessionStorage = storage;
globalThis.localStorage = storage;
globalThis.location = { origin: 'https://portal.example', search: '', assign: value => { location.assigned = value; } };
globalThis.history = { replaceState: () => { location.search = ''; } };
function load() {
  const m = { exports: {} };
  new Function('exports', 'module', 'require', code)(m.exports, m, require);
  return m.exports;
}
async function run() {
  let exchanged = 0;
  globalThis.fetch = async (url, options) => {
    if (url === '/api/auth/config') return Response.json({ configured: true, domain: 'example.auth0.com', clientId: 'public-client' });
    if (url === '/api/auth/exchange') {
      exchanged++;
      const body = JSON.parse(options.body);
      assert.equal(body.redirect_uri, 'https://portal.example/auth/callback');
      assert.ok(body.code_verifier.length >= 43);
      return Response.json({ user: { id: 'synthetic', nome: 'Teste', modo_autenticacao: 'auth0' } });
    }
    if (url === '/api/auth/logout') return Response.json({ ok: true });
    return Response.json({ detail: { mensagem: 'Entre para continuar.' } }, { status: 401 });
  };
  const auth = load();
  await auth.beginGoogleLogin();
  const redirect = new URL(location.assigned);
  assert.equal(redirect.searchParams.get('code_challenge_method'), 'S256');
  assert.ok(redirect.searchParams.get('code_challenge'));
  assert.ok(redirect.searchParams.get('state'));
  assert.ok(!location.assigned.includes('client_secret'));
  location.search = `?code=synthetic&state=${redirect.searchParams.get('state')}`;
  const user = await auth.restoreAuthSession();
  assert.equal(user.id, 'synthetic');
  assert.equal(exchanged, 1);
  assert.equal(await auth.restoreAuthSession(), user); // React StrictMode nao repete exchange.
  assert.equal(exchanged, 1);
  location.search = '?code=synthetic&state=replay';
  await assert.rejects(load().restoreAuthSession(), /ausente/);
  const invalid = load();
  await invalid.beginGoogleLogin();
  location.search = '?code=synthetic&state=forged';
  await assert.rejects(invalid.restoreAuthSession(), /inválida/);
  assert.equal(exchanged, 1);
  await auth.endAuthSession();
  assert.equal(await auth.restoreAuthSession(), null);
  console.log('Auth: PKCE, state, callback unico, replay, rejeicao e logout passaram.');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
