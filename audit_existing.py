"""Offline triage of legacy TXT. Heuristics never certify semantic quality."""
import re
from pathlib import Path
from semantic_gate import read_json, write_json, digest, flatten_lore, prepared_raw, term_occurrences

ROOT = Path(__file__).resolve().parent


def main():
    glossary = flatten_lore(read_json(ROOT / 'novel_lore.json'))
    rows = []
    for file in sorted((ROOT / 'output_dich').glob('chuong_*.txt')):
        match = re.match(r'chuong_(\d+)', file.name)
        if not match:
            continue
        chapter = int(match[1])
        text = file.read_text(encoding='utf-8')
        body = re.split(r'={10,}\s*\n', text, maxsplit=1)[-1]
        sources = list((ROOT / 'prepared_input').glob(f'chap_{chapter:03d}_*.txt'))
        flags = []
        chinese = re.findall(r'[\u3400-\u9fff]+', body)
        if chinese:
            flags.append({'kind': 'residual_chinese', 'samples': chinese[:12]})
        source_hash = None
        if len(sources) == 1:
            paragraphs = prepared_raw(sources[0])
            raw = '\n\n'.join(paragraphs)
            source_hash = digest(raw)
            for term in sorted(set(term_occurrences(raw, glossary))):
                if glossary[term].casefold() not in body.casefold():
                    flags.append({'kind': 'canonical_term_absent', 'source_term': term, 'expected': glossary[term]})
        else:
            flags.append({'kind': 'no_paired_prepared_source'})
        rows.append({'chapter': chapter, 'file': str(file.resolve()), 'status': 'UNREVIEWED_LEGACY',
                     'target_hash': digest(text), 'source_file': str(sources[0].resolve()) if len(sources) == 1 else None,
                     'source_hash': source_hash, 'flags': flags})
    report = {'scope': 'Offline triage; not a semantic PASS; absent canonical terms are review flags',
              'chapters': len(rows), 'paired_sources': sum(r['source_hash'] is not None for r in rows),
              'flagged_chapters': sum(bool(r['flags']) for r in rows), 'results': rows}
    write_json(ROOT / 'audit' / 'legacy_inventory.json', report)
    print({k: report[k] for k in ('chapters', 'paired_sources', 'flagged_chapters')})


if __name__ == '__main__':
    main()
