"""Conservative source extraction. Never silently discard undecodable bytes."""
import re
import hashlib
import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

BASE_URL = 'https://www.piaotia.com/html/16/16014/'


def extract_paragraphs(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content')
    if content is None:
        # Live Piaotia snapshot (2026-10-13) has no #content. Its body is
        # unwrapped between navigation blocks, after ad tables. Bound that exact
        # template rather than accepting the complete page as chapter text.
        top = re.search(r'<div\s+class=["\']toplink["\'][^>]*>.*?</div>', html, re.S | re.I)
        bottom = re.search(r'<div\s+class=["\']bottomlink["\'][^>]*>', html, re.I)
        if not top or not bottom or bottom.start() <= top.end():
            raise ValueError('Unknown source template; requires manual inspection')
        region = html[top.end():bottom.start()]
        start = re.search(r'(?:&nbsp;){4}', region)
        if not start:
            raise ValueError('Chapter start marker missing')
        content = BeautifulSoup('<div id="content">' + region[start.start():] + '</div>', 'html.parser').select_one('#content')
    for tag in content.select('script, style'):
        tag.decompose()
    for br in content.find_all('br'):
        br.replace_with('\n')
    # Inline links retain their text. Do not remove narrative containing site markers.
    for tag in content.find_all(['p', 'div']):
        tag.insert_before('\n')
        tag.insert_after('\n')
    paragraphs = [p.strip() for p in content.get_text().replace('\xa0', ' ').splitlines() if p.strip()]
    if not paragraphs or not any(re.search(r'[\u3400-\u9fff]', p) for p in paragraphs):
        raise ValueError('Empty or non-Chinese source')
    return paragraphs


def fetch_chapter_raw(href, max_retries=1):
    if not re.fullmatch(r'\d+\.html', href):
        raise ValueError('Invalid chapter href')
    req = urllib.request.Request(BASE_URL + href, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
        encoding = response.headers.get_content_charset() or 'gb18030'
        final_url = response.geturl()
    if final_url != BASE_URL + href:
        raise ValueError('Unexpected source redirect')
    html = data.decode(encoding, errors='strict')
    for field, expected in (('article_id', '16014'), ('chapter_id', href.removesuffix('.html'))):
        actual = re.search(r'var\s+' + field + r'\s*=\s*["\'](\d+)["\']', html)
        if not actual or actual[1] != expected:
            raise ValueError('Returned page book/chapter identity mismatch')
    paragraphs = extract_paragraphs(html)
    archive = Path(__file__).resolve().parent / 'source_archive'
    archive.mkdir(exist_ok=True)
    stamp = hashlib.sha256(data).hexdigest()
    name = href.removesuffix('.html') + '_' + stamp[:16]
    (archive / (name + '.html')).write_bytes(data)
    (archive / (name + '.json')).write_text(json.dumps({
        'url': final_url, 'fetched_at_utc': datetime.now(timezone.utc).isoformat(),
        'encoding': encoding, 'raw_sha256': stamp, 'paragraphs': len(paragraphs),
        'parser_version': 'piaotia-template-20261013', 'completeness': 'not independently established'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return paragraphs


def terminology_hint(text, glossary):
    """Hints only; no grammar rewrite or hybrid strings passed off as an AST."""
    return '\n'.join(f'{key}: {value}' for key, value in glossary.items() if key in text)
