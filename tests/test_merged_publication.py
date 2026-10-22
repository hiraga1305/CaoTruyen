"""G-copy source/export regressions exercised against the combined native gate.

All review/translation data is synthetic; no real models or novel publication.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_antigravity_workflow as fixture_module
from semantic_gate import digest, write_json
from native_oauth.book_publication import read_manifest, read_approval, load_approved_chapters
from native_oauth.review_book_chapter import review_and_promote
from native_oauth.book_progress import book_progress
from native_oauth.source_adapters import extract_paragraphs, normalize_paragraphs, fetch_czbooks
from native_oauth.chapter_integrity import validate_source, source_content_hash, read_verified_draft
from native_oauth.export_integrity import verify_epub, verify_pdf, verify_azw3

AVAILABLE = all(importlib.util.find_spec(m) for m in ('fitz','ebooklib','reportlab','PIL'))


class MergedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.AntigravityWorkflowTests('test_complete_book_draft_review_promote_and_revalidate')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.book, _ = self.fixture.draft_book()

    def approve(self, chapter):
        with patch('native_oauth.review_book_chapter.run_independent_reviews',side_effect=self.fixture.fake_reviews):
            return review_and_promote(self.book, chapter, 'fixture', 'fixture')

    def two_chapters(self):
        self.fixture.draft_book(1, body='Anh ấy nói: A & B < C.', raw_body='他说：A & B < C。', force=True)
        self.approve(1)
        self.fixture.draft_book(2)
        self.approve(2)
        return load_approved_chapters(self.book,[1,2])

    def test_draft_and_legacy_files_never_count_as_approved(self):
        report = book_progress(self.book,2)
        self.assertEqual(report['approved_count'],0)
        self.assertEqual(report['draft_unreviewed_chapters'],[1])
        with self.assertRaises(ValueError): load_approved_chapters(self.book,[1,2])

    def test_new_revision_preserves_old_artifacts_and_invalidates_later_manifest(self):
        self.two_chapters()
        old = read_approval(self.book,1)
        old_evidence = old['evidence_path'].read_bytes()
        self.fixture.draft_book(1, body='Anh ấy nói: A & B nhỏ hơn C.', raw_body='他说：A & B < C。', force=True)
        # A new unreviewed draft must not mutate the committed old revision/runtime.
        self.assertEqual(read_approval(self.book,1)['evidence'],old['evidence'])
        self.approve(1)
        self.assertEqual(set(read_manifest(self.book)['chapters']),{'1'})
        self.assertEqual(old['evidence_path'].read_bytes(),old_evidence)
        with self.assertRaises(ValueError): load_approved_chapters(self.book,[1,2])

    def test_manifest_pointer_escape_and_receipt_tampering_block(self):
        self.approve(1)
        path = self.book/'approved/manifest.json'
        manifest = read_manifest(self.book)
        manifest['chapters']['1']['receipt'] = '../outside/receipt.json'
        write_json(path,manifest)
        with self.assertRaisesRegex(ValueError,'escapes'): read_approval(self.book,1)

    def test_adding_previously_absent_canon_invalidates_approval(self):
        self.approve(1)
        write_json(self.book/'lore.json',{'characters':{'他':'Tên mới'}})
        with self.assertRaises(ValueError): read_approval(self.book,1)

    def test_candidate_cannot_diverge_from_native_response_even_with_rehashed_receipt(self):
        path=self.book/'drafts/chuong_0001.dich.json'
        receipt_path=path.with_name('chuong_0001.receipt.json')
        candidate=json.loads(path.read_text(encoding='utf-8'))
        candidate['bilingual_alignment'][1]['translated_vi']='Tự sửa mất nghĩa.'
        write_json(path,candidate)
        from native_oauth.chapter_integrity import render_text
        text=render_text(candidate['bilingual_alignment'])
        path.with_name('chuong_0001.txt').write_text(text,encoding='utf-8')
        receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
        receipt.update(candidate_hash=digest(candidate),text_hash=digest(text))
        write_json(receipt_path,receipt)
        self.assertIsNone(read_verified_draft(self.book,1))

    @unittest.skipUnless(AVAILABLE,'Install requirements-publishing.txt for actual exporters')
    def test_actual_epub_and_pdf_export_from_approved_manifest(self):
        from native_oauth.book_49736 import build_ebooks as exporter
        chapters=self.two_chapters()
        folder=self.book/'export'
        folder.mkdir()
        values={'BOOK_DIR':self.book,'TOTAL_CHAPTERS':2,'DIST_DIR':folder,
                'FINAL_PDF_PATH':folder/'fixture.pdf','FINAL_EPUB_PATH':folder/'fixture.epub',
                'FINAL_AZW3_PATH':folder/'fixture.azw3','COVER_PATH':folder/'cover.jpg',
                'BOOK_TITLE':'KIỂM THỬ XUẤT BẢN','BOOK_SUBTITLE':'DỮ LIỆU TỔNG HỢP'}
        with patch.multiple(exporter,**values), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError): exporter.export_pdf(chapters[:1])
            exporter.export_epub_and_azw3(chapters,folder/'no-cover.jpg',include_azw3=False)
            self.assertEqual(verify_epub(folder/'fixture.epub',chapters)['paragraphs'],2)
            with self.assertRaises(ValueError): verify_epub(folder/'fixture.epub',list(reversed(chapters)))
            if Path('C:/Windows/Fonts/times.ttf').exists():
                exporter.export_pdf(chapters)
                self.assertEqual(verify_pdf(folder/'fixture.pdf',chapters)['chapters'],2)

    def test_azw3_requires_round_trip_converter(self):
        with patch('native_oauth.export_integrity.shutil.which',return_value=None):
            with self.assertRaises(RuntimeError): verify_azw3(self.book/'missing.azw3',[])

    @unittest.skipUnless(AVAILABLE,'Install requirements-publishing.txt for actual exporters')
    def test_export_entrypoint_writes_receipt_after_verified_outputs(self):
        from native_oauth.book_49736 import build_ebooks as exporter
        self.two_chapters()
        folder=self.book/'dist'
        values={'BOOK_DIR':self.book,'TOTAL_CHAPTERS':2,'DIST_DIR':folder,
                'FINAL_PDF_PATH':folder/'fixture.pdf','FINAL_EPUB_PATH':folder/'fixture.epub',
                'FINAL_AZW3_PATH':folder/'fixture.azw3','COVER_PATH':folder/'cover.jpg'}
        with patch.multiple(exporter,**values), patch('sys.argv',['exporter','--formats','epub']), \
                patch.object(exporter,'generate_cover_image',side_effect=lambda path:path), \
                contextlib.redirect_stdout(io.StringIO()):
            exporter.main()
        receipts=list(folder.rglob('publication.json'))
        self.assertEqual(len(receipts),1)
        receipt=json.loads(receipts[0].read_text(encoding='utf-8'))
        self.assertEqual(receipt['approval_manifest_hash'],digest(read_manifest(self.book)))
        self.assertEqual(set(receipt['artifacts']),{'fixture.epub'})
        self.assertEqual(receipt['status'],'EXPORTED')


class SourceNormalizationTests(unittest.TestCase):
    def test_anchor_content_and_duplicate_heading_mapping_are_preserved(self):
        paragraphs=extract_paragraphs('<div class="content">第1章 标题<br>第1章 标题<p>他说<a>不要走</a>。</p>（本章完）</div>')
        rows,mapping=normalize_paragraphs(paragraphs,1)
        self.assertEqual([r['source'] for r in rows],['第1章 标题','他说不要走。'])
        self.assertEqual(mapping['segment_map'][0]['raw_indices'],[1,2])
        source={'version':'bns-source-v2','book_id':'fixture','chapter':1,'title':'第1章 标题',
                'source_ref':'https://czbooks.net/n/s6p7bb/a','segments':rows,'paragraph_count':len(rows),'normalization':mapping}
        source['content_hash']=source_content_hash(source)
        source['package_hash']=digest(source)
        self.assertEqual(validate_source(source),rows)
        source['normalization']['segment_map'][1]['raw_indices']=[]
        source['package_hash']=digest({k:v for k,v in source.items() if k!='package_hash'})
        with self.assertRaises(ValueError): validate_source(source)

    def test_wrong_redirect_or_invalid_utf8_is_rejected(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def geturl(self): return 'https://czbooks.net/n/other/a'
            def read(self): return b'\xff'
        response=Response()
        with patch('native_oauth.source_adapters.urllib.request.urlopen',return_value=response):
            with self.assertRaises(ValueError): fetch_czbooks('https://czbooks.net/n/s6p7bb/a')
            response.geturl=lambda:'https://czbooks.net/n/s6p7bb/a'
            with self.assertRaises(UnicodeError): fetch_czbooks('https://czbooks.net/n/s6p7bb/a')
