"""Report committed approvals separately from verified drafts and legacy text."""
import argparse
import json
from pathlib import Path
from native_oauth.book_publication import read_manifest, read_approval
from native_oauth.chapter_integrity import read_verified_draft


def book_progress(book_dir, total_chapters):
    book = Path(book_dir)
    from native_oauth.resilient_publication import manifest_path, progress
    if manifest_path(book).exists():return progress(book,total_chapters)
    approved, invalid, words, paragraphs = [], [], 0, 0
    for key in read_manifest(book)['chapters']:
        chapter = int(key)
        if not 1 <= chapter <= total_chapters:
            continue
        try:
            value = read_approval(book, chapter)
            approved.append(chapter)
            words += sum(len(p.split()) for p in value['rendered']['paragraphs'])
            paragraphs += len(value['rendered']['paragraphs'])
        except (OSError, ValueError, KeyError, TypeError) as error:
            invalid.append({'chapter':chapter, 'reason':str(error)})
    drafts = []
    for path in (book/'drafts').glob('chuong_*.receipt.json'):
        chapter = int(path.name.split('.')[0].split('_')[1])
        if 1 <= chapter <= total_chapters and chapter not in approved and read_verified_draft(book, chapter):
            drafts.append(chapter)
    legacy = [int(path.stem.split('_')[1]) for path in (book/'output_dich').glob('chuong_*.txt')
              if path.stem.split('_')[1].isdigit()]
    wave_errors = []
    try:
        from native_oauth.wave_review import validate_wave_gates
        validate_wave_gates(book)
    except (OSError,ValueError,KeyError,TypeError) as error:
        wave_errors.append(str(error))
    return {'scope':'Independent approvals from the current manifest', 'total_chapters':total_chapters,
            'approved_chapters':sorted(approved), 'approved_count':len(approved),
            'approved_percent':round(len(approved)/total_chapters*100,1) if total_chapters else 0,
            'draft_unreviewed_chapters':sorted(drafts),
            'legacy_unreviewed_chapters':sorted(ch for ch in legacy if ch not in approved),
            'invalid_approvals':invalid, 'wave_review_errors':wave_errors,
            'export_ready':len(approved)==total_chapters and not invalid and not wave_errors,
            'approved_words':words, 'approved_paragraphs':paragraphs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book-dir', required=True, type=Path)
    parser.add_argument('--chapters', required=True, type=int)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.chapters < 1:
        parser.error('chapters must be positive')
    report = book_progress(args.book_dir, args.chapters)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.verify and not report['export_ready']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
