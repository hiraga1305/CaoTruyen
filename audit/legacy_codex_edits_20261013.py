"""Archived one-off pilot edits; not used by the Antigravity workflow."""
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from semantic_gate import read_json,write_json,digest,candidate_hash,mechanical_findings


def main():
    data=ROOT/'native_oauth/pilot_workspace/native_oauth/runs/chapter1'
    package=read_json(data/'source.json')
    original=read_json(data/'draft.json')
    semantic=read_json(ROOT/'native_oauth/codex_audit/semantic_review.json')
    literary=read_json(ROOT/'native_oauth/codex_audit/literary_review.json')
    if any(r['candidate_hash']!=candidate_hash(original) for r in [semantic,literary]):
        raise ValueError('Reviews do not match original draft')
    replacements={i['id']:i['correction'] for i in literary['issues']}
    old=next(s['text'] for s in original['segments'] if s['id']=='c0001p0019')
    replacements['c0001p0019']=old.replace('những học sinh xuất sắc các khóa trước',
                                        'những học sinh tốt nghiệp xuất sắc các khóa trước')
    replacements['c0001p0103']='Từ hai ba nghìn đến bảy tám nghìn… lần cuối cùng, Trương Vũ còn bảo bà chuyển thẳng hai mươi nghìn, nói đó là phí thuê Thiên Linh Căn.'
    final=copy.deepcopy(original)
    changes=[]
    sources={s['id']:s['source'] for s in package['segments']}
    for row in final['segments']:
        if row['id'] in replacements:
            changes.append({'id':row['id'],'source':sources[row['id']],
                            'before':row['text'],'after':replacements[row['id']]})
            row['text']=replacements[row['id']]
    final['edited_by']={'backend':'GPT in Codex','scope':'19 targeted source-bound paragraph corrections',
                        'native_original_candidate_hash':candidate_hash(original),
                        'review_hashes':[digest(semantic),digest(literary)]}
    if mechanical_findings(package,final):
        raise ValueError('Edited draft failed mechanical checks')
    target=ROOT/'native_oauth/codex_audit/draft.gpt_edited.json'
    write_json(target,final)
    write_json(ROOT/'native_oauth/codex_audit/edit_manifest.json',
               {'original_hash':candidate_hash(original),'edited_hash':candidate_hash(final),
                'source_package_hash':package['package_hash'],'changes':changes,
                'status':'AWAITING_INDEPENDENT_REVIEW_OF_EDITS'})
    # Isolated modern synthetic fixture; keep the original native output.
    work=ROOT/'native_oauth/pilot_hien_dai/native_oauth/runs/chapter1'
    modern=copy.deepcopy(read_json(work/'draft.json'))
    modern['segments'][2]['text']='Cô chưa nhận lời, chỉ nói cần suy nghĩ thêm hai ngày.'
    modern['segments'][3]['text']='Quản lý Trương yêu cầu lượng hàng tồn kho phải có ít nhất 900 sản phẩm, chứ không phải hơn 900 sản phẩm.'
    modern['edited_by']={'backend':'GPT in Codex','scope':'synthetic fixture paragraphs 3 and 4'}
    write_json(ROOT/'native_oauth/codex_audit/modern_fixture.gpt_edited.json',modern)
    print('New draft saved; paragraphs corrected:',len(changes))


if __name__=='__main__':
    main()
