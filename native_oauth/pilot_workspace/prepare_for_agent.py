"""Prepare immutable Chinese source packages for native agents."""
import argparse
import re
from pathlib import Path
from semantic_gate import build_package, flatten_lore, read_json, write_json, translation_prompt
from source_integrity import fetch_chapter_raw, terminology_hint

ROOT = Path(__file__).resolve().parent
LORE_FILE = ROOT / 'novel_lore.json'
PREPARED_DIR = ROOT / 'prepared_input_v2'


def load_lore():
    return flatten_lore(read_json(LORE_FILE))


def chivi3_parse_advanced(text, glossary):
    return terminology_hint(text, glossary)


def prepare_chapter(chap_num, context_file=None):
    toc = read_json(ROOT / 'toc_cache.json')
    if not 1 <= chap_num <= len(toc):
        raise ValueError('Chapter outside TOC')
    href, title = toc[chap_num - 1]
    context = read_json(context_file) if context_file else None
    if chap_num > 1 and not context:
        raise ValueError('Provide --context with approved preceding chapter evidence')
    paragraphs = fetch_chapter_raw(href)
    if re.sub(r'\s+', '', paragraphs[0]) != re.sub(r'\s+', '', title):
        raise ValueError('Returned title does not match cached TOC; inspect source/refresh TOC')
    package = build_package(chap_num, title, paragraphs, load_lore(),
                            'https://www.piaotia.com/html/16/16014/' + href, context)
    safe = re.sub(r'[\\/*?:"<>|]', '', title).strip()
    package_file = PREPARED_DIR / f'chap_{chap_num:03d}_{safe}_{package["package_hash"][:12]}.source.json'
    write_json(package_file, package)
    prompt_file = package_file.with_suffix('.translator.txt')
    prompt_file.write_text(translation_prompt(package), encoding='utf-8')
    print(package_file)
    return str(package_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chap', type=int, default=1)
    parser.add_argument('--context')
    parser.add_argument('--from_chap', type=int)
    parser.add_argument('--to_chap', type=int)
    args = parser.parse_args()
    if args.from_chap or args.to_chap:
        parser.error('Prepare sequentially with a separate approved context for each chapter')
    prepare_chapter(args.chap, args.context)
