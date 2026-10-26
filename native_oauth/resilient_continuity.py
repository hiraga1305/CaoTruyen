"""Book-local editorial conventions, with literal evidence and native decisions.

This module does not infer identities, gender, relationships or Vietnamese names.
It selects declared conventions and requires both reviewers to explain their use.
"""
import re

from semantic_gate import read_json
from native_oauth.recovery_native import ProtocolFailure

VERSION = 'scoped-continuity-1'
CHECKS = ('names_and_labels', 'aliases_and_viewpoint', 'speaker_and_addressee')
KINDS = {'name', 'title', 'profession', 'item', 'place', 'faction', 'address', 'pronoun', 'term'}
ID = re.compile(r'c([0-9]{4,})p([0-9]{4,})\Z')


def text(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def evidence_chapter(entry):
    sid = entry.get('source_id')
    match = ID.fullmatch(sid) if isinstance(sid, str) else None
    if not match or int(match[1]) < 1 or int(match[2]) < 1:
        raise ValueError('Continuity convention needs a real source paragraph ID')
    return int(match[1])


def declared_entries(canon):
    entries = canon.get('continuity_entries', [])
    if not isinstance(entries, list):
        raise ValueError('continuity_entries must be an array')
    keys = set()
    required = {'key', 'kind', 'zh', 'vi', 'scope', 'source_id', 'source_quote'}
    optional = {'aliases_zh', 'aliases_vi', 'valid_from_chapter', 'valid_to_chapter', 'speaker_zh', 'addressee_zh'}
    for entry in entries:
        if (not isinstance(entry, dict) or not required.issubset(entry) or set(entry) - required - optional
                or not text(entry.get('key'), 128) or entry['key'] in keys
                or not isinstance(entry.get('kind'), str) or entry['kind'] not in KINDS or not text(entry.get('zh'), 64)
                or not text(entry.get('vi'), 128) or not text(entry.get('scope'), 1200)
                or not text(entry.get('source_quote'), 3000) or entry['zh'] not in entry['source_quote']):
            raise ValueError('Invalid, duplicate or ungrounded continuity convention')
        chapter = evidence_chapter(entry)
        start = entry.get('valid_from_chapter', chapter)
        end = entry.get('valid_to_chapter')
        if type(start) is not int or start < chapter or (end is not None and (type(end) is not int or end < start)):
            raise ValueError('Continuity scope cannot precede its source evidence')
        for field in ('aliases_zh', 'aliases_vi'):
            aliases = entry.get(field, [])
            if (not isinstance(aliases, list) or len(aliases) > 16 or any(not text(a, 128) for a in aliases)
                    or len(set(aliases)) != len(aliases)):
                raise ValueError('Continuity aliases must be explicit, unique strings')
        if any(alias not in entry['source_quote'] for alias in entry.get('aliases_zh', [])):
            raise ValueError('Chinese identity aliases need literal evidence in the cited source span')
        for field in ('speaker_zh', 'addressee_zh'):
            if field in entry and (not text(entry[field], 64) or entry[field] not in entry['source_quote']):
                raise ValueError('Speaker/addressee scope needs literal evidence, not inferred gender or relationships')
        if entry['kind'] == 'address' and not all(field in entry for field in ('speaker_zh', 'addressee_zh')):
            raise ValueError('An address convention must identify both speaker and addressee')
        keys.add(entry['key'])
    return entries


def selected_entries(canon, source):
    literal = source['title'] + '\n' + '\n'.join(row['source'] for row in source['segments'])
    chapter = source['chapter']
    return [entry for entry in declared_entries(canon)
            if entry.get('valid_from_chapter', evidence_chapter(entry)) <= chapter
            and (entry.get('valid_to_chapter') is None or chapter <= entry['valid_to_chapter'])
            and any(zh in literal for zh in (entry['zh'], *entry.get('aliases_zh', [])))]


def validate_contract(package, source):
    contract = package.get('continuity_contract')
    if contract is None:
        return  # Old approved evidence keeps its original schema and policy.
    if (not isinstance(contract, dict) or set(contract) != {'version', 'entries', 'evidence'}
            or contract['version'] != VERSION or contract['entries'] != selected_entries(package['canon'], source)
            or not isinstance(contract['evidence'], dict)
            or set(contract['evidence']) != {e['key'] for e in contract['entries']}):
        raise ValueError('Continuity contract differs from frozen source/canon scope')
    from native_oauth.chapter_integrity import validate_source, validate_source_archive
    cache = {}
    for entry in contract['entries']:
        proof = contract['evidence'][entry['key']]
        if not isinstance(proof, dict) or set(proof) != {'source_file', 'source_input_file'}:
            raise ValueError('Continuity convention is missing its source proof')
        paths = (proof['source_file'], proof['source_input_file'])
        if any(not isinstance(p, str) or p not in package['native_bound_files'] for p in paths):
            raise ValueError('Continuity evidence is not hash-bound')
        if paths not in cache:
            original = read_json(paths[0]); validate_source(original); validate_source_archive(original)
            if read_json(paths[1]) != original:
                raise ValueError('Continuity source changed after snapshot')
            cache[paths] = original
        original = cache[paths]
        if (original['book_id'] != source['book_id'] or original['chapter'] != evidence_chapter(entry)
                or original['chapter'] > source['chapter'] or not any(
                    row['id'] == entry['source_id'] and entry['source_quote'] in row['source']
                    for row in original['segments'])):
            raise ValueError('Continuity evidence belongs to another book, future chapter or invented quote')


def scoped_canon(canon, chapter):
    """Native prompts never reveal future evidence from an editorial file."""
    result = dict(canon)
    if 'continuity_entries' in canon:
        result['continuity_entries'] = [e for e in declared_entries(canon)
            if e.get('valid_from_chapter', evidence_chapter(e)) <= chapter
            and (e.get('valid_to_chapter') is None or chapter <= e['valid_to_chapter'])]
    if 'source_bound_terms' in canon:
        result['source_bound_terms'] = [e for e in canon['source_bound_terms'] if evidence_chapter(e) <= chapter]
    return result


def row_obligations(package, source):
    obligations = []
    for entry in package.get('continuity_contract', {}).get('entries', []):
        if any(zh in source for zh in (entry['zh'], *entry.get('aliases_zh', []))):
            obligations.append({'kind': 'continuity_convention', 'key': entry['key'],
                'category': entry['kind'], 'source_term': entry['zh'], 'canonical_name': entry['vi'],
                'accepted_forms': entry.get('aliases_vi', [])})
    return obligations


def required_decisions(packet):
    return [(slot, obligation) for slot in packet['scope_slots']
            for obligation in packet['catalog'][slot - 1].get('review_obligations', [])
            if obligation.get('kind') == 'continuity_convention']


def validate_review(packet, value):
    if packet.get('continuity_policy') is None:
        return
    if packet['continuity_policy'] != VERSION:
        raise ProtocolFailure('Unsupported continuity review policy')
    checks = value.get('continuity_checks')
    if not isinstance(checks, dict) or set(checks) != set(CHECKS) or any(v is not True for v in checks.values()):
        raise ProtocolFailure('Both reviewers must inspect names/labels, aliases/viewpoint and speaker/addressee')
    decisions = value.get('continuity_decisions')
    required = required_decisions(packet)
    if (not isinstance(decisions, list) or len(decisions) != len(required)
            or any(not isinstance(d, dict) for d in decisions)):
        raise ProtocolFailure('continuity_decisions must cover every assigned (slot,key) obligation')
    from native_oauth.resilient_policy import contains_name
    for decision, (slot, obligation) in zip(decisions, required):
        if (set(decision) != {'slot', 'key', 'status', 'reason'} or type(decision.get('slot')) is not int
                or decision['slot'] != slot or decision.get('key') != obligation['key']
                or decision.get('status') not in ('consistent', 'valid_variation', 'violation', 'needs_context')
                or not text(decision.get('reason'), 1600)):
            raise ProtocolFailure('Continuity decision needs its exact assigned slot/key, status and explanation')
        status = decision['status']
        if status == 'consistent' and not any(contains_name(packet['catalog'][slot - 1]['target'], form)
                for form in (obligation['canonical_name'], *obligation['accepted_forms'])):
            raise ProtocolFailure('Missing declared spelling needs a reasoned valid_variation or a real issue')
        if status in ('violation', 'needs_context'):
            kinds = {'needs_context'} if status == 'needs_context' else {'continuity', 'entities', 'speaker_pronouns'}
            if not any(i['slot'] == slot and i['kind'] in kinds for i in value['issues']):
                raise ProtocolFailure('A continuity violation/context gap requires a blocking owned issue, not style suggestion')
