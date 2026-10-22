"""Read-only legacy output triage. Never delete untranslated text or approve it."""
from dataclasses import dataclass, field, asdict
import json
from pathlib import Path
from native_oauth.quality_gate import CJK_PATTERN, URBAN_FALSE_FRIENDS
from native_oauth.chapter_integrity import inspect_chapter, atomic_json
import re


@dataclass
class ChapterAuditResult:
    chap_id: int
    raw_path: str
    total_paragraphs: int
    header_cleansed: bool = False
    cjk_cleared_count: int = 0
    patches_applied: list = field(default_factory=list)
    prophecy_clues_found: list = field(default_factory=list)
    is_gate_pass: bool = False
    findings: list = field(default_factory=list)
    scope: str = 'TRIAGE_ONLY_UNREVIEWED'


class UrbanAuditor:
    def __init__(self, book_dir='native_oauth/book_14713'):
        self.book_dir = Path(book_dir)
        self.output_dir = self.book_dir/'output_dich'
        self.sources_dir = self.book_dir/'sources'
        self.logs_dir = self.book_dir/'logs'

    def audit_and_heal_chapter(self, chap_id):
        # Historical method name retained for callers; this method never heals.
        path = self.output_dir/f'chuong_{chap_id:04d}.txt'
        text = path.read_text(encoding='utf-8')
        findings = []
        for match in CJK_PATTERN.finditer(text):
            findings.append({'kind':'untranslated_cjk', 'offset':match.start(),
                             'quote':match.group(), 'action':'REVIEW_SOURCE_AND_REGENERATE'})
        for pattern, code, suggestion, _ in URBAN_FALSE_FRIENDS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                findings.append({'kind':code, 'quote':match.group(),
                                 'severity':'WARNING', 'suggestion':suggestion})
        source = self.sources_dir/f'source_chapter_{chap_id:04d}.json'
        sidecar = self.output_dir/f'chuong_{chap_id:04d}.dich.json'
        if not source.exists() or not sidecar.exists():
            findings.append({'kind':'missing_source_or_alignment'})
        else:
            try:
                errors = inspect_chapter(json.loads(source.read_text(encoding='utf-8')),
                                         json.loads(sidecar.read_text(encoding='utf-8')), text)
                findings.extend({'kind':'integrity', 'detail':e} for e in errors)
            except (ValueError, KeyError, TypeError) as error:
                findings.append({'kind':'invalid_alignment', 'detail':str(error)})
        return ChapterAuditResult(chap_id, str(path), len([p for p in text.split('\n\n') if p.strip()]),
                                  findings=findings)

    def run_full_audit(self, total_chapters=50):
        results = [asdict(self.audit_and_heal_chapter(c)) for c in range(1, total_chapters+1)]
        summary = {'scope':'TRIAGE_ONLY_UNREVIEWED', 'total_chapters':total_chapters,
                   'all_chapters_gate_pass':False, 'chapter_breakdown':results,
                   'total_patches_applied':0, 'total_cjk_cleared':0}
        atomic_json(self.logs_dir/'urban_audit_report.json', summary)
        return summary


if __name__ == '__main__':
    print(json.dumps(UrbanAuditor().run_full_audit(), ensure_ascii=False))
