import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

// Use the project's compiler so the tests also run on the Docker image's Node 20.
const source = readFileSync(new URL('../lib/user-deletion.ts', import.meta.url), 'utf8');
const {outputText} = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext}});
const {deleteUserWithConfirmation} = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

const target = {id: 2, email: 'jane@example.com', display_name: 'Jane Doe', is_active: false};
const forbidden = () => assert.fail('This operation must not run');

test('cancelled confirmation sends no DELETE', async () => {
    assert.equal(await deleteUserWithConfirmation(target, 1, () => false, forbidden), false);
});

test('confirmation identifies the account and successful deletion uses its ID', async () => {
    let deleted;
    assert.equal(await deleteUserWithConfirmation(target, 1, message => {
        assert.match(message, /Permanently delete Jane Doe \(jane@example.com\)/);
        assert.match(message, /cannot be undone/);
        return true;
    }, async id => { deleted = id; }), true);
    assert.equal(deleted, 2);
});

test('self deletion is refused regardless of active state', async () => {
    for (const is_active of [true, false]) {
        await assert.rejects(deleteUserWithConfirmation({...target, is_active}, 2, forbidden, forbidden), /own account/);
    }
});

test('active other user receives inactive-first explanation without confirmation', async () => {
    await assert.rejects(deleteUserWithConfirmation({...target, is_active: true}, 1, forbidden, forbidden), /first be made inactive/);
});

test('stale inactive UI state preserves server refusal after confirmation', async () => {
    await assert.rejects(deleteUserWithConfirmation(target, 1, () => true, async () => {
        throw new Error('This user must first be made inactive before deletion.');
    }), /first be made inactive/);
});
