"""Source-owned title selection when site metadata differs from article content."""
import hashlib
import re
import threading
import urllib.parse
from collections import OrderedDict
from pathlib import Path
from bs4 import BeautifulSoup
from semantic_gate import read_json,digest
from native_oauth.source_adapters import clean_title

VERSION='article-title-dom-1'
_TITLE_SOURCE_CACHE=OrderedDict()
_TITLE_SOURCE_LOCK=threading.RLock()


def metadata_title_source(source):
    """Verify a separate title against archived metadata; never insert body IDs."""
    if source.get('version') != 'bns-source-v2':
        raise ValueError('Separate title requires an archived v2 source')
    from native_oauth.chapter_integrity import validate_source_archive
    validate_source_archive(source)
    archive = Path(__file__).resolve().parents[1]/'source_archive'/('book_'+source['book_id'])/source['raw_archive']
    raw=archive.read_bytes();raw_hash=hashlib.sha256(raw).hexdigest()
    if raw_hash!=source['raw_sha256']:raise ValueError('Title archive changed during validation')
    key=(digest(source),str(archive),raw_hash,id(BeautifulSoup))
    with _TITLE_SOURCE_LOCK:
        if key in _TITLE_SOURCE_CACHE:
            _TITLE_SOURCE_CACHE.move_to_end(key)
            return dict(_TITLE_SOURCE_CACHE[key])
    soup = BeautifulSoup(raw, 'html.parser')
    selector = 'h1.page-d-name' if 'ixdzs8' in source.get('source_ref','') else '.name'
    node = soup.select_one(selector)
    title = source.get('title', '')
    declared=chapter_number(title)
    parsed=urllib.parse.urlsplit(source['source_ref'])
    toc_identity=(parsed.scheme=='https' and parsed.hostname=='czbooks.net' and not parsed.username and not parsed.password
                  and source.get('toc_index')==source['chapter']
                  and urllib.parse.parse_qs(parsed.query).get('chapterNumber')==[str(source['chapter']-1)])
    canonical=soup.select_one('link[rel="canonical"],meta[property="og:url"]')
    if canonical:
        canonical_url=urllib.parse.urlsplit(urllib.parse.urljoin(source['source_ref'],canonical.get('href') or canonical.get('content') or ''))
        toc_identity=toc_identity and (canonical_url.scheme,canonical_url.hostname,canonical_url.path)==(parsed.scheme,parsed.hostname,parsed.path)
    if (node is None or not title or declared is None or (declared != source['chapter'] and not toc_identity)
            or clean_title(node.get_text(strip=True)) != clean_title(title)):
        raise ValueError('Separate chapter title does not match archived metadata')
    result={'id':f"c{source['chapter']:04d}title", 'source':title,
            'origin':f'archived {selector} metadata; absent from body',
            'archive':str(archive), 'archive_sha256':raw_hash}
    if declared!=source['chapter']:
        result.update(catalog_chapter=source['chapter'],declared_chapter=declared,
            numbering_note='Archived printed number differs from the verified zero-based TOC URL. '
                           'Preserve source metadata and IDs; render chapter numbering by catalog ordinal. '
                           'This editorial heading number mapping must not change body numbers or story meaning.')
    with _TITLE_SOURCE_LOCK:
        _TITLE_SOURCE_CACHE[key]=result
        while len(_TITLE_SOURCE_CACHE)>4096:_TITLE_SOURCE_CACHE.popitem(last=False)
    return dict(result)


def chapter_number(text):
    text=re.sub(r'^《[^》]+》','',text.strip())
    text=re.sub(r'^\d+\s*[.．]\s*','',text)
    match=re.match(r'^第\s*(\d+)\s*章',text)
    return int(match[1]) if match else None


def validate_selection(source, selection):
    if not isinstance(selection,dict) or not isinstance(selection.get('metadata_title'),str):
        raise ValueError('Invalid title selection schema')
    rows=source['segments'][:2]
    if (len(rows)!=2 or selection.get('version')!=VERSION
            or selection.get('source_hash')!=source['package_hash']
            or selection.get('source_ref')!=source['source_ref']
            or selection.get('title_segment_ids')!=[r['id'] for r in rows]
            or selection.get('primary_title_id')!=rows[1]['id']
            or clean_title(selection.get('metadata_title',''))!=clean_title(rows[0]['source'])
            or selection.get('article_heading')!=rows[1]['source']
            or any(chapter_number(row['source'])!=source['chapter'] for row in rows)):
        raise ValueError('Title selection does not match the two source-owned chapter headings')


def load_selection(source, snapshot_file):
    path=Path(snapshot_file).resolve();snapshot=read_json(path)
    if (not isinstance(snapshot,dict) or len(source['segments'])<2
            or any(not isinstance(snapshot.get(k),str) or not snapshot[k].strip()
                   for k in ('url','metadata_title','article_heading','article_heading_html'))
            or snapshot.get('method')!='read_only_browser_dom'
            or snapshot.get('metadata_selector')!='.name' or snapshot.get('article_selector')!='.content'
            or snapshot.get('chapter')!=source['chapter']
            or BeautifulSoup(snapshot.get('article_heading_html',''),'html.parser').get_text().strip()!=snapshot.get('article_heading')):
        raise ValueError('Invalid rendered article heading snapshot')
    selection={'version':VERSION,'source_hash':source['package_hash'],'source_ref':snapshot['url'],
        'metadata_title':snapshot['metadata_title'],'article_heading':snapshot['article_heading'],
        'title_segment_ids':[r['id'] for r in source['segments'][:2]],
        'primary_title_id':source['segments'][1]['id'],
        'snapshot_file':str(path),'snapshot_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    validate_selection(source,selection)
    return selection


def require_reviewed_selection(source, aligned, package):
    selected=aligned.get('render_title_ownership')
    if selected!=package.get('render_title_ownership'):
        raise ValueError('Rendered title ownership was not part of the independently reviewed package')
    if selected is None:
        return
    validate_selection(source,selected)
    if (load_selection(source,selected['snapshot_file'])!=selected
            or package.get('native_bound_files',{}).get(selected['snapshot_file'])!=selected['snapshot_sha256']):
        raise ValueError('Title ownership snapshot changed or was not bound before native review')
