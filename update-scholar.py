#!/usr/bin/env python3
"""
Fetch latest Google Scholar stats and save to scholar.json.
Runs manually or via GitHub Actions (see .github/workflows/update-scholar.yml).

Exit codes:
  0 — success (or Google temporarily unreachable; kept existing JSON)
  1 — fatal error (malformed local scholar.json, disk error, etc.)

This script is *tolerant* to transient failures: if Google returns a
CAPTCHA / rate-limit page, we keep the previous scholar.json untouched
and exit 0 so the GitHub Action doesn't falsely report failure.
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.request

USER = '-XWPfk4AAAAJ'
URL = f'https://scholar.google.com/citations?user={USER}&hl=en'
OUT = 'scholar.json'


def fetch_scholar():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(URL, headers={
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0 Safari/537.36'
        ),
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml',
    })

    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        html = r.read().decode('utf-8', errors='ignore')

    # Detect CAPTCHA / unusual traffic block pages
    low = html.lower()
    if 'unusual traffic' in low or 'captcha' in low or 'sorry' in low[:2000]:
        raise RuntimeError('Google Scholar is rate-limiting this request (CAPTCHA page).')

    # Six number cells in the stats table:
    # citations(all), citations(since X), h(all), h(since X), i10(all), i10(since X)
    nums = re.findall(r'gsc_rsb_std">(\d+)', html)
    if len(nums) < 6:
        raise RuntimeError(
            f'Could not parse stats table. Found {len(nums)} numbers '
            f'(expected 6). HTML length: {len(html)}'
        )

    # Count publication rows
    paper_count = len(re.findall(r'class="gsc_a_tr"', html))

    # Extract display name
    name_m = re.search(r'<div id="gsc_prf_in">([^<]+)</div>', html)
    name = name_m.group(1) if name_m else 'Zongying Lin'

    return {
        'user': USER,
        'name': name,
        'paper_count': paper_count,
        'citations_all': int(nums[0]),
        'citations_recent': int(nums[1]),
        'h_index_all': int(nums[2]),
        'h_index_recent': int(nums[3]),
        'i10_index_all': int(nums[4]),
        'i10_index_recent': int(nums[5]),
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'updated_at_local': time.strftime('%Y-%m-%d %H:%M UTC'),
        'source': URL,
    }


def main():
    try:
        data = fetch_scholar()
    except Exception as e:
        print(f'[WARN] Scholar fetch failed: {e}', file=sys.stderr)
        # Graceful exit — keep existing scholar.json intact.
        # GitHub Action will skip the commit step.
        if os.path.exists(OUT):
            print(f'[INFO] Keeping existing {OUT} unchanged.')
            return 0
        # No existing file — that's a real problem.
        print(f'[ERROR] No existing {OUT} to fall back to.', file=sys.stderr)
        return 1

    try:
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    except OSError as e:
        print(f'[ERROR] Could not write {OUT}: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
