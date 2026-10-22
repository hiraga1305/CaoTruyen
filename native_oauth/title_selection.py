"""Source-owned title selection when site metadata differs from article content."""
import hashlib
import re
from pathlib import Path
from bs4 import BeautifulSoup
from semantic_gate import read_json
from native_oauth.source_adapters import clean_title

VERSION='article-title-dom-1'


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
