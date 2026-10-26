"""Offline preflight and opt-in, identity-checked source reacquisition.

    Original source packages are never overwritten. Replacements live in job.
"""
import hashlib
import json
import re
import sqlite3
import http.cookiejar
import shutil
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from bs4 import BeautifulSoup

from semantic_gate import digest, read_json
from native_oauth.chapter_integrity import validate_source, validate_source_archive, source_content_hash
from native_oauth.source_adapters import (fetch_czbooks, extract_ixdzs8_paragraphs, normalize_paragraphs)
from native_oauth.title_selection import chapter_number
from native_oauth.workflow_io import atomic_json

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_path(book,job,chapter):
    replacement=Path(job)/'effective_sources'/f'source_chapter_{chapter:04d}.json'
    if replacement.exists():return replacement
    approved_manifest=Path(book)/'approved/resilient_manifest.json'
    if approved_manifest.exists():
        from native_oauth.resilient_publication import manifest,contained
        value=manifest(book);entry=value['chapters'].get(str(chapter))
        if entry:
            record=value['batches'][entry['batch']];proof=read_json(contained(book,record['evidence']))
            if digest(proof)!=record['evidence_hash']:raise ValueError('Approved source evidence changed')
            item=next(r for r in proof['package']['chapters'] if r['source_packet']['chapter']==chapter)
            path=Path(item['source_packet']['source_file'])
            if read_json(path)['package_hash']!=entry['source_hash']:raise ValueError('Approved source revision changed')
            return path
    return Path(book)/'sources'/replacement.name


def import_replacements(book,job,directory):
    """Import verified revisions by identity and old-source hash, never rehash old data."""
    book,job,directory=Path(book).resolve(),Path(job).resolve(),Path(directory).resolve()
    lore=read_json(book/'lore.json') if (book/'lore.json').exists() else {}
    expected_id=lore.get('book_id',book.name.removeprefix('book_'));imported=[]
    for path in sorted(directory.glob('source_chapter_*.json')):
        source=read_json(path);validate_source(source);validate_source_archive(source)
        original=book/'sources'/path.name;lineage=source.get('recovery_lineage',{})
        if (source['book_id']!=expected_id or source['chapter']!=int(path.stem.rsplit('_',1)[1])
                or not original.exists() or lineage.get('original_sha256')!=sha(original)
                or lineage.get('previous_package_hash')!=read_json(original)['package_hash']):
            raise ValueError('Replacement does not match the exact original book/chapter revision')
        from native_oauth.resilient_publication import manifest
        entry=manifest(book)['chapters'].get(str(source['chapter']))
        if entry and entry['source_hash']!=source['package_hash']:
            raise ValueError('Cannot replace an approved source in place; use an explicit revision campaign')
        target=job/'effective_sources'/path.name
        if target.exists() and target.read_bytes()!=path.read_bytes():raise ValueError('Effective source already differs; preserve and resolve its history')
        target.parent.mkdir(parents=True,exist_ok=True)
        if target!=path:shutil.copy2(path,target)
        imported.append(source['chapter'])
    return imported


def check_one(book,job,chapter):
    path=source_path(book,job,chapter)
    try:
        value=read_json(path);validate_source(value);validate_source_archive(value)
        if value['chapter']!=chapter:raise ValueError('Source chapter identity mismatch')
        lore=read_json(Path(book)/'lore.json') if (Path(book)/'lore.json').exists() else {}
        if value['book_id']!=lore.get('book_id',Path(book).name.removeprefix('book_')):
            raise ValueError('Source book identity mismatch')
        from native_oauth.book_publication import title_ids
        if not title_ids(value):
            from native_oauth.title_selection import metadata_title_source
            metadata_title_source(value)
        return {'chapter':chapter,'status':'SOURCE_READY','source_file':str(path.resolve()),'source_hash':value['package_hash']}
    except Exception as error:
        return {'chapter':chapter,'status':'WAITING_SOURCE','source_file':str(path.resolve()),'reason':str(error),
            'action':'REACQUIRE_FROM_TOC_OR_VERIFIED_ALTERNATE','replacement_file':str((Path(job)/'effective_sources'/path.name).resolve())}


def alternate_root(book):
    """Derive the site book identity from an existing archived, valid source."""
    for path in sorted((Path(book)/'sources').glob('source_chapter_*.json')):
        source=read_json(path);url=urllib.parse.urlsplit(source.get('source_ref',''))
        if url.hostname=='ixdzs8.com' and re.fullmatch(r'/read/\d+/p\d+\.html',url.path):
            try:validate_source(source);validate_source_archive(source)
            except Exception:continue
            return url.path.rsplit('/',1)[0]+'/'
    return None


def fetch_alternate(url):
    """Follow the site's own bounded same-origin browser redirect, not arbitrary JS.

    The server supplies a signed token and a normal location.pathname redirect.
    No token is forged, no CAPTCHA/login is solved, no foreign origin is allowed.
    """
    origin=urllib.parse.urlsplit(url)
    if origin.scheme!='https' or origin.hostname!='ixdzs8.com' or origin.query:
        raise ValueError('Unsupported alternate origin')
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    current=url
    for _ in range(3):
        request=urllib.request.Request(current,headers={'User-Agent':'Mozilla/5.0'})
        with opener.open(request,timeout=30) as response:
            actual=urllib.parse.urlsplit(response.geturl())
            if actual.scheme!=origin.scheme or actual.netloc!=origin.netloc or actual.path!=origin.path:
                raise ValueError('Alternate source redirected away from verified book/chapter')
            raw=response.read()
        soup=BeautifulSoup(raw,'html.parser')
        if soup.select_one('h1.page-d-name'):return raw
        text=raw.decode('utf8',errors='strict')
        token=re.search(r'\blet\s+token\s*=\s*"([A-Za-z0-9+/=_-]{1,1024})"',text)
        if (not token or not soup.title or soup.title.get_text(strip=True)!='正在验证浏览器'
                or 'location.pathname + "?challenge=" + encodeURIComponent(token)' not in text):
            raise ValueError('Alternate returned no chapter; verify browser/archive before translation')
        current=url+'?'+urllib.parse.urlencode({'challenge':token[1]})
    raise ValueError('Browser validation did not complete; open verified source normally and import its raw archive')


def reacquire(book,job,chapter,alt_root=None):
    """Network only when explicitly enabled in Antigravity; no challenge bypass."""
    book,job=Path(book),Path(job);original=book/'sources'/f'source_chapter_{chapter:04d}.json'
    old=read_json(original) if original.exists() else {}
    toc=read_json(book/'toc.json');item=toc[chapter-1];lore=read_json(book/'lore.json') if (book/'lore.json').exists() else {}
    book_id=old.get('book_id',book.name.removeprefix('book_'));errors=[]
    urls=[]
    href=item.get('href','')
    if urllib.parse.urlsplit(href).hostname=='czbooks.net':urls.append(('czbooks',href))
    if alt_root:urls.append(('ixdzs8',f'https://ixdzs8.com{alt_root}p{chapter}.html'))
    for site,url in urls:
        try:
            if site=='czbooks':
                slug=urllib.parse.urlsplit(url).path.split('/')[2]
                paras,raw=fetch_czbooks(url,book_slug=slug,expected_title=item['title'],
                    expected_book_titles=tuple(lore[k] for k in ('book_title','book_title_traditional') if lore.get(k)))
                soup=BeautifulSoup(raw,'html.parser');node=soup.select_one('.name')
                title=re.sub(r'^《[^》]+》','',node.get_text(strip=True)) if node else item['title']
                if chapter_number(title)!=chapter:raise ValueError('Reacquired CZBooks chapter number mismatch')
            else:
                raw=fetch_alternate(url)
                soup=BeautifulSoup(raw,'html.parser');node=soup.select_one('h1.page-d-name')
                if not node or chapter_number(node.get_text(strip=True))!=chapter:raise ValueError('Alternate source chapter heading mismatch')
                canonical=soup.select_one('link[rel="canonical"]')
                if canonical and urllib.parse.urljoin(url,canonical.get('href',''))!=url:raise ValueError('Alternate canonical chapter mismatch')
                title=node.get_text(strip=True);paras=extract_ixdzs8_paragraphs(raw)
            # These particular old packages are known obfuscated fallbacks.
            # Do not globally strip Hangul: other chapters contain real dialogue.
            if str(old.get('chapter_key','')).startswith('timotxt') and any(re.search(r'[\uac00-\ud7af]',p) for p in paras):
                raise ValueError('Recovered known-obfuscated chapter still contains Hangul; needs source verification')
            rows,mapping=normalize_paragraphs(paras,chapter);raw_hash=hashlib.sha256(raw).hexdigest()
            archive=ROOT/'source_archive'/('book_'+book_id)/f'chap_{chapter:04d}_{raw_hash}.html'
            archive.parent.mkdir(parents=True,exist_ok=True)
            if archive.exists() and sha(archive)!=raw_hash:raise ValueError('Archive hash collision')
            if not archive.exists():archive.write_bytes(raw)
            source={'version':'bns-source-v2','book_id':book_id,'chapter':chapter,'title':title,'source_ref':url,
                'chapter_key':f'{site}_recovered_{chapter}','segments':rows,'paragraph_count':len(rows),
                'normalization':mapping,'raw_archive':archive.name,'raw_sha256':raw_hash,
                'recovery_lineage':{'original_file':str(original.resolve()),'original_sha256':sha(original) if original.exists() else None,
                    'previous_package_hash':old.get('package_hash'),'method':'identity_checked_refetch_no_original_overwrite'}}
            source['content_hash']=source_content_hash(source);source['package_hash']=digest(source)
            validate_source(source);validate_source_archive(source)
            target=job/'effective_sources'/f'source_chapter_{chapter:04d}.json'
            if target.exists() and read_json(target)!=source:
                atomic_json(job/'source_revision_history'/f"{chapter:04d}_{digest(read_json(target))}.json",read_json(target))
            atomic_json(target,source)
            atomic_json(job/'source_recovery'/f'{chapter:04d}.json',{'status':'RECOVERED','source_file':str(target.resolve()),'source_hash':source['package_hash'],'attempts':errors})
            return
        except Exception as error:errors.append({'site':site,'url':url,'reason':str(error)})
    atomic_json(job/'source_recovery'/f'{chapter:04d}.json',{'status':'WAITING_SOURCE','attempts':errors,
        'action':'RETRY_VERIFIED_REFETCH_OR_PROVIDE_VERIFIABLE_REPLACEMENT','original_preserved':True})


def preflight(book,job,through,*,repair_sources=False,workers=4,progress_callback=None):
    book,job=Path(book).resolve(),Path(job).resolve();job.mkdir(parents=True,exist_ok=True)
    if type(through) is not int or through<1:raise ValueError('Preflight needs a positive chapter range')
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows=[]
        for count,row in enumerate(pool.map(lambda ch:check_one(book,job,ch),range(1,through+1)),1):
            rows.append(row)
            if progress_callback and (count%100==0 or count==through):progress_callback(count,through)
    bad=[r for r in rows if r['status']!='SOURCE_READY']
    if repair_sources and bad:
        alt=alternate_root(book)
        for row in bad:
            try:reacquire(book,job,row['chapter'],alt)
            except Exception as error:
                atomic_json(job/'source_recovery'/f"{row['chapter']:04d}.json",{'status':'WAITING_SOURCE',
                    'reason':str(error),'action':'REPAIR_TOC_OR_SUPPLY_VERIFIED_SOURCE_REPLACEMENT'})
        rows=[check_one(book,job,ch) for ch in range(1,through+1)]
    # Source index is a retrieval cache, never an approval or substitute for hash validation.
    db=sqlite3.connect(job/'source_index.sqlite')
    try:
        db.execute('CREATE TABLE IF NOT EXISTS paragraphs(chapter INTEGER,id TEXT PRIMARY KEY,source TEXT,source_hash TEXT)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_paragraphs_chapter ON paragraphs(chapter,id)')
        db.execute('DELETE FROM paragraphs')
        for row in rows:
            if row['status']=='SOURCE_READY':
                source=read_json(row['source_file'])
                db.executemany('INSERT INTO paragraphs VALUES(?,?,?,?)',[(source['chapter'],s['id'],s['source'],source['package_hash']) for s in source['segments']])
        db.commit()
    finally:db.close()
    result={'through_chapter':through,'sources':rows,'ready':sum(r['status']=='SOURCE_READY' for r in rows),
        'pending':[r for r in rows if r['status']!='SOURCE_READY'],'status':'READY' if all(r['status']=='SOURCE_READY' for r in rows) else 'RECOVERY_REQUIRED'}
    atomic_json(job/'source_preflight.json',result)
    return result


def source_context(job,chapter,queries=(),max_chars=6000):
    """Only earlier literal Chinese; source hash and IDs are checked outside SQLite."""
    db=sqlite3.connect(Path(job)/'source_index.sqlite')
    try:
        recent=list(db.execute('SELECT chapter,id,source,source_hash FROM paragraphs WHERE chapter<? AND chapter>=? ORDER BY chapter DESC,id ASC',(chapter,max(1,chapter-2))))
        rows=[]
        for query in queries:
            if not isinstance(query,str) or not query.strip() or len(query)>24:continue
            for order in ('ASC','DESC'):
                rows+=list(db.execute(f'SELECT chapter,id,source,source_hash FROM paragraphs WHERE chapter<? AND instr(source,?)>0 ORDER BY chapter {order},id {order} LIMIT 2',(chapter,query)))
        rows+=recent
    finally:db.close()
    result=[];seen=set();used=0;verified={}
    report=read_json(Path(job)/'source_preflight.json');paths={r['chapter']:r['source_file'] for r in report['sources'] if r['status']=='SOURCE_READY'}
    for ch,sid,raw,expected in rows:
        if sid in seen or used+len(raw)>max_chars:continue
        if ch not in verified:
            source=read_json(paths[ch]);validate_source(source);validate_source_archive(source)
            verified[ch]=(source,{r['id']:r['source'] for r in source['segments']})
        source,by_id=verified[ch]
        if source['package_hash']!=expected or by_id.get(sid)!=raw:
            raise ValueError('Source changed: retrieval index no longer matches literal source')
        result.append({'chapter':ch,'id':sid,'source':raw,'source_hash':expected,'source_file':paths[ch]});seen.add(sid);used+=len(raw)
    return sorted(result,key=lambda row:(row['chapter'],row['id']))
