"""Conservative source extraction. Never silently discard undecodable bytes."""
import re
import urllib.request
from bs4 import BeautifulSoup

BASE_URL = 'https://www.piaotia.com/html/16/16014/'


def extract_paragraphs(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content')
    if content is None:
        raise ValueError('Missing #content; source requires manual inspection')
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
    return extract_paragraphs(data.decode(encoding, errors='strict'))


def terminology_hint(text, glossary):
    """Hints only; no grammar rewrite or hybrid strings passed off as an AST."""
    return '\n'.join(f'{key}: {value}' for key, value in glossary.items() if key in text)
