import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require = createRequire(import.meta.url);
const ordinary = {id: 1, email: 'synthetic@example.invalid', display_name: 'Synthetic', is_active: true, is_admin: false};
const admin = {...ordinary, is_admin: true};
const record = {...ordinary, id: 2, display_name: 'ACCOUNT_SENTINEL', created_at: '2026-01-01', updated_at: '2026-01-01'};

// Execute real components with deterministic hooks and mocked I/O, without DOM
// dependencies, live API calls, or generated files. This is not a browser E2E test.
function harness(file, user, reply, exportName = 'default', options = {}) {
    let current = user, index = 0;
    let pathname = '/dashboard';
    const redirects = [];
    const router = {replace: path => redirects.push(path), refresh() {}};
    const context = React.createContext(null);
    let authRequests = 0;
    const slots = [], effects = [], requests = [];
    const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
    const hooks = {...React,
        useState(initial) {
            const i = index++;
            if (!(i in slots)) slots[i] = initial;
            return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }];
        },
        useCallback(fn, deps) {
            const i = index++;
            if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = {fn, deps};
            return slots[i].fn;
        },
        useEffect(fn, deps) {
            const i = index++;
            if (!slots[i] || !same(slots[i].deps, deps)) {
                const previous = slots[i];
                const slot = {deps};
                slots[i] = slot;
                effects.push(() => { previous?.cleanup?.(); slot.cleanup = fn(); });
            }
        },
    };
    const stub = () => null;
    function mockedRequire(name) {
        if (name === 'react') return hooks;
        if (name === '@/lib/current-user') return {useCurrentUser: () => current, CurrentUserContext: context};
        if (name === '@/lib/auth') return {getCurrentUser: async () => { authRequests++; return options.getCurrentUser ? options.getCurrentUser() : current; }};
        if (name === 'next/link') return {__esModule: true, default: ({children, href}) => React.createElement('a', {href}, children)};
        if (name === 'next/image') return {__esModule: true, default: stub};
        if (name === 'next/navigation') return {usePathname: () => pathname, useRouter: () => router};
        if (name === '@/components/navigation' && options.Navigation) return {Navigation: options.Navigation};
        if (name === '@/components/modal') return {Modal: ({isOpen, children}) => isOpen ? React.createElement('section', null, children) : null};
        if (name === 'lucide-react' || name.startsWith('@/components/')) return new Proxy({}, {get: () => stub});
        if (name === '@/lib/user-deletion') return {deleteUserWithConfirmation: stub};
        return require(name);
    }
    const source = readFileSync(new URL(`../${file}`, import.meta.url), 'utf8');
    const {outputText} = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true}});
    const compiledModule = {exports: {}};
    vm.runInNewContext(outputText, {module: compiledModule, exports: compiledModule.exports, require: mockedRequire, process: {env: {}}, console,
        fetch: async (...args) => { requests.push(args); return reply(...args); },
    }, {filename: file});
    const tree = () => { index = 0; return compiledModule.exports[exportName]({user: current, children: options.children}); };
    const render = () => renderToStaticMarkup(tree());
    return {render, tree, context, requests, redirects, get authRequests() { return authRequests; },
        setPath(path) { pathname = path; }, setUser(user) { current = user; }, async settle() {
        for (let i = 0; i < 5; i++) {
            const html = render(), pending = effects.splice(0);
            if (!pending.length) return html;
            pending.forEach(fn => fn());
            await new Promise(resolve => setImmediate(resolve));
        }
        return render();
    }};
}
for (const [file, name] of [['components/navigation.tsx', 'Navigation'], ['app/dashboard/page.tsx', 'default'], ['app/dashboard/help/page.tsx', 'default']]) {
    test(`${file}: only explicit administrators see Users`, () => {
        for (const user of [ordinary, {...ordinary, is_admin: undefined}, {...ordinary, is_admin: 'true'}])
            assert.doesNotMatch(harness(file, user, null, name).render(), /href="\/dashboard\/users"/);
        assert.match(harness(file, admin, null, name).render(), /href="\/dashboard\/users"/);
    });
}
test('Profile and Change Password remain visible to both roles', () => {
    for (const user of [ordinary, admin]) {
        assert.match(harness('app/dashboard/page.tsx', user).render(), /href="\/dashboard\/profile"/);
        const html = harness('app/dashboard/help/page.tsx', user).render();
        assert.match(html, /Change your own password/);
        assert.match(html, /href="\/dashboard\/profile"/);
    }
});
for (const user of [ordinary, null, {...ordinary, is_admin: undefined}]) {
    test(`Users page makes no account request for ${user === null ? 'unresolved' : String(user.is_admin)}`, async () => {
        const page = harness('app/dashboard/users/page.tsx', user, () => assert.fail('Forbidden request'));
        const html = await page.settle();
        assert.equal(page.requests.length, 0);
        assert.doesNotMatch(html, /All Users|Add User|ACCOUNT_SENTINEL/);
        if (user) assert.match(html, /Access denied/);
    });
}
test('Users page waits for administrator before fetching accounts', async () => {
    const page = harness('app/dashboard/users/page.tsx', null, () => ({ok: true, json: async () => [record]}));
    assert.doesNotMatch(await page.settle(), /All Users|ACCOUNT_SENTINEL/);
    assert.equal(page.requests.length, 0);
    page.setUser(admin);
    assert.doesNotMatch(page.render(), /ACCOUNT_SENTINEL/);
    assert.match(await page.settle(), /ACCOUNT_SENTINEL/);
    assert.equal(page.requests.length, 1);
    assert.equal(page.requests[0][0], '/api/users/list');
});
test('Backend 403 denies access without reading the account response', async () => {
    const page = harness('app/dashboard/users/page.tsx', admin, () => ({ok: false, status: 403, json: () => assert.fail('Forbidden body read')}));
    const html = await page.settle();
    assert.match(html, /Access denied/);
    assert.doesNotMatch(html, /All Users|Add User|ACCOUNT_SENTINEL/);
    assert.equal(page.requests.length, 1);
});
test('Later 403 removes previously displayed accounts', async () => {
    let revoked = false;
    const page = harness('app/dashboard/users/page.tsx', admin, () => revoked ? {ok: false, status: 403} : {ok: true, json: async () => [record]});
    assert.match(await page.settle(), /ACCOUNT_SENTINEL/);
    revoked = true;
    page.setUser({...admin});
    const html = await page.settle();
    assert.match(html, /Access denied/);
    assert.doesNotMatch(html, /ACCOUNT_SENTINEL|All Users/);
});

for (const refreshedUser of [ordinary, null]) {
    test(`shell refresh hides stale admin before ${refreshedUser ? 'ordinary' : 'invalid'} result`, async () => {
        let resolveRefresh;
        const refresh = new Promise(resolve => { resolveRefresh = resolve; });
        let refreshing = false, viewingUsers = false;
        const exposed = [];
        const page = harness('app/dashboard/users/page.tsx', null, () => assert.fail('Account request forbidden'));
        let shell;
        function Probe() {
            const user = React.useContext(shell.context);
            exposed.push(user);
            if (!viewingUsers) return React.createElement('span', null, 'ORDINARY_NAVIGATION');
            page.setUser(user);
            return React.createElement('div', {dangerouslySetInnerHTML: {__html: page.render()}});
        }
        shell = harness('components/authenticated-shell.tsx', null, null, 'AuthenticatedShell', {
            getCurrentUser: () => refreshing ? refresh : admin,
            Navigation: ({user}) => React.createElement('nav', null, user.is_admin === true ? 'ADMIN_NAVIGATION' : 'ORDINARY_NAVIGATION'),
            children: React.createElement(Probe),
        });
        assert.match(await shell.settle(), /ADMIN_NAVIGATION/);
        assert.equal(shell.authRequests, 1);
        await shell.settle();
        assert.equal(shell.authRequests, 1);
        refreshing = true;
        viewingUsers = true;
        exposed.length = 0;
        shell.setPath('/dashboard/users');
        assert.doesNotMatch(shell.render(), /ADMIN_NAVIGATION|ACCOUNT_SENTINEL|All Users/);
        assert.equal(exposed.length, 0, 'no stale provider value before effects run');
        assert.doesNotMatch(await shell.settle(), /ADMIN_NAVIGATION|All Users/);
        assert.equal(shell.authRequests, 2);
        assert.equal(page.requests.length, 0);
        resolveRefresh(refreshedUser);
        await new Promise(resolve => setImmediate(resolve));
        const html = await shell.settle();
        if (refreshedUser) {
            assert.match(html, /Access denied/);
            assert.match(html, /ORDINARY_NAVIGATION/);
            assert.ok(exposed.every(user => user.is_admin === false));
            await page.settle();
        } else {
            assert.equal(exposed.length, 0);
            assert.equal(shell.redirects.at(-1), '/local-login?next=%2Fdashboard%2Fusers');
        }
        assert.equal(page.requests.length, 0);
        assert.equal(shell.authRequests, 2);
    });
}

function findElement(node, predicate) {
    if (!node || typeof node !== 'object') return null;
    if (Array.isArray(node)) {
        for (const child of node) { const found = findElement(child, predicate); if (found) return found; }
        return null;
    }
    if (node.props?.isOpen === false) return null;
    if (predicate(node)) return node;
    return findElement(node.props?.children, predicate);
}

test('mutation 403 preserves accounts and displays administrator deactivation refusal', async () => {
    const refusal = 'Administrator accounts cannot be deactivated.';
    const page = harness('app/dashboard/users/page.tsx', admin, (url, options) => {
        if (options.method === 'PUT') {
            assert.equal(url, '/api/users/2');
            assert.equal(JSON.parse(options.body).is_active, false);
            return {ok: false, status: 403, json: async () => ({detail: refusal})};
        }
        assert.equal(url, '/api/users/list');
        return {ok: true, json: async () => [record]};
    });
    await page.settle();
    findElement(page.tree(), node => node.props?.title === 'Edit user').props.onClick();
    findElement(page.tree(), node => node.type === 'input' && node.props.type === 'checkbox').props.onChange({target: {checked: false}});
    await findElement(page.tree(), node => node.type === 'form').props.onSubmit({preventDefault() {}});
    const html = await page.settle();
    assert.match(html, /Administrator accounts cannot be deactivated\./);
    assert.match(html, /ACCOUNT_SENTINEL/);
    assert.match(html, /All Users/);
    assert.doesNotMatch(html, /Access denied/);
    assert.equal(page.requests.length, 2);
});
