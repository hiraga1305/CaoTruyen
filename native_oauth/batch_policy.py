"""Preventive routing policies; failures regenerate scenes, never patch targets."""
import copy
import re
from semantic_gate import digest

VERSION='source-contract-v2'
LITERARY_DECODER_POLICY=(
    'Đọc toàn cảnh rồi diễn đạt lại bằng cấu trúc câu tiếng Việt, không thay từng từ Trung. '
    'Vị ngữ chỉ thái độ, ánh mắt và dẫn thoại phải thành câu hoàn chỉnh, có đối tượng '
    'hoặc mối liên hệ rõ với lời thoại trước; không để một cụm dịch từ điển treo trong câu. '
    'Thành ngữ/cụm cố định phải chọn nghĩa theo lập trường của nhân vật và ngữ cảnh; '
    'không đồng nhất thành ngữ gần giống nhau, không bỏ sắc thái để câu trơn hơn. '
    'Nhãn idiom của parser có thể gộp nhầm động từ dẫn thoại; nguyên câu Trung mới là chuẩn. '
    'Đọc lại toàn bản Việt như một truyện liền mạch trước khi xuất; giữ giọng kể và vai xưng hô '
    'cùng snapshot. Các ví dụ đã duyệt chỉ dạy văn phong, không cung cấp sự kiện cho cảnh mới.'
)
NUMBER=re.compile(r'([0-9]+(?:\.[0-9]+)?[万亿]?|[零〇一二三四五六七八九十百千万亿两]+)(元|块|件|克|公斤|斤|天|年|个月|小时)')
CLASSIFIER_POLICY=(
    'Phân biệt loại đơn vị với âm Hán Việt: 件 là đơn vị đếm đồ vật/sản phẩm; '
    'chỉ gọi là kiện hàng khi nguồn xác nhận đóng kiện hoặc bao gói. '
    '套/份/台/张/支/粒 phải chọn theo vật được đếm, không dịch máy móc âm Hán Việt. '
    'Đại lượng tiền chỉ đổi cách đọc số, giữ nguyên độ lớn và loại tiền có trong nguồn; '
    'không tự quy đổi sang đồng Việt Nam. Không làm tròn hoặc bỏ số. '
    'Giữ riêng khoản vay, người cho vay/người vay, khoản đã trả/khoản còn nợ. '
    'Không tự suy diễn vay, làm hồ sơ vay hay đảo nợ thành quỵt nợ/trốn nợ/lừa đảo '
    'khi nguồn chưa xác nhận hành vi không trả hoặc gian lận. '
    'Giữ ít nhất/hơn/tối đa, không/chưa/không còn và phạm vi thời gian của lời từ chối. '
    'Xưng hô đùa như 爹/爸爸 không tự tạo quan hệ huyết thống; đọc lời giải thích trong cảnh. '
    'Mỗi thoại phải khớp người nói, người nghe và vai vế theo trích nguồn, không theo bản nháp trước.'
)


def quantity_candidates(source):
    """Bind quantitative spans without pretending idioms/approximations are exact."""
    result=[]
    for match in NUMBER.finditer(source):
        context=source[max(0,match.start()-8):min(len(source),match.end()+8)]
        result.append({'source_quote':match.group(),'raw_number':match[1],'source_unit':match[2],
                       'local_context':context,'comparison_markers':[x for x in ('至少','不少于','不低于','多于','超过','至多','不超过') if x in context],
                       'authority':'Exact original span; inspect negation and scope before interpreting comparison markers'})
    return result


def apply_prevention(contract):
    result=copy.deepcopy(contract)
    result['preventive_policy']={'version':VERSION,'instructions':CLASSIFIER_POLICY,
         'quantities':[{'id':s['id'],'spans':quantity_candidates(s['source'])} for s in result['owned_segments']],
         'rule':'Interpret source-qualified constraints before drafting; no target patches or source substitution'}
    result['contract_hash']=digest({k:v for k,v in result.items() if k!='contract_hash'})
    return result


def bind_approved_style_seed(contract,evidence,ids):
    """Optional once-per-book editorial seed, never previous draft story truth."""
    from semantic_gate import evaluate
    if evaluate(evidence['package'],evidence['candidate'],evidence['reviews'],
                review_policy=evidence.get('review_policy'))['status']!='PASS':
        raise ValueError('Unapproved editorial examples')
    sources={s['id']:s['source'] for s in evidence['package']['segments']}
    targets={s['id']:s['text'] for s in evidence['candidate']['segments']}
    if not ids or len(ids)>8 or any(i not in sources for i in ids):raise ValueError('Invalid style seed ids')
    result=copy.deepcopy(contract)
    result['literary_decoder']={'version':'source-literary-decoder-v3','instructions':LITERARY_DECODER_POLICY,
             'examples':[{'source_id':i,'source':sources[i],'approved_target':targets[i]} for i in ids],
             'evidence_hash':digest(evidence),'authority':'Editorial examples only; new Chinese source determines all facts'}
    result['contract_hash']=digest({k:v for k,v in result.items() if k!='contract_hash'})
    return result


def next_route(failures,attempt=0):
    """Machine-readable action plan for a trusted checker, not a PASS oracle."""
    if type(attempt) is not int or attempt<0:raise ValueError('Invalid retry attempt')
    codes={f['kind'] for f in failures}
    if not codes:
        return {'action':'AWAIT_BOUNDARY_SEMANTIC_STYLE_GATE','publish':False}
    if attempt>=2:
        return {'action':'QUARANTINE','publish':False,'reason_codes':sorted(codes)}
    if codes & {'source_changed','stale_state','glossary_conflict'}:
        action='REBUILD_SOURCE_STATE_AND_INVALIDATE_DEPENDENT_SCENES'
    elif codes & {'referent','speaker','boundary','missing_context','memory_conflict'}:
        action='EXPAND_SOURCE_RETRIEVAL_AND_MERGE_DIALOGUE_SCENES'
    elif codes & {'number_unit','negation','meaning','genre_voice','grammar'}:
        action='REGENERATE_WHOLE_SCENE_WITH_PREVENTION_MEDIUM'
    else:
        action='RETRY_COMPLETE_SCENE_OR_QUARANTINE'
    return {'action':action,'publish':False,'model':'gemini-3.8-flash-medium',
            'worker_concurrency':1,'regenerate_scope':'whole affected scenes from original Chinese',
            'invalidate_scope':'all scenes bound to changed state/contract and downstream dependent commits',
            'attempt':attempt+1,'reason_codes':sorted(codes)}


def choose_model(contract):
    """Conservative source-risk routing; not a measured confidence estimator."""
    source='\n'.join(s['source'] for s in contract['owned_segments']+contract['neighbor_segments'])
    reasons=[]
    if any(t in source for t in ('贷款','小贷','借贷','原身','上线','以贷养贷')):
        reasons.append('domain_or_identity_polysemy')
    if any(s.get('idiom_candidates') for s in contract.get('parser_hints',[])):
        reasons.append('predicted_fixed_phrase_needs_contextual_decoding')
    if contract.get('context_capsule',{}).get('omitted_optional_entries',0):
        reasons.append('source_memory_budget_omissions')
    return {'model':'gemini-3.8-flash-medium' if reasons else 'gemini-3.8-flash-low',
            'risk_reasons':reasons,'basis':'Conservative source heuristics; medium does not certify meaning/style',
            'publish':False}
