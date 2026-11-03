import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

// Inspect fetch options structurally, including dynamic endpoints.
function fetches(page) {
    const source = ts.createSourceFile(page, readFileSync(new URL(`../app/dashboard/${page}/page.tsx`, import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const calls = [];
    function visit(node) {
        if (ts.isCallExpression(node) && node.expression.getText(source) === 'fetch') {
            const options = node.arguments[1];
            const properties = new Map(options.properties.map(p => [p.name.getText(source), p.initializer.getText(source).replaceAll("'", '').replaceAll('"', '')]));
            calls.push({url: node.arguments[0].getText(source), method: properties.get('method') || 'GET', credentials: properties.get('credentials')});
        }
        ts.forEachChild(node, visit);
    }
    visit(source);
    return calls;
}
for (const [page, generations] of [['reports', ['report.endpoint']], ['mailing-lists', ['list.endpoint', 'selected.endpoint']]]) {
    test(`${page}: generation uses POST, ordinary reads remain GET`, () => {
        const calls = fetches(page);
        for (const endpoint of generations) {
            const matching = calls.filter(c => c.url.includes(endpoint));
            assert.equal(matching.length, 1);
            assert.equal(matching[0].method, 'POST');
        }
        for (const call of calls) {
            assert.equal(call.credentials, 'include');
            if (!generations.some(endpoint => call.url.includes(endpoint))) assert.equal(call.method, 'GET');
        }
    });
}
