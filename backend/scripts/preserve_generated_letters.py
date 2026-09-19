#!/usr/bin/env python3
"""Authenticated read-only PDF export or comparison with a saved manifest.

Export: --cookie-file /private/session.cookies.txt --output /private/new-directory
Verify: --cookie-file /private/session.cookies.txt --verify /private/manifest.json
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cookie-file', required=True, type=Path)
    parser.add_argument('--api-url', default='https://api.mrrc.online')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if not args.api_url.startswith('https://'):
        parser.error('Use an HTTPS API URL')
    os.umask(0o077)
    jar = http.cookiejar.MozillaCookieJar(str(args.cookie_file))
    jar.load(ignore_discard=True, ignore_expires=True)
    for cookie in jar:
        # Netscape/curl uses zero for session cookies; Python treats it as expired.
        if cookie.expires == 0:
            cookie.expires = None
            cookie.discard = True
    session = requests.Session()
    session.cookies = jar

    def get(path):
        response = session.get(args.api_url.rstrip('/') + path, timeout=30, allow_redirects=False)
        if response.status_code != 200:
            raise ValueError(f'HTTP {response.status_code}; preservation stopped')
        return response

    def names():
        listing = get('/api/letters/pdfs').json()
        result = [item['filename'] for item in listing]
        if len(result) != len(set(result)):
            raise ValueError('Duplicate filenames in inventory')
        for name in result:
            if (not name.endswith('.pdf') or '/' in name or '\\' in name or '..' in name
                    or any(ord(c) < 32 or ord(c) == 127 for c in name)):
                raise ValueError('Unsafe filename in inventory')
        return sorted(result)

    get('/api/auth/me')
    inventory = names()
    expected = None
    if args.verify:
        manifest = json.loads(args.verify.read_text())
        expected = {item['filename']: item for item in manifest['files']}
        if len(expected) != len(manifest['files']) or sorted(expected) != inventory:
            raise ValueError('Remote inventory differs from manifest')
    else:
        args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    records = []
    for name in inventory:
        path = '/api/letters/pdfs/' + quote(name, safe='')
        data = get(path).content
        if not data.startswith(b'%PDF-'):
            raise ValueError('Non-PDF response; preservation stopped')
        record = dict(filename=name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        if expected is not None:
            if record != expected[name]:
                raise ValueError('Remote file differs from manifest')
            local = args.verify.parent / name
        else:
            local = args.output / name
            with local.open('xb') as output:
                output.write(data)
        if local.read_bytes() != data:
            raise ValueError('Saved file differs from remote PDF')
        if hashlib.sha256(get(path).content).hexdigest() != record['sha256']:
            raise ValueError('Remote file changed during verification')
        records.append(record)
    if names() != inventory:
        raise ValueError('Remote inventory changed during verification')
    if expected is None:
        manifest = dict(source=args.api_url, verified_at=datetime.now(timezone.utc).isoformat(), files=records)
        (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Verified {len(records)} PDFs; all sizes and SHA-256 checksums match.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Exceptions can contain URLs, headers, or payloads; do not print them.
        raise SystemExit('Preservation/verification failed. Do not deploy; keep any partial export for investigation.')
