"""Source/title drift regressions; all page observations and reviews are fixtures."""
import copy
import tempfile
import unittest
from pathlib import Path
from semantic_gate import build_package, digest, write_json, validate_review, CHECKS
from native_oauth.title_selection import load_selection, validate_selection, require_reviewed_selection
from native_oauth.book_publication import rendered_chapter, title_ids
from native_oauth.revise_book import revision_protocol, matching_legacy_rows
from native_oauth.chapter_integrity import require_approved, render_text
from native_test_helpers import native_runtime, bind_artifact, native_reviews


class SourceTitleSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'chapter_0001.dom.json'
        self.source={'version':'bns-source-v1','book_id':'fixture','chapter':1,
            'source_ref':'https://czbooks.net/n/fixture/chapter','title':'第1章 71018（感謝',
            'paragraph_count':3,
            'segments':[{'id':'c0001p0001','source':'第1章 71018（感謝'},
                        {'id':'c0001p0002','source':'第1章 710^18（感謝讀者）'},
                        {'id':'c0001p0003','source':'他走了。'}]}
        self.source['package_hash']=digest(self.source)
        self.snapshot={'method':'read_only_browser_dom','metadata_selector':'.name','article_selector':'.content',
            'chapter':1,'url':self.source['source_ref'],'metadata_title':'《測試書》第1章 71018（感謝',
            'article_heading':'第1章 710^18（感謝讀者）','article_heading_html':'\u2003\u2003第1章 710^18（感謝讀者）'}
        write_json(self.path,self.snapshot)
        self.plan=load_selection(self.source,self.path)
        self.aligned={'render_title_ownership':self.plan,'bilingual_alignment':[
            {'para_id':'c0001p0001','translated_vi':'Chương 1: 71018 (Cảm ơn'},
            {'para_id':'c0001p0002','translated_vi':'Chương 1: 710^18 (Cảm ơn độc giả)'},
            {'para_id':'c0001p0003','translated_vi':'Anh ấy đi rồi.'}]}

    def test_render_uses_article_heading_and_keeps_full_note_and_body(self):
        original=copy.deepcopy(self.source)
        result=rendered_chapter(self.source,self.aligned)
        self.assertEqual(result['title'],'Chương 1: 710^18 (Cảm ơn độc giả)')
        self.assertEqual(result['paragraphs'],['Anh ấy đi rồi.'])
        self.assertEqual(result['title_segment_ids'],['c0001p0001','c0001p0002'])
        self.assertEqual(self.source,original)

    def test_layout_cannot_discard_a_body_id_or_use_another_page(self):
        wrong=copy.deepcopy(self.plan);wrong['primary_title_id']='c0001p0003'
        with self.assertRaises(ValueError):validate_selection(self.source,wrong)
        snapshot={**self.snapshot,'url':'https://czbooks.net/n/other/chapter'};write_json(self.path,snapshot)
        with self.assertRaises(ValueError):load_selection(self.source,self.path)

    def test_title_choice_must_be_in_reviewed_package_and_snapshot_cannot_change(self):
        package={'render_title_ownership':self.plan,'native_bound_files':{str(self.path.resolve()):self.plan['snapshot_sha256']}}
        require_reviewed_selection(self.source,self.aligned,package)
        with self.assertRaises(ValueError):require_reviewed_selection(self.source,self.aligned,{})
        snapshot={**self.snapshot,'article_heading':'第1章 別的標題'};write_json(self.path,snapshot)
        with self.assertRaises(ValueError):require_reviewed_selection(self.source,self.aligned,package)

    def test_v2_article_heading_does_not_depend_on_lossy_toc_metadata(self):
        source={**self.source,'version':'bns-source-v2','segments':[
            {'id':f'c0001p{i:04d}','source':row['source']} for i,row in enumerate(self.source['segments'][1:],1)]}
        self.assertEqual(title_ids(source),['c0001p0001'])

    def test_publication_requires_native_review_of_the_exact_title_plan(self):
        root=Path(self.temp.name)
        package=build_package(1,self.source['title'],[r['source'] for r in self.source['segments']],{},self.source['source_ref'])
        package.update(origin_source_hash=self.source['package_hash'],render_title_ownership=self.plan,
            native_bound_files={str(self.path.resolve()):self.plan['snapshot_sha256']})
        package['package_hash']=digest({k:v for k,v in package.items() if k!='package_hash'})
        draft={'package_hash':package['package_hash'],'model':'native/fixture','identity_basis':'native_cli_init',
            'native_runtimes':[native_runtime(root/'generation')],
            'segments':[{'id':row['para_id'],'text':row['translated_vi']} for row in self.aligned['bilingual_alignment']]}
        draft=bind_artifact(root/'draft.json',draft)
        reviews=native_reviews(package,draft,root/'reviews')
        for i,review in enumerate(reviews):
            review['title_ownership_checked']=True
            reviews[i]=bind_artifact(root/f'review_{i}.json',review)
        evidence=root/'evidence.json'
        write_json(evidence,{'package':package,'candidate':draft,'reviews':reviews,
                             'review_policy':{'mode':'antigravity_sessions','version':1}})
        aligned={**self.aligned,'chapter_num':1,'total_paragraphs':3,'translated_paragraphs':3,
            'source_hash':self.source['package_hash'],'review_evidence':str(evidence),
            'bilingual_alignment':[{**row,'index':i,'raw_zh':raw['source']}
                for i,(row,raw) in enumerate(zip(self.aligned['bilingual_alignment'],self.source['segments']),1)]}
        text=render_text(aligned['bilingual_alignment'])
        self.assertEqual(require_approved(self.source,aligned,text,root)['status'],'PASS')
        aligned.pop('render_title_ownership')
        with self.assertRaisesRegex(ValueError,'title ownership'):require_approved(self.source,aligned,text,root)

    def test_each_reviewer_must_explicitly_check_source_backed_title_ownership(self):
        package=build_package(1,self.source['title'],[r['source'] for r in self.source['segments']],{},'fixture')
        package['render_title_ownership']=self.plan
        package['package_hash']=digest({k:v for k,v in package.items() if k!='package_hash'})
        candidate={'package_hash':package['package_hash'],'segments':[{'id':r['para_id'],'text':r['translated_vi']}
            for r in self.aligned['bilingual_alignment']]}
        review={'package_hash':package['package_hash'],'candidate_hash':digest(candidate),'verdict':'PASS',
            'checks':dict.fromkeys(CHECKS,True),'issues':[],'segments':[{'id':r['id'],'verdict':'PASS',
                'source_quote':r['source'],'target_quote':t['text'],'reason':'Fixture comparison'}
                for r,t in zip(package['segments'],candidate['segments'])]}
        with self.assertRaisesRegex(ValueError,'title ownership'):validate_review(package,candidate,review)
        review['title_ownership_checked']=True
        validate_review(package,candidate,review)

    def test_reindexed_legacy_body_is_never_offered_as_the_wrong_source_id(self):
        package={'segments':self.source['segments']}
        rows=[{'para_id':'c0001p0001','raw_zh':self.source['segments'][1]['source'],'translated_vi':'WRONG_TITLE_REFERENCE'},
              {'para_id':'c0001p0002','raw_zh':'他走了。','translated_vi':'WRONG_BODY_REFERENCE'}]
        original=copy.deepcopy(rows)
        self.assertEqual(matching_legacy_rows(package,rows),[])
        package=build_package(1,self.source['title'],[r['source'] for r in self.source['segments']],{},'fixture')
        protocol=revision_protocol(package,{'bilingual_alignment':rows})
        self.assertNotIn('WRONG_BODY_REFERENCE',protocol);self.assertNotIn('WRONG_TITLE_REFERENCE',protocol)
        self.assertIn('他走了。',protocol);self.assertEqual(rows,original)
