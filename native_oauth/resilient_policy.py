"""Versioned content checks: deterministic errors versus native review duties."""
import re
import unicodedata
from semantic_gate import mechanical_findings,term_occurrences
from native_oauth.recovery_native import ProtocolFailure

POLICY='resilient-content-2'
REVIEW_POLICY='resilient-review-2'
HAN=re.compile('[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U000323af]')


def normalized(text):
    """Comparison only; never rewrite model output or collapse accents."""
    return ' '.join(unicodedata.normalize('NFC',text).casefold().split())


def contains_name(text,name):
    return re.search(r'(?<!\w)'+re.escape(normalized(name))+r'(?!\w)',normalized(text)) is not None


def visible(text):
    return isinstance(text,str) and any(not ch.isspace() and unicodedata.category(ch) not in ('Cf','Cc','Cs') for ch in text)


def policy_v2(package):
    version=package.get('validation_policy')
    if version not in (None,POLICY):raise ValueError('Source changed: unsupported validation policy')
    return version==POLICY


def quote_claims(package,value):
    claims=value.get('source_script_quotes',[])
    if not isinstance(claims,list):raise ProtocolFailure('source_script_quotes must be an array')
    source={row['id']:row['source'] for row in package['segments']}
    if package.get('metadata_title_source'):
        source[package['metadata_title_source']['id']]=package['metadata_title_source']['source']
    target={row['id']:row.get('text') for row in value['segments']}
    if package.get('metadata_title_source'):target[package['metadata_title_source']['id']]=value.get('title_vi')
    seen=set()
    for claim in claims:
        if (not isinstance(claim,dict) or set(claim)!= {'id','quote','reason'}
                or not isinstance(claim.get('id'),str) or claim['id'] not in source
                or not isinstance(claim.get('quote'),str) or not 1<=len(claim['quote'])<=32
                or not HAN.search(claim['quote']) or claim['quote'] not in source[claim['id']]
                or not isinstance(target.get(claim['id']),str) or claim['quote'] not in target[claim['id']]
                or not isinstance(claim.get('reason'),str) or not claim['reason'].strip()):
            raise ProtocolFailure('Script quotes require an owned ID, exact source/target quote (1–32 chars) and reason')
        key=(claim['id'],claim['quote'])
        if key in seen:raise ProtocolFailure('Duplicate source script quote')
        seen.add(key)
    return claims


def content_findings(package,value):
    if not policy_v2(package):return mechanical_findings(package,value)
    claims=quote_claims(package,value);by_id={}
    for claim in claims:by_id.setdefault(claim['id'],[]).append(claim)
    rows=[(row['id'],row.get('text')) for row in value['segments']]
    if package.get('metadata_title_source'):rows.append((package['metadata_title_source']['id'],value.get('title_vi')))
    findings=[]
    for sid,text in rows:
        if not visible(text):
            findings.append({'id':sid,'kind':'empty_translation'});continue
        if '\ufffd' in text or any(unicodedata.category(ch)=='Cs' for ch in text):
            findings.append({'id':sid,'kind':'replacement_character'})
        explained=set()
        for claim in by_id.get(sid,[]):
            for match in re.finditer(re.escape(claim['quote']),text):explained.update(range(match.start(),match.end()))
        if any(match.start() not in explained for match in HAN.finditer(text)):
            findings.append({'id':sid,'kind':'residual_chinese'})
    return findings


def review_hints(package,value):
    """Hints are obligations for both native reviewers, never host-issued PASS."""
    if not policy_v2(package):return {}
    hints={}
    for source,target in zip(package['segments'],value['segments']):
        for term in sorted(set(term_occurrences(source['source'],package['glossary']))):
            expected=package['glossary'][term]
            if not contains_name(target['text'],expected):
                hints.setdefault(source['id'],[]).append({'kind':'entity_reference','source_term':term,
                    'canonical_name':expected,'duty':'Check the referent across context: pronoun/alias may be valid; a wrong person, misspelling or lost identity is an error.'})
    for claim in quote_claims(package,value):
        hints.setdefault(claim['id'],[]).append({'kind':'source_script_quote',
            'quote':claim['quote'],'native_reason':claim['reason'],
            'duty':'Verify original-script text is necessary quoted material, not untranslated residue. A declaration is not approval.'})
    return hints
