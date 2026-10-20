"""Default: source-frozen Antigravity OAuth batch drafts; --legacy-api is explicit."""
import sys
from pipeline_api import critic_qa_linter, load_lore, chivi3_parse_advanced, fetch_chapter_raw


def main():
    args=sys.argv[1:]
    if '--legacy-api' in args:
        from pipeline_api import main as api_main
        original=sys.argv[:]
        try:
            sys.argv=[sys.argv[0]]+[a for a in args if a!='--legacy-api']
            return api_main()
        finally:
            sys.argv=original
    from native_oauth.batch_run import main as native_main
    return native_main(args)


if __name__ == '__main__':
    main()
