"""Strict CZBooks source adapter with explicit title normalization and raw mapping."""
import hashlib
import re
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup

PARSER_VERSION="czbooks-content-2"
TITLE=re.compile(r"^(?:\d+\s*[.．]\s*)?(第\s*\d+\s*章.*)$")
FOOTERS={"(本章完)","（本章完）","【本章完】"}


def identity_url(value, book_slug):
    parsed=urllib.parse.urlsplit(value)
    if parsed.scheme!="https" or parsed.hostname!="czbooks.net" or parsed.username or parsed.password:
        raise ValueError("Unsupported source origin")
    if not re.fullmatch(r"/n/"+re.escape(book_slug)+r"/[A-Za-z0-9_-]+/?",parsed.path):
        raise ValueError("Source URL book/chapter identity mismatch")
    return parsed.path.rstrip("/")


def extract_paragraphs(html):
    soup=BeautifulSoup(html,"html.parser")
    content=soup.select_one(".content")
    if content is None: raise ValueError("Unknown CZBooks content template")
    for tag in content.select("script,style"): tag.decompose()
    for br in content.find_all("br"): br.replace_with("\n")
    for tag in content.find_all(["p","div"]):
        tag.insert_before("\n"); tag.insert_after("\n")
    paragraphs=[p.strip() for p in content.get_text().replace("\xa0"," ").splitlines() if p.strip()]
    if not paragraphs or not any(re.search(r"[\u3400-\u9fff]",p) for p in paragraphs):
        raise ValueError("Empty/non-Chinese source")
    return paragraphs


def clean_title(text):
    text = re.sub(r'^《[^》]+》', '', text.strip())
    text = re.sub(r'^\d+\s*[.．]\s*', '', text)
    return re.sub(r'[\s.．。·・]', '', text)


def fetch_czbooks(href, *, book_slug="s6p7bb", expected_title=None, headers=None, expected_book_titles=()):
    expected_path=identity_url(href,book_slug)
    request=urllib.request.Request(href,headers=headers or {"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(request,timeout=25) as response:
        if identity_url(response.geturl(),book_slug)!=expected_path:
            raise ValueError("Unexpected chapter redirect")
        raw=response.read()
        html=raw.decode("utf-8",errors="strict")
    soup=BeautifulSoup(html,"html.parser")
    if expected_book_titles:
        headings = [n.get_text(strip=True) for n in soup.select('h1,.chapter-title,.name')]
        declared = [name for heading in headings for name in re.findall(r'《([^》]+)》', heading)]
        if declared and any(name not in expected_book_titles for name in declared):
            raise ValueError('Declared book title mismatch')
    canonical=soup.select_one('link[rel="canonical"], meta[property="og:url"]')
    if canonical:
        canonical_url=canonical.get("href") or canonical.get("content")
        if canonical_url and identity_url(canonical_url,book_slug)!=expected_path:
            raise ValueError("Canonical page identity mismatch")
    paragraphs=extract_paragraphs(html)
    if expected_title:
        expected=clean_title(expected_title)
        candidates=paragraphs[:2]+[n.get_text(strip=True) for n in soup.select("h1,.chapter-title,.name")]
        if not any(clean_title(c)==expected or (len(expected)>=8 and clean_title(c).startswith(expected)) for c in candidates):
            raise ValueError("Page title does not match TOC; inspect source before normalization")
    return paragraphs,raw


def normalize_paragraphs(paragraphs,chapter):
    """Keep body text verbatim; consolidate only equivalent initial title rows."""
    if not paragraphs: raise ValueError("Empty source")
    rows=[]; mapping=[]; excluded=[]
    for index,text in enumerate(paragraphs,1):
        if index==len(paragraphs) and text in FOOTERS:
            excluded.append({"raw_index":index,"reason":"exact_terminal_boilerplate","text":text})
            continue
        role="title" if index<=2 and TITLE.match(text) else "body"
        if role=="title" and rows and rows[0].get("role")=="title" and clean_title(text)==clean_title(rows[0]["source"]):
            mapping[0]["raw_indices"].append(index)
            excluded.append({"raw_index":index,"reason":"duplicate_initial_title","kept_segment":rows[0]["id"]})
            continue
        sid=f"c{chapter:04d}p{len(rows)+1:04d}"
        rows.append({"id":sid,"source":text,"role":role})
        mapping.append({"id":sid,"raw_indices":[index]})
    if not rows: raise ValueError("No source after bounded normalization")
    return rows,{"parser_version":PARSER_VERSION,"raw_paragraph_count":len(paragraphs),
                 "segment_map":mapping,"excluded":excluded}


def extract_ixdzs8_paragraphs(html_bytes_or_str):
    if isinstance(html_bytes_or_str, bytes):
        html = html_bytes_or_str.decode('utf-8', errors='strict')
    else:
        html = html_bytes_or_str
    soup = BeautifulSoup(html, 'html.parser')
    page_content = (
        soup.find('article', class_='page-content')
        or soup.find('div', class_='page-content')
        or soup.find('div', class_='read-content')
        or soup.find('article')
    )
    if not page_content:
        divs = soup.find_all('div')
        page_content = max(divs, key=lambda d: len(d.find_all('p'))) if divs else soup.body
    p_tags = page_content.find_all('p')
    if p_tags:
        paras = [p.get_text(strip=True).replace('\xa0', ' ') for p in p_tags if p.get_text(strip=True)]
    else:
        for tag in page_content.select('script, style'):
            tag.decompose()
        for br in page_content.find_all('br'):
            br.replace_with('\n')
        paras = [p.strip() for p in page_content.get_text().replace('\xa0', ' ').splitlines() if p.strip()]
    cleaned = []
    for p in paras:
        if p.startswith('请记住本书首发') or p.startswith('最新网址') or p in ('上一章', '下一章', '目 录'):
            continue
        cleaned.append(p)
    if len(cleaned) < 5 or not any(re.search(r'[\u3400-\u9fff]', p) for p in cleaned):
        raise ValueError('Extracted paragraphs too few or non-Chinese')
    return cleaned
