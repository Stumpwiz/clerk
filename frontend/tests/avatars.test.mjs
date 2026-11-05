import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import ts from 'typescript';
import React from 'react';

const require = createRequire(import.meta.url);
const transpile = file => ts.transpileModule(readFileSync(new URL('../' + file, import.meta.url), 'utf8'),
    {compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX}}).outputText;
const mod = {exports: {}};
vm.runInNewContext(transpile('lib/avatars.ts'), {exports: mod.exports, require, AbortController, URL, fetch, Error});
const {loadAvatar, validateAvatar, avatarUrl, mutateAvatar} = mod.exports;
const path = '/api/avatars/1/' + 'a'.repeat(32) + '.png';
const tick = () => new Promise(resolve => setImmediate(resolve));
const image = {size: 42, type: 'image/png'};
const user = {id: 1, avatar_path: null};
test('production URL resolution and external URL refusal', () => {
    assert.equal(avatarUrl(path, 'https://api.mrrc.online/'), 'https://api.mrrc.online' + path);
    assert.equal(avatarUrl(path, ''), path);
    assert.throws(() => avatarUrl('https://evil.example/image', ''));
    assert.throws(() => avatarUrl('//evil.example/image', ''));
});
test('client size and format validation', () => {
    for (const type of ['image/jpeg', 'image/png', 'image/webp']) validateAvatar({...image, type, size: 2097152});
    assert.throws(() => validateAvatar({...image, size: 2097153}), /2 MiB/);
    assert.throws(() => validateAvatar({...image, type: 'image/svg+xml'}), /JPEG/);
});
test('fallback, credentials, blob cleanup and failed image retrieval', async () => {
    const published = [], revoked = [];
    let request;
    const urls = {createObjectURL: () => 'blob:photo', revokeObjectURL: url => revoked.push(url)};
    const cleanup = loadAvatar(path, 'https://api.mrrc.online', url => published.push(url), async (url, options) => {
        request = {url, options};
        return {ok: true, blob: async () => image};
    }, urls);
    await tick();
    assert.deepEqual(published, ['/logo.svg', 'blob:photo']);
    assert.equal(request.options.credentials, 'include');
    assert.equal(request.options.redirect, 'error');
    cleanup();
    assert.deepEqual(revoked, ['blob:photo']);
    assert.equal(request.options.signal.aborted, true);
    for (const fetcher of [async () => ({ok: false}), async () => { throw Error('offline'); }]) {
        const states = [];
        const dispose = loadAvatar(path, '', url => states.push(url), fetcher, urls);
        await tick();
        assert.equal(states.at(-1), '/logo.svg');
        dispose();
    }
    loadAvatar(null, '', url => assert.equal(url, '/logo.svg'), () => assert.fail())();
});
test('late response after cleanup never creates or publishes stale blob', async () => {
    let resolve;
    const states = [];
    const dispose = loadAvatar(path, '', url => states.push(url),
        () => new Promise(done => { resolve = done; }),
        {createObjectURL: () => assert.fail(), revokeObjectURL: () => assert.fail()});
    dispose();
    resolve({ok: true, blob: async () => image});
    await tick();
    assert.deepEqual(states, ['/logo.svg']);
});
test('upload replacement and removal publish server user to shared state', async () => {
    let current = user;
    for (const file of [image, image, null]) {
        const next = {...user, avatar_path: file ? path : null};
        await mutateAvatar(file, 'https://api.mrrc.online', value => { current = value; }, undefined, async (url, options) => {
            assert.equal(url, 'https://api.mrrc.online/api/auth/me/avatar');
            assert.equal(options.method, file ? 'PUT' : 'DELETE');
            assert.equal(options.credentials, 'include');
            assert.equal(options.body, file || undefined);
            return {ok: true, json: async () => next};
        });
        assert.equal(current, next);
    }
    await assert.rejects(mutateAvatar(image, '', () => assert.fail(), undefined,
        async () => ({ok: false, json: async () => ({detail: 'Invalid image'})})), /Invalid image/);
});

// Execute the actual manager with deterministic hooks, following the existing
// frontend tests' component harness convention. No browser or API is contacted.
function manager() {
    const slots = [], effects = [], revoked = [], updates = [];
    let index = 0;
    const hooks = {...React,
        useState(initial) { const i = index++; if (!(i in slots)) slots[i] = initial;
            return [slots[i], value => { slots[i] = value; }]; },
        useRef(initial) { const i = index++; return slots[i] ??= {current: initial}; },
        useEffect(fn, deps) { const i = index++; const old = slots[i];
            if (!old || deps.some((dep, j) => dep !== old.deps[j])) {
                slots[i] = {deps}; effects.push(() => {old?.cleanup?.(); slots[i].cleanup = fn();});
            }
        },
    };
    const compiled = {exports: {}};
    vm.runInNewContext(transpile('components/avatar-manager.tsx'), {
        exports: compiled.exports, Error, process: {env: {}}, AbortController,
        URL: {createObjectURL: () => 'blob:preview', revokeObjectURL: url => revoked.push(url)},
        require: name => name === 'react' ? hooks : name === './avatar' ? {Avatar: () => null} :
            name === '@/lib/avatars' ? {...mod.exports, mutateAvatar: async (file, base, update) => update({...user, avatar_path: file ? path : null})} : require(name),
    });
    let current = user;
    const tree = () => {index = 0; return compiled.exports.AvatarManager({user: current, onUpdate: next => {current = next; updates.push(next);}});};
    const settle = () => {tree(); effects.splice(0).forEach(fn => fn()); return tree();};
    return {tree, settle, revoked, updates, unmount: () => slots.forEach(slot => slot?.cleanup?.())};
}
function find(tree, predicate) {
    if (!tree || typeof tree !== 'object') return;
    if (predicate(tree)) return tree;
    for (const child of React.Children.toArray(tree.props?.children)) {
        const result = find(child, predicate); if (result) return result;
    }
}
test('profile selection previews locally, uploads, removes, and cleans up', async () => {
    const page = manager();
    page.settle();
    find(page.tree(), node => node.props.id === 'avatar-file').props.onChange({target: {files: [image]}});
    let tree = page.settle();
    assert.equal(find(tree, node => node.props.alt === 'Selected photo preview').props.src, 'blob:preview');
    find(tree, node => node.type === 'button' && node.props.children === 'Upload photo').props.onClick();
    await tick();
    tree = page.settle();
    assert.equal(page.updates[0].avatar_path, path);
    assert.deepEqual(page.revoked, ['blob:preview']);
    assert.equal(find(tree, node => node.props.role === 'status').props.children, 'Avatar saved.');
    find(tree, node => node.type === 'button' && node.props.children === 'Remove photo').props.onClick();
    await tick(); page.settle();
    assert.equal(page.updates.at(-1).avatar_path, null);
    page.unmount();
});
test('invalid selection produces accessible error and no preview', () => {
    const page = manager(); page.settle();
    find(page.tree(), node => node.props.id === 'avatar-file').props.onChange({target: {files: [{...image, size: 2097153}]}});
    assert.match(find(page.settle(), node => node.props.role === 'alert').props.children, /2 MiB/);
    assert.equal(find(page.tree(), node => node.props.alt === 'Selected photo preview'), undefined);
    page.unmount();
});
