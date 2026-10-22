"""Read-only verification of a native book repair campaign, including its baseline."""
import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from semantic_gate import read_json, write_json, digest
from native_oauth.book_publication import read_manifest, read_approval
from native_oauth.native_evidence import validate_provenance
from native_oauth.recover_missing import missing_segments


def campaign_status(book, job):
    book,job=Path(book).resolve(),Path(job).resolve()
    frozen=read_json(job/'baseline_manifest.json')
    changed=[]
    for relative,expected in frozen.items():
        for scope,root in (('original',book),('snapshot',job/'baseline')):
            path=(root/relative).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError('Baseline path escapes its root')
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected['sha256']:
                changed.append({'scope':scope,'path':relative})
    manifest=read_manifest(book)
    approved=[];invalid=[]
    for chapter in sorted(map(int,manifest['chapters'])):
        try:
            value=read_approval(book,chapter)
            approved.append({'chapter':chapter,'paragraphs':len(value['aligned']['bilingual_alignment']),
                'review_models':[r['model'] for r in value['evidence']['reviews']],
                'revision':value['receipt']['evidence_hash']})
        except (OSError,ValueError,KeyError,TypeError) as error:
            invalid.append({'chapter':chapter,'reason':str(error)})
    recoveries=[]
    for path in sorted((job/'recovery_proposals').glob('chapter_*.json')):
        result=read_json(path);chapter=result['chapter']
        source=read_json(job/'baseline/sources'/f'source_chapter_{chapter:04d}.json')
        legacy=read_json(job/'baseline/output_dich'/f'chuong_{chapter:04d}.dich.json')
        expected=missing_segments(source,legacy)
        if (result.get('status')!='RECOVERY_PROPOSAL_UNREVIEWED' or result.get('source_hash')!=source['package_hash']
                or [r['id'] for r in result['segments']] != [r['id'] for r in expected]):
            raise ValueError('Recovery proposal source/coverage mismatch')
        generated=[]
        for proof in result['native_results']:
            validate_provenance(proof)
            if proof.get('source_hash')!=source['package_hash']:
                raise ValueError('Recovery runtime belongs to another source')
            generated.extend(proof['segments'])
        if generated!=result['segments']:
            raise ValueError('Recovered text differs from actual native responses')
        recoveries.append({'chapter':chapter,'paragraphs':len(expected),'status':result['status']})
    state=read_json(job/'campaign.json')
    manifest_stable=read_manifest(book)==manifest
    return {'as_of_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Verified local native revisions; recovery proposals do not grant publication approval',
        'campaign_state':state,'baseline_files':len(frozen),'baseline_changes':changed,
        'manifest_hash':digest(manifest),'manifest_stable':manifest_stable,
        'approved_count':len(approved),'approved':approved,'invalid_approvals':invalid,
        'unreviewed_recoveries':recoveries,'recovered_draft_paragraphs':sum(r['paragraphs'] for r in recoveries),
        'full_range_approved':not invalid and not changed and manifest_stable
            and [r['chapter'] for r in approved]==list(range(1,state['range'][1]+1))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book-dir',required=True,type=Path)
    parser.add_argument('--job',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    result=campaign_status(args.book_dir,args.job)
    write_json(args.out,result)
    print({key:result[key] for key in ('approved_count','baseline_files','baseline_changes',
                                     'recovered_draft_paragraphs','full_range_approved')})
    if result['baseline_changes'] or result['invalid_approvals'] or not result['manifest_stable']:
        raise SystemExit(2)


if __name__=='__main__':
    main()
