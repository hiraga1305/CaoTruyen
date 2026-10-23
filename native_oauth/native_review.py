"""Independent native review sessions, with no external approval dependency."""
from contextlib import contextmanager
import shutil
import json
import uuid
from pathlib import Path
from semantic_gate import review_prompt, write_json, validate_review, LITERARY_CHECKS
from native_oauth.session_monitor import get_session_monitor
from native_oauth.review_quotes import evidence_catalog


def install_agents(workspace):
    target = Path(workspace)/'.agents/agents'
    target.mkdir(parents=True, exist_ok=True)
    for profile in (Path(__file__).resolve().parents[1]/'.agents/agents').glob('novel-*.md'):
        shutil.copy2(profile, target/profile.name)


@contextmanager
def visible_stage(package, role):
    chapter = package['chapter']
    mon = get_session_monitor(str(package.get('book_id', 'native')),
                              package.get('book_title', package.get('title', 'Truyện')),
                              package.get('total_chapters', max(1, chapter)))
    mon.genre = package.get('genre', package.get('style_profile', {}).get('genre', 'Theo nguồn'))
    mon.chapter_range = package.get('chapter_range', package.get('draft_anchor',{}).get('chapter_range',str(chapter)))
    worker = role + '-' + uuid.uuid4().hex[:8]
    mon.record_worker_active(worker, chapter, (chapter - 1) // 5 + 1, message=role)
    print(mon.render_markdown_badge(), flush=True)
    try:
        yield
    except Exception:
        mon.record_stage_result(chapter, role, worker, 'BLOCKED')
        print(mon.render_markdown_badge(), flush=True)
        raise
    else:
        mon.record_stage_result(chapter, role, worker, 'STAGE_COMPLETE')
        print(mon.render_markdown_badge(), flush=True)


def run_independent_reviews(package, candidate, data, workspace, reviewer_model, auditor_model, timeout=420):
    # Import at call time to keep the stage transport mockable and avoid cycles.
    from native_oauth.pipeline_native import run_stage, NativeJSONSchemaError
    data, workspace = Path(data), Path(workspace)
    suffix = ('\nĐọc đủ mọi đoạn và biên cảnh/chương. Không đọc báo cáo của reviewer khác. '
                 'Kiểm xưng hô theo đúng người nói/nghe, lời nhại, độc thoại, người thứ ba và quan hệ tại cảnh. '
                 'Vai auditor kiểm thêm tiếng Việt tự nhiên, nhất quán tên/giọng và continuity. '
                 'Đánh giá tương đương nghĩa trong ngữ cảnh, chấp nhận hoán dụ/thành ngữ Việt hợp nghĩa; '
                 'không coi mọi khác biệt từ vựng hoặc việc dịch một từ viết tắt là lỗi. '
                 'Không sửa draft, không thêm dữ kiện. Include literary_checks: ' +
                 json.dumps(dict.fromkeys(LITERARY_CHECKS, True)) +
                 '. Return valid JSON; true means inspected, real defects still FAIL.')
    suffix += ('\nsource_quote/target_quote must be exact contiguous substrings of their supplied paragraph, '
                 'including original case and punctuation. Prefer a short meaningful quote from the middle '
                 'of a paragraph rather than copying all text. Every evidence quote must stay inside its assigned paragraph; '
                 'never invent an opening or closing quotation mark absent from this paragraph. '
                 'Do not normalize quotation marks or whitespace in evidence. '
                 'Use short meaningful exact quotes and one concise source-grounded reason per row; '
                 'do not duplicate full paragraphs in the report. Inspect every paragraph regardless of report brevity.')
    base_size = max(len(review_prompt(package,candidate,literary_first=first)+suffix) for first in (False,True))
    suffix += evidence_catalog(package, candidate, budget=max(0, min(18000, 117000-base_size)))
    if max(len(review_prompt(package,candidate,literary_first=first)+suffix) for first in (False,True)) > 120000:
        raise ValueError('Complete review protocol exceeds context budget')
    def review(role, model):
        role_protocol = review_prompt(package,candidate,literary_first=(role=='auditor'))+suffix
        schema_error = None
        for evidence_attempt in range(2):
            isolated = workspace / 'review_sessions' / (role + '_' + uuid.uuid4().hex)
            target = isolated / 'native_oauth/runs/chapter1'
            target.mkdir(parents=True)
            install_agents(isolated)
            write_json(target / 'source.json', package)
            for name in ('analysis.full.json', 'analysis.compact.json'):
                if (data / name).exists():
                    shutil.copy2(data / name, target / name)
            lookup = Path(__file__).with_name('analysis_lookup.py')
            shutil.copy2(lookup, isolated / 'native_oauth/analysis_lookup.py')
            current = role_protocol + ('\nYour prior response failed evidence schema validation: '+schema_error+
                '. Independently check the same frozen candidate again; provide exact quotes and do not infer a required verdict.'
                if schema_error else '')
            try:
                result = run_stage(target, isolated, role, model, current, role+'.json', timeout)
            except NativeJSONSchemaError as error:
                schema_error = str(error)
            else:
                try:
                    validate_review(package, candidate, result)
                    if role=='auditor':
                        checks=result.get('literary_checks',{})
                        if (not isinstance(checks,dict) or set(checks)!=set(LITERARY_CHECKS)
                                or any(value is not True for value in checks.values())):
                            raise ValueError('Missing explicit literary review dimensions')
                except (ValueError,KeyError,TypeError,AttributeError) as error:
                    schema_error = str(error)
                else:
                    return result
            write_json(isolated/'evidence_error.json', {'status':'BLOCKED','reason':schema_error})
            if evidence_attempt == 1:
                raise ValueError('Native review evidence failed twice: '+schema_error)
    # Isolated sessions, in stable role order. CLI shutdown proved unreliable
    # during concurrent full-chapter reviews, so completion takes priority.
    return [review('reviewer',reviewer_model),review('auditor',auditor_model)]
