"""Historical chapter-1 entrypoint, now routed through mandatory semantic QA."""
from pipeline_api import main, process_single_chapter
from prepare_for_agent import load_lore
from source_integrity import terminology_hint


def chivi3_parse(text):
    return terminology_hint(text, load_lore())


def process_chapter_1():
    return process_single_chapter(1)


if __name__ == '__main__':
    main()
