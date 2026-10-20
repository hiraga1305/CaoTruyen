"""Compatibility entrypoint for the source-bound quality pipeline."""
from pipeline_api import main, critic_qa_linter
from source_integrity import fetch_chapter_raw as fetch_chapter_content


if __name__ == '__main__':
    main()
