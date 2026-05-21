#!/usr/bin/env python3
"""
Fetch latest Google Scholar stats via SerpAPI and save to scholar.json.

Runs manually or via GitHub Actions (see .github/workflows/update-scholar.yml).

Requirements:
  * Environment variable SERPAPI_KEY must be set (free tier: 100 searches/month).
    Get a key at https://serpapi.com/

Exit codes:
  0 — success (or transient failure with existing JSON kept untouched)
  1 — fatal error (no SERPAPI_KEY without fallback, malformed JSON, disk error)

Behavior:
  * If SerpAPI returns an error or is unreachable AND a previous scholar.json
    exists, we keep it and exit 0 so the GitHub Action doesn't false-fail.
"""
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

USER = '-XWPfk4AAAAJ'
OUT = 'scholar.json'
SERPAPI_ENDPOINT = 'https://serpapi.com/search.json'


def fetch_scholar_via_serpapi(api_key: str) -> dict:
    """Fetch author profile + stats from SerpAPI google_scholar_author engine."""
    ctx = ssl.create_default_context()

    params = {
        'engine': 'google_scholar_author',
        'author_id': USER,
        'hl': 'en',
        'api_key': api_key,
    }
    url = f'{SERPAPI_ENDPOINT}?{urllib.parse.urlencode(params)}'

    req = urllib.request.Request(url, headers={
        'User-Agent': 'scholar-updater/1.0',
        'Accept': 'application/json',
    })

    with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
        raw = r.read().decode('utf-8', errors='ignore')

    data = json.loads(raw)

    if 'error' in data:
        raise RuntimeError(f"SerpAPI error: {data['error']}")

    author = data.get('author', {}) or {}
    cited_by = data.get('cited_by', {}) or {}
    articles = data.get('articles', []) or []

    # cited_by.table is a list of dicts like:
    # [{"citations": {"all": 123, "since_2020": 100}},
    #  {"h_index":  {"all":  7,  "since_2020":   6}},
    #  {"i10_index":{"all":  5,  "since_2020":   4}}]
    table = cited_by.get('table', []) or []

    def pick(metric_key: str, span: str) -> int:
        for row in table:
            if metric_key in row:
                val = row[metric_key].get(span)
                if val is not None:
                    return int(val)
        return 0

    citations_all    = pick('citations', 'all')
    citations_recent = next(
        (int(row['citations'][k])
         for row in table if 'citations' in row
         for k in row['citations'] if k.startswith('since_')),
        0,
    )
    h_index_all    = pick('h_index', 'all')
    h_index_recent = next(
        (int(row['h_index'][k])
         for row in table if 'h_index' in row
         for k in row['h_index'] if k.startswith('since_')),
        0,
    )
    i10_index_all    = pick('i10_index', 'all')
    i10_index_recent = next(
        (int(row['i10_index'][k])
         for row in table if 'i10_index' in row
         for k in row['i10_index'] if k.startswith('since_')),
        0,
    )

    name = author.get('name') or 'Zongying Lin'
    paper_count = len(articles)

    return {
        'user': USER,
        'name': name,
        'paper_count': paper_count,
        'citations_all': citations_all,
        'citations_recent': citations_recent,
        'h_index_all': h_index_all,
        'h_index_recent': h_index_recent,
        'i10_index_all': i10_index_all,
        'i10_index_recent': i10_index_recent,
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'updated_at_local': time.strftime('%Y-%m-%d %H:%M UTC'),
        'source': f'https://scholar.google.com/citations?user={USER}&hl=en',
        'provider': 'serpapi',
    }


def main() -> int:
    api_key = os.environ.get('SERPAPI_KEY', '').strip()
    if not api_key:
        print('[ERROR] SERPAPI_KEY environment variable is not set.', file=sys.stderr)
        if os.path.exists(OUT):
            print(f'[INFO] Keeping existing {OUT} unchanged.', file=sys.stderr)
            return 0
        return 1

    try:
        data = fetch_scholar_via_serpapi(api_key)
    except Exception as e:
        print(f'[WARN] Scholar fetch failed: {e}', file=sys.stderr)
        if os.path.exists(OUT):
            print(f'[INFO] Keeping existing {OUT} unchanged.', file=sys.stderr)
            return 0
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
