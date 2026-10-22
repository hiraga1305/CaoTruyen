"""Archived pilot code; not used by the Antigravity production workflow."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from semantic_gate import read_json,write_json,evaluate,publish,candidate_hash,digest
from native_oauth.pipeline_native import validate_literary_review


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',required=True)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--semantic-review',required=True)
    parser.add_argument('--literary-review',required=True)
    parser.add_argument('--semantic-session',required=True)
    parser.add_argument('--literary-session',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--publish-dir')
    args=parser.parse_args()
    package,candidate=read_json(args.package),read_json(args.candidate)
    reviews=[read_json(args.semantic_review),read_json(args.literary_review)]
    policy={'mode':'codex_gpt_sessions','required_sessions':[args.semantic_session,args.literary_session],
            'literary_session':args.literary_session,
            'identity_note':'Same inherited GPT may be used; independence is by separate attested Codex subagent sessions, not invented model versions'}
    report=evaluate(package,candidate,reviews,review_policy=policy)
    try:
        validate_literary_review(reviews[1])
    except ValueError as error:
        report['status']='BLOCKED'
        report['findings'].append({'kind':'literary_review_missing','reason':str(error)})
    write_json(args.out,report)
    print(report['status'])
    if report['status']!='PASS':
        raise SystemExit(2)
    if args.publish_dir:
        print(publish(package,candidate,reviews,args.publish_dir,review_policy=policy))


if __name__=='__main__':
    main()
