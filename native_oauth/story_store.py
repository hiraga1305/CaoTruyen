"""Durable source-only retrieval for one novel; not a semantic approval gate.

Literal mention and recent-source retrieval is indexed and bounded. It does not
resolve coreference. Original Chinese quotes are evidence; glossary is policy.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic_gate import digest, read_json, write_json
from native_oauth.batch_contract import _sources, ID_PATTERN

SCHEMA = 'source-story-store-1'
CUES = ('母亲', '父亲', '姐姐', '妹妹', '哥哥', '弟弟', '朋友', '老师', '学生',
        '同学', '借款', '贷款', '转账', '原身', '拒绝', '答应')


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _integer(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('Invalid ' + label)
    return value


class StoryStore:
    """One database per book. Use a separate connection for each worker/thread."""

    def __init__(self, path, book_id='default'):
        if not isinstance(book_id, str) or not book_id:
            raise ValueError('Book identity required')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=10000')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS revisions(
                revision INTEGER PRIMARY KEY, parent_hash TEXT, revision_hash TEXT NOT NULL,
                operation TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS chapters(
                chapter INTEGER PRIMARY KEY, package_hash TEXT NOT NULL, package_json TEXT NOT NULL,
                introduced_revision INTEGER NOT NULL REFERENCES revisions(revision));
            CREATE TABLE IF NOT EXISTS paragraphs(
                source_id TEXT PRIMARY KEY, chapter INTEGER NOT NULL REFERENCES chapters(chapter),
                ordinal INTEGER NOT NULL, source TEXT NOT NULL, source_hash TEXT NOT NULL,
                package_hash TEXT NOT NULL, introduced_revision INTEGER NOT NULL REFERENCES revisions(revision),
                UNIQUE(chapter,ordinal));
            CREATE INDEX IF NOT EXISTS paragraph_position ON paragraphs(chapter DESC,ordinal DESC);
            CREATE TABLE IF NOT EXISTS mentions(
                key TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES paragraphs(source_id),
                chapter INTEGER NOT NULL, ordinal INTEGER NOT NULL, quote TEXT NOT NULL,
                quote_hash TEXT NOT NULL, introduced_revision INTEGER NOT NULL REFERENCES revisions(revision),
                PRIMARY KEY(key,source_id,quote_hash));
            CREATE INDEX IF NOT EXISTS mention_lookup ON mentions(key,chapter DESC,ordinal DESC);
            CREATE TABLE IF NOT EXISTS glossary(
                key TEXT PRIMARY KEY, target TEXT NOT NULL,
                introduced_revision INTEGER NOT NULL REFERENCES revisions(revision));
        ''')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            identity = dict(self.db.execute('SELECT key,value FROM metadata'))
            if identity and identity != {'schema': SCHEMA, 'book_id': book_id}:
                raise ValueError('Database book identity/schema mismatch')
            if not identity:
                self.db.executemany('INSERT INTO metadata VALUES(?,?)', [('schema', SCHEMA), ('book_id', book_id)])
                operation = _encoded({'schema': SCHEMA, 'book_id': book_id})
                revision_hash = digest({'revision': 0, 'parent_hash': None, 'operation': operation})
                self.db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (0, None, revision_hash, operation))
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK')
            self.db.close()
            raise
        self.book_id = book_id

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @property
    def revision(self):
        return self.db.execute('SELECT MAX(revision) FROM revisions').fetchone()[0]

    def snapshot(self, revision=None):
        revision = self.revision if revision is None else revision
        _integer(revision, 0, self.revision, 'revision')
        row = self.db.execute('SELECT * FROM revisions WHERE revision=?', (revision,)).fetchone()
        if row is None:
            raise ValueError('Unknown revision')
        expected = digest({'revision': row['revision'], 'parent_hash': row['parent_hash'], 'operation': row['operation']})
        if row['revision_hash'] != expected:
            raise ValueError('Revision hash changed')
        return {'schema': SCHEMA, 'book_id': self.book_id, 'revision': revision,
                'revision_hash': row['revision_hash']}

    def index_package(self, package, ledger_entries=(), *, expected_revision,
                      max_paragraphs=2000, max_source_chars=1000000, max_mentions=100000):
        """Transactionally index one sealed ORIGINAL source chapter, idempotently.

        No target-text/interpretation input is accepted. Generated NER keys may
        locate quotes but have no authority beyond their literal source occurrence.
        """
        _integer(max_paragraphs, 1, 10000, 'paragraph cap')
        _integer(max_source_chars, 1, 2000000, 'source character cap')
        _integer(max_mentions, 1, 200000, 'mention cap')
        if len(package.get('segments', [])) > max_paragraphs:
            raise ValueError('Index paragraph cap exceeded')
        if any(set(s) - {'id', 'source', 'source_hash'} for s in package.get('segments', [])):
            raise ValueError('Only original source fields accepted; no target draft')
        if any(k in package for k in ('candidate_hash', 'translation', 'approved_translation', 'target', 'text')):
            raise ValueError('Target draft must never enter source store')
        index, _, chapters = _sources([package])
        if any('source_hash' in segment and segment['source_hash'] != index[segment['id']]['source_hash']
               for segment in package['segments']):
            raise ValueError('Supplied original source hash disagrees with text')
        if sum(len(s['source']) for s in index.values()) > max_source_chars:
            raise ValueError('Index source character cap exceeded')
        chapter = chapters[0]
        glossary = package.get('glossary', {})
        if not isinstance(glossary, dict) or len(glossary) > 10000 or any(
                not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in glossary.items()):
            raise ValueError('Invalid glossary')
        mention_rows = set()
        def mention(key, identifier, quote):
            row = index.get(identifier)
            if (not row or not isinstance(key, str) or not key or len(key) > 256
                    or not isinstance(quote, str) or not quote or quote not in row['source'] or key not in quote):
                raise ValueError('Mention quote/key not bound to original source')
            ordinal = int(ID_PATTERN.fullmatch(identifier).group(2))
            mention_rows.add((key, identifier, chapter, ordinal, quote, digest(quote)))
            if len(mention_rows) > max_mentions:
                raise ValueError('Index mention cap exceeded')
        for row in index.values():
            for key in tuple(glossary) + CUES:
                if key in row['source']:
                    mention(key, row['id'], row['source'])
        for entry in ledger_entries:
            if set(entry) - {'ledger_id', 'kind', 'keys', 'references', 'valid_from', 'required', 'global_required'}:
                raise ValueError('Only original source quote entries accepted; no interpretation/draft')
            keys, refs = entry.get('keys'), entry.get('references')
            if not isinstance(keys, list) or not keys or not isinstance(refs, list) or not refs:
                raise ValueError('Mention keys and source references required')
            for ref in refs:
                raw = index.get(ref.get('source_id'))
                quote = ref.get('source_quote')
                if not raw or not isinstance(quote, str) or not quote or quote not in raw['source']:
                    raise ValueError('Mention quote not bound to original source')
                for key in keys:
                    # Only keys present in this particular quote are indexed.
                    quote = ref.get('source_quote')
                    if isinstance(quote, str) and isinstance(key, str) and key in quote:
                        mention(key, ref.get('source_id'), quote)
                    elif not isinstance(quote, str) or not isinstance(key, str):
                        raise ValueError('Invalid source reference')
            if any(not any(isinstance(r.get('source_quote'), str) and k in r['source_quote'] for r in refs) for k in keys):
                raise ValueError('Mention key has no source evidence')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            current = self.revision
            if type(expected_revision) is not int or expected_revision != current:
                raise ValueError('Stale optimistic revision; refresh snapshot and retry')
            existing = self.db.execute('SELECT package_hash FROM chapters WHERE chapter=?', (chapter,)).fetchone()
            if existing and existing['package_hash'] != package['package_hash']:
                raise ValueError('Already indexed source changed; create a new book store')
            for key, target in glossary.items():
                previous = self.db.execute('SELECT target FROM glossary WHERE key=?', (key,)).fetchone()
                if previous and previous['target'] != target:
                    raise ValueError('Conflicting canonical glossary: ' + key)
            new_mentions = [m for m in sorted(mention_rows) if not self.db.execute(
                'SELECT 1 FROM mentions WHERE key=? AND source_id=? AND quote_hash=?', (m[0], m[1], m[5])).fetchone()]
            new_terms = [(k, v) for k, v in sorted(glossary.items()) if not self.db.execute(
                'SELECT 1 FROM glossary WHERE key=?', (k,)).fetchone()]
            if existing and not new_mentions and not new_terms:
                snapshot = self.snapshot()
                self.db.execute('COMMIT')
                return {**snapshot, 'changed': False}
            previous = self.snapshot()
            revision = current + 1
            operation = _encoded({'chapter': chapter, 'package_hash': package['package_hash'],
                                  'new_source': not bool(existing), 'mentions_hash': digest(new_mentions),
                                  'glossary_hash': digest(new_terms)})
            revision_hash = digest({'revision': revision, 'parent_hash': previous['revision_hash'], 'operation': operation})
            self.db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (revision, previous['revision_hash'], revision_hash, operation))
            if not existing:
                self.db.execute('INSERT INTO chapters VALUES(?,?,?,?)', (chapter, package['package_hash'], _encoded(package), revision))
                self.db.executemany('INSERT INTO paragraphs VALUES(?,?,?,?,?,?,?)',
                    [(s['id'], chapter, int(ID_PATTERN.fullmatch(s['id']).group(2)), s['source'], s['source_hash'], package['package_hash'], revision) for s in index.values()])
            self.db.executemany('INSERT INTO glossary VALUES(?,?,?)', [(k, v, revision) for k, v in new_terms])
            self.db.executemany('INSERT INTO mentions VALUES(?,?,?,?,?,?,?)', [(*m, revision) for m in new_mentions])
            self.db.execute('COMMIT')
            return {**self.snapshot(revision), 'changed': True}
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def _paragraph(self, source_id, revision):
        row = self.db.execute('SELECT * FROM paragraphs WHERE source_id=? AND introduced_revision<=?',
                              (source_id, revision)).fetchone()
        if row is None:
            raise ValueError('Source id absent from requested snapshot: ' + source_id)
        if row['source_hash'] != digest(row['source']):
            raise ValueError('Stored source hash changed')
        return row

    def get_source_package(self, chapter, revision=None):
        """Return a fresh, verified copy of a previously indexed source package.

        Indexed source is not an approved translation or publication barrier.
        This permits later-block source context without loading all prior chapters.
        """
        _integer(chapter, 1, 10000000, 'chapter')
        snap = self.snapshot(revision)
        row = self.db.execute('SELECT * FROM chapters WHERE chapter=? AND introduced_revision<=?',
                              (chapter, snap['revision'])).fetchone()
        if row is None:
            raise ValueError('Source chapter absent from requested snapshot')
        package = json.loads(row['package_json'])
        index, _, chapters = _sources([package])
        if chapters != [chapter] or package['package_hash'] != row['package_hash']:
            raise ValueError('Stored package hash/chapter changed')
        self.snapshot(row['introduced_revision'])
        introduction = self.db.execute('SELECT operation FROM revisions WHERE revision=?',
                                        (row['introduced_revision'],)).fetchone()
        operation = json.loads(introduction['operation'])
        if (operation.get('chapter') != chapter or operation.get('package_hash') != row['package_hash']
                or operation.get('new_source') is not True):
            raise ValueError('Stored package differs from its immutable index revision')
        count = self.db.execute('SELECT COUNT(*) FROM paragraphs WHERE chapter=? AND introduced_revision<=?',
                                (chapter, snap['revision'])).fetchone()[0]
        if count != len(index):
            raise ValueError('Stored source package coverage changed')
        for identifier, expected in index.items():
            actual = self._paragraph(identifier, snap['revision'])
            if (actual['source'] != expected['source'] or actual['source_hash'] != expected['source_hash']
                    or actual['package_hash'] != package['package_hash']):
                raise ValueError('Stored source disagrees with sealed original package')
        # Decode created a fresh copy. Only source-store projections should be
        # indexed by route adapters; this never invents translation approval.
        return package

    def retrieve_capsule(self, owned_ids, keys=(), *, revision=None, before_id=None,
                         pronoun_recent=4, max_entries=32, max_chars=12000,
                         retain_first_anchor=True):
        """Bounded past quotes. Recent paragraphs assist pronouns, never resolve them.

        A revision is immutable: newer source/mentions/glossary are excluded. The
        exclusive cutoff cannot extend beyond the first owned paragraph.
        """
        _integer(pronoun_recent, 0, 32, 'recent evidence cap')
        _integer(max_entries, 1, 256, 'capsule entry cap')
        _integer(max_chars, 256, 100000, 'capsule character cap')
        if type(retain_first_anchor) is not bool:
            raise ValueError('First source anchor policy must be boolean')
        if not isinstance(owned_ids, (list, tuple)) or not 1 <= len(owned_ids) <= 256:
            raise ValueError('Owned source cap is 256 paragraphs')
        if len(set(owned_ids)) != len(owned_ids):
            raise ValueError('Duplicate owned source id')
        if not isinstance(keys, (list, tuple)) or len(keys) > 128 or any(not isinstance(k, str) or not k or len(k) > 256 for k in keys):
            raise ValueError('Retrieval key cap/type exceeded')
        snap = self.snapshot(revision)
        revision = snap['revision']
        owned = [self._paragraph(i, revision) for i in owned_ids]
        positions = [(s['chapter'], s['ordinal']) for s in owned]
        if positions != sorted(positions):
            raise ValueError('Owned source ids must be in source order')
        cutoff_row = self._paragraph(before_id, revision) if before_id else owned[0]
        cutoff = (cutoff_row['chapter'], cutoff_row['ordinal'])
        if cutoff > positions[0]:
            raise ValueError('Past retrieval cutoff would expose future source')
        evidence, seen = [], set()
        pooled_chars, pool_omitted = 0, 0
        def add(row, key):
            nonlocal pooled_chars, pool_omitted
            source = self._paragraph(row['source_id'], revision)
            quote = row['quote'] if 'quote' in row.keys() else source['source']
            quote_hash = row['quote_hash'] if 'quote_hash' in row.keys() else digest(quote)
            if (quote_hash != digest(quote) or quote not in source['source'] or
                    (source['chapter'], source['ordinal']) != (row['chapter'], row['ordinal'])):
                raise ValueError('Stored quote hash/evidence changed')
            token = (source['source_id'], quote_hash)
            if token in seen:
                return
            seen.add(token)
            if len(evidence) >= max_entries * 4 or pooled_chars + len(quote) > max_chars * 4:
                pool_omitted += 1
                return
            pooled_chars += len(quote)
            evidence.append({'source_id': source['source_id'], 'chapter': source['chapter'],
                             'source_quote': quote, 'quote_hash': quote_hash,
                             'source_hash': source['source_hash'], 'source_package_hash': source['package_hash'],
                             'retrieved_by': key})
        for key in sorted(set(keys)):
            if retain_first_anchor:
                first = self.db.execute('''SELECT * FROM mentions
                    WHERE key=? AND (chapter,ordinal)<(?,?) AND introduced_revision<=?
                    ORDER BY chapter ASC,ordinal ASC,quote_hash LIMIT 1''',
                    (key, *cutoff, revision)).fetchone()
                if first:
                    if key not in first['quote']:
                        raise ValueError('Stored mention key lost source evidence')
                    add(first, 'literal_first_source_anchor:' + key)
            recent_limit = min(3, max(0, max_entries-1)) if retain_first_anchor else min(4, max_entries)
            rows = self.db.execute('''SELECT * FROM mentions
                WHERE key=? AND (chapter,ordinal)<(?,?) AND introduced_revision<=?
                ORDER BY chapter DESC,ordinal DESC,quote_hash LIMIT ?''',
                (key, *cutoff, revision, recent_limit))
            for row in rows:
                if key not in row['quote']:
                    raise ValueError('Stored mention key lost source evidence')
                add(row, 'literal_latest:' + key)
        for row in self.db.execute('''SELECT * FROM paragraphs
                WHERE (chapter,ordinal)<(?,?) AND introduced_revision<=?
                ORDER BY chapter DESC,ordinal DESC LIMIT ?''', (*cutoff, revision, pronoun_recent)):
            add(row, 'recent_original_source_not_coreference')
        terms = {}
        for key in sorted(set(keys)):
            row = self.db.execute('SELECT target FROM glossary WHERE key=? AND introduced_revision<=?', (key, revision)).fetchone()
            if row:
                terms[key] = row['target']
        capsule = {**snap, 'source_visibility_before': cutoff_row['source_id'], 'owned_ids': list(owned_ids),
                   'glossary': terms, 'evidence': [], 'omitted_evidence_candidates': pool_omitted,
                   'retrieval_candidates_per_key': min(4, max_entries),
                   'retain_first_source_anchor': retain_first_anchor,
                   'authority': 'Quoted original Chinese; glossary is editorial policy; no semantic PASS.',
                   'retrieval': 'Indexed literal first/latest mentions plus bounded recent source; not coreference.'}
        def capsule_size(value):
            return len(_encoded({**value, 'capsule_hash': '0' * 64}))
        if capsule_size(capsule) > max_chars:
            raise ValueError('Capsule metadata exceeds budget')
        for item in evidence:
            candidate = {**capsule, 'evidence': capsule['evidence'] + [item]}
            if len(candidate['evidence']) <= max_entries and capsule_size(candidate) + 16 <= max_chars:
                capsule = candidate
            else:
                capsule['omitted_evidence_candidates'] += 1
        if capsule_size(capsule) > max_chars:
            raise ValueError('Capsule budget exceeded')
        capsule['capsule_hash'] = digest(capsule)
        return capsule

    def integrity_check(self):
        """Full streaming audit, opt-in; retrieval verifies only the rows it uses."""
        if self.db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or self.db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('SQLite integrity failure')
        previous = None
        for row in self.db.execute('SELECT * FROM revisions ORDER BY revision'):
            if row['parent_hash'] != previous:
                raise ValueError('Revision chain changed')
            self.snapshot(row['revision'])
            previous = row['revision_hash']
        for row in self.db.execute('SELECT * FROM chapters'):
            package = json.loads(row['package_json'])
            _sources([package])
            if package['package_hash'] != row['package_hash']:
                raise ValueError('Stored package hash changed')
            if self.db.execute('SELECT COUNT(*) FROM paragraphs WHERE chapter=?', (row['chapter'],)).fetchone()[0] != len(package['segments']):
                raise ValueError('Stored chapter coverage changed')
            for segment in package['segments']:
                actual = self._paragraph(segment['id'], self.revision)
                if actual['source'] != segment['source'] or actual['package_hash'] != row['package_hash']:
                    raise ValueError('Stored source disagrees with original package')
        for row in self.db.execute('SELECT * FROM mentions'):
            source = self._paragraph(row['source_id'], self.revision)
            if (digest(row['quote']) != row['quote_hash'] or row['quote'] not in source['source']
                    or row['key'] not in row['quote'] or (row['chapter'], row['ordinal']) != (source['chapter'], source['ordinal'])):
                raise ValueError('Stored mention quote/hash changed')
        return {'status': 'INTEGRITY_VERIFIED_NOT_SEMANTIC_PASS', **self.snapshot(),
                'paragraphs': self.db.execute('SELECT COUNT(*) FROM paragraphs').fetchone()[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--book-id', default='default')
    commands = parser.add_subparsers(dest='command', required=True)
    index = commands.add_parser('index')
    index.add_argument('--source', required=True)
    index.add_argument('--ledger')
    index.add_argument('--expected-revision', required=True, type=int)
    retrieve = commands.add_parser('retrieve')
    retrieve.add_argument('--owned', nargs='+', required=True)
    retrieve.add_argument('--key', action='append', default=[])
    retrieve.add_argument('--revision', type=int)
    retrieve.add_argument('--recent', type=int, default=4)
    retrieve.add_argument('--latest-only', action='store_true', help='Disable first literal source anchor retention')
    retrieve.add_argument('--out', required=True)
    commands.add_parser('check')
    args = parser.parse_args()
    with StoryStore(args.db, args.book_id) as store:
        if args.command == 'index':
            result = store.index_package(read_json(args.source), read_json(args.ledger) if args.ledger else (), expected_revision=args.expected_revision)
        elif args.command == 'retrieve':
            result = store.retrieve_capsule(args.owned, args.key, revision=args.revision,
                pronoun_recent=args.recent, retain_first_anchor=not args.latest_only)
            write_json(args.out, result)
            result = {'out': args.out, 'capsule_hash': result['capsule_hash'], 'revision': result['revision']}
        else:
            result = store.integrity_check()
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
