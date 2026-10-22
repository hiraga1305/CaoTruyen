"""Independent native review sessions, with no external approval dependency."""
from contextlib import contextmanager
import shutil
import json
import uuid
from pathlib import Path
from semantic_gate import review_prompt, write_json, LITERARY_CHECKS
from native_oauth.session_monitor import get_session_monitor


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
    mon.chapter_range = str(chapter)
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
    from native_oauth.pipeline_native import run_stage
    data, workspace = Path(data), Path(workspace)
    protocol = review_prompt(package, candidate)
    protocol += ('\nĐọc đủ mọi đoạn và biên cảnh/chương. Không đọc báo cáo của reviewer khác. '
                 'Kiểm xưng hô theo đúng người nói/nghe, lời nhại, độc thoại, người thứ ba và quan hệ tại cảnh. '
                 'Vai auditor kiểm thêm tiếng Việt tự nhiên, nhất quán tên/giọng và continuity. '
                 'Không sửa draft, không thêm dữ kiện. Include literary_checks: ' +
                 json.dumps(dict.fromkeys(LITERARY_CHECKS, True)) +
                 '. Return valid JSON; true means inspected, real defects still FAIL.')
    if len(protocol) > 120000:
        raise ValueError('Complete review protocol exceeds context budget')
    reviews = []
    for role, model in (('reviewer', reviewer_model), ('auditor', auditor_model)):
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
        reviews.append(run_stage(target, isolated, role, model, protocol, role + '.json', timeout))
    return reviews
