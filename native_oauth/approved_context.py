"""Bounded retrieval of verbatim approved rows; no generated story summaries."""
import json
from pathlib import Path
from semantic_gate import digest
from native_oauth.semantic_context import entity_aliases


def retrieve_context(book_dir, chapter, previous_evidence, entities, current_source,
                     max_rows=24, max_characters=6000):
    previous_evidence = Path(previous_evidence).resolve()
    previous = json.loads(previous_evidence.read_text(encoding='utf-8'))
    keys = [entity_aliases(e) for e in entities
            if any(name in current_source for name in entity_aliases(e))]
    rows = []
    from native_oauth.book_publication import read_manifest, contained_file
    book = Path(book_dir)
    for key, entry in sorted(read_manifest(book)['chapters'].items(), key=lambda kv: int(kv[0])):
        number = int(key)
        if number >= chapter:
            continue
        evidence_file = str(contained_file(book, entry['receipt']).with_name('evidence.json'))
        evidence = json.loads(Path(evidence_file).read_text(encoding='utf-8'))
        for raw, target in zip(evidence['package']['segments'], evidence['candidate']['segments']):
            rows.append((number, evidence_file, {'source_id':raw['id'], 'source_quote':raw['source'],
                                                'statement':target['text']}))
    required = []
    recent = [r for r in rows if r[0] == chapter-1]
    # First introductions and latest mentions of currently present people are
    # both useful; their original statements remain viewpoints, not world truth.
    for aliases in keys:
        matched = [r for r in rows if any(alias in r[2]['source_quote'] for alias in aliases)]
        if matched:
            required.append(matched[0])
    selected, count = [], 0
    for row in required + list(reversed(recent[-4:])) + [r for r in reversed(rows)
                if any(any(k in r[2]['source_quote'] for k in aliases) for aliases in keys)]:
        if any(r[2]['source_id'] == row[2]['source_id'] for r in selected):
            continue
        size = len(row[2]['source_quote']) + len(row[2]['statement'])
        if len(selected) >= max_rows or count + size > max_characters:
            if row in required:
                raise ValueError('Required first-introduction context exceeds budget')
            continue
        selected.append(row)
        count += size
    paths = list(dict.fromkeys([str(previous_evidence)] + [row[1] for row in selected]))
    return {'through_chapter':chapter-1, 'previous_approved_hash':digest(previous['candidate']),
            'facts':[row[2] for row in selected], 'evidence_files':paths,
            'evidence_hashes':{p:digest(json.loads(Path(p).read_text(encoding='utf-8'))) for p in paths}}
