"""Source-bound API entrypoint. Legacy outputs are unreviewed, never auto-skipped."""
import argparse
from multi_llm_client import load_config
from quality_pipeline import run_package, preflight
from prepare_for_agent import prepare_chapter, load_lore, chivi3_parse_advanced
from semantic_gate import read_json
from source_integrity import fetch_chapter_raw

OUTPUT_DIR = 'approved_output'


def critic_qa_linter(text):
    return text.replace('\r\n', '\n').strip()


def process_single_chapter(chap_num, href=None, title=None, provider=None, force=False,
                           context_file=None, max_repairs=1):
    if provider:
        raise ValueError('Configure provider/models per quality_roles')
    preflight(load_config())
    package_file = prepare_chapter(chap_num, context_file)
    return str(run_package(read_json(package_file), approved_dir=OUTPUT_DIR, max_repairs=max_repairs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', help='Use saved source package; no recrawl')
    parser.add_argument('--chap', type=int)
    parser.add_argument('--context')
    parser.add_argument('--max-repairs', type=int, default=1)
    parser.add_argument('--from_chap', type=int)
    parser.add_argument('--to_chap', type=int)
    parser.add_argument('--provider')
    parser.add_argument('--force', action='store_true', help='Every run ignores legacy caches')
    args = parser.parse_args()
    if args.from_chap or args.to_chap or args.provider:
        parser.error('Use one chapter/package with approved context and explicit quality_roles')
    if args.package:
        print(run_package(read_json(args.package), max_repairs=args.max_repairs))
    elif args.chap:
        print(process_single_chapter(args.chap, context_file=args.context, max_repairs=args.max_repairs))
    else:
        parser.error('Provide --package or --chap')


if __name__ == '__main__':
    main()
