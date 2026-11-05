import test from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';

// Run against the disposable local preview. API responses are synthetic;
// no credentials, account mutations, or external requests are needed.
const base = process.env.CLERK_BROWSER_URL || 'http://localhost:3000';
assert.equal(new URL(base).hostname, 'localhost', 'Browser tests require localhost');
const ordinary = {
    id: 987654, email: 'ordinary@example.com', display_name: 'Ordinary Tester',
    is_admin: false, is_active: true, avatar_path: null, last_login_at: null,
};

for (const colorScheme of ['light', 'dark']) {
    test(`ordinary user denial has readable contrast in ${colorScheme} mode`, async () => {
        const browser = await chromium.launch({
            headless: true,
            ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
                ? {executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE} : {}),
        });
        try {
            const context = await browser.newContext({colorScheme});
            const administrativeRequests = [];
            await context.route('**/*', async route => {
                const url = new URL(route.request().url());
                if (url.hostname !== 'localhost') return route.abort();
                if (url.pathname === '/api/auth/me') {
                    return route.fulfill({json: ordinary, headers: {
                        'Access-Control-Allow-Origin': new URL(base).origin,
                        'Access-Control-Allow-Credentials': 'true',
                    }});
                }
                if (url.pathname.startsWith('/api/users')) administrativeRequests.push(url.pathname);
                if (url.pathname.startsWith('/api/')) return route.abort();
                return route.continue();
            });
            const page = await context.newPage();
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            await page.goto(base + '/dashboard/users');
            const message = page.getByText('Access denied. Administrator access is required.', {exact: true});
            await message.waitFor();
            const contrast = await message.evaluate(element => {
                // Canvas resolves browser-computed CSS colors, including Tailwind's
                // OKLCH values, into sRGB. Use the actual opaque ancestor background.
                const canvas = document.createElement('canvas');
                canvas.width = canvas.height = 1;
                const ctx = canvas.getContext('2d');
                const rgba = color => {
                    ctx.clearRect(0, 0, 1, 1);
                    ctx.fillStyle = color;
                    ctx.fillRect(0, 0, 1, 1);
                    return [...ctx.getImageData(0, 0, 1, 1).data];
                };
                const foreground = rgba(getComputedStyle(element).color);
                let background;
                for (let node = element; node; node = node.parentElement) {
                    const color = rgba(getComputedStyle(node).backgroundColor);
                    if (color[3] === 255) { background = color; break; }
                }
                if (!background || foreground[3] !== 255) throw Error('Expected opaque text and background');
                const luminance = color => color.slice(0, 3).map(value => {
                    const channel = value / 255;
                    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
                }).reduce((total, channel, index) => total + channel * [0.2126, 0.7152, 0.0722][index], 0);
                const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
                return (values[0] + 0.05) / (values[1] + 0.05);
            });
            console.log(`${colorScheme} denial contrast: ${contrast.toFixed(2)}:1`);
            assert.ok(contrast >= 4.5, `Expected at least 4.5:1, got ${contrast}`);
            assert.equal(await page.getByRole('button', {name: 'Add User', exact: true}).count(), 0);
            assert.equal(await page.locator('a[href="/dashboard/users"]').count(), 0);
            assert.equal(await page.getByRole('heading', {name: 'User Management'}).count(), 0);
            assert.deepEqual(administrativeRequests, []);
            assert.deepEqual(errors, []);
        } finally {
            await browser.close();
        }
    });
}
