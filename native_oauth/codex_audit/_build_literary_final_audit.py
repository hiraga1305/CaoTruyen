import json
import sys
import hashlib
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT))
from semantic_gate import digest, CHECKS, validate_review, validate_package, mechanical_findings

RUN = ROOT / 'native_oauth/pilot_workspace/native_oauth/runs/chapter1'
source_path = RUN / 'source.json'
old_path = RUN / 'draft.json'
new_path = OUT / 'draft.gpt_edited.json'
paths = [source_path, old_path, new_path]
before_file_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
source = json.loads(source_path.read_text(encoding='utf-8'))
old = json.loads(old_path.read_text(encoding='utf-8'))
new = json.loads(new_path.read_text(encoding='utf-8'))
prior = json.loads((OUT / 'literary_review.json').read_text(encoding='utf-8'))
assert prior['package_hash'] == source['package_hash']
assert prior['candidate_hash'] == digest(old)
validate_package(source)
assert not mechanical_findings(source, new)
validate_review(source, old, prior)

# Đối chiếu lại 19 đoạn thay đổi với nguyên văn. Các nhận xét sau viết riêng cho câu mới.
changed_reasons = {
    5: 'Đã bỏ vị trí túi không có nguồn; đủ cất điện thoại, hít sâu, nhắm mắt và chờ, giữ SMS là SMS.',
    9: 'Lời chào “Em chào ba thầy cô” đúng cú pháp/người nói; đủ nụ cười đã luyện, ba giám khảo và Trường cấp hai Đông Dương.',
    11: '“Quý trường” đúng kính xưng 贵校; đủ lịch sử, nền tảng, nguồn lực dạy học và nhân tài xã hội, không còn đổi thành trường của người nói.',
    14: '“Điểm tối đa ở tất cả các môn” đúng 全科满分; giữ nhất trường và lý do được giới thiệu.',
    19: 'Bổ sung “tốt nghiệp” đúng 毕业生; đủ từ tiểu học, trung bình không quá hai tiếng và mức khái quát cơ bản không ngủ của các khóa xuất sắc.',
    37: '“Sọt rác giấy” đúng 纸篓; hành động ném và chen cùng hàng trăm hồ sơ dự phòng khôi phục cú châm biếm, không thêm phán xét.',
    43: '“Chất tăng cường trí não” đúng 促智剂; giữ thêm vào nước uống, luôn tập trung cấp năm và cùng lượt thoại tuyển sinh.',
    44: '“Từ 900 gram ... trở lên” giữ biên gồm 900; “ít nhất gấp mười lần ban đầu” giữ tỷ lệ không cộng thêm mười lần; đủ thuốc ngưu yêu và cấp phát hằng ngày.',
    65: 'Khoản tiền dự phòng trị số 5.000 là đúng 五千; không tự thêm đơn vị hay tỷ giá; giữ SMS giải ngân trong mười giây.',
    66: '“Cho vay nhỏ lẻ” đúng loại 小贷, không còn gán mục đích vay tiêu dùng; câu hỏi quảng cáo giữ nguyên giọng ngờ vực.',
    90: '“Được mọi người quý mến” đúng 好人缘, đủ chăm chỉ và thể hiện xuất sắc ở lớp luyện thi; không còn gán kỹ năng giao tiếp.',
    103: 'Hai ba nghìn, bảy tám nghìn và hai mươi nghìn đúng 两三千、七八千、两万; giữ con bảo mẹ chuyển và lời giải thích phí thuê Thiên Linh Căn, không quy đổi sang VND.',
    105: '“Phụ phí học tập” đúng 学杂费, đủ học phí/thuốc/các khoản khác; mẹ mừng, tự hào về nỗ lực/tài năng và nhận lời ngay.',
    111: 'Giữ hơn một năm, không có miễn phí/ưu ái/quà tặng như lời con kể và toàn bộ tiền từ cậu vay các nền tảng; câu có thể gọn thêm nhưng đã rõ các lời biện hộ bị phủ nhận.',
    120: '“Mọi công sức trước đây ... đổ sông đổ biển” đúng 前功尽弃; giữ không được ngừng thuốc và đạo tâm thụt lùi, xưng mẹ/con đúng.',
    122: 'Phân biệt thẻ lớp luyện thi với thầy ở trường chính khóa, đúng 学校老师; giữ phải nạp và nếu không thì không hiểu công pháp.',
    149: 'Đã bỏ dấu phẩy tách chủ-vị, “mình” liền giọng người xuyên việt; giữ đã thành Trương Vũ của thế giới khác, không thêm chuyện nói thành tiếng.',
    162: 'Đã bỏ hành động thở dài không có nguồn; ngồi phịch xuống giường trong bất lực đúng 有些无奈地坐倒.',
    177: 'Giữ trước cấp ba vay học thêm, sau vào Tung Dương muốn bắt kịp, vay mới trả cũ, dùng thuốc và học thêm, ép tiềm năng; kết quả tăng nợ và vắt cạn tiềm năng đúng trình tự/nhân quả.',
}

changed_ids = []
unchanged_ids = []
rows = []
for num, (s, d_old, d_new, previous_row) in enumerate(zip(source['segments'], old['segments'], new['segments'], prior['segments']), 1):
    assert s['id'] == d_old['id'] == d_new['id'] == previous_row['id']
    old_bytes, new_bytes = d_old['text'].encode('utf-8'), d_new['text'].encode('utf-8')
    changed = old_bytes != new_bytes
    if changed:
        assert num in changed_reasons, f'Unexpected changed paragraph {num}'
        changed_ids.append(s['id'])
        reason = changed_reasons[num]
    else:
        assert num not in changed_reasons
        assert previous_row['verdict'] == 'PASS', f'Unfixed prior issue {s["id"]}'
        # UTF-8 bytes của cả object đoạn cũng phải giữ nguyên, không chỉ text.
        assert json.dumps(d_old, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8') == json.dumps(d_new, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        unchanged_ids.append(s['id'])
        reason = previous_row['reason'] + ' Nội dung UTF-8 khớp bản đã audit, không phát hiện mâu thuẫn do 19 đoạn sửa.'
    rows.append({'id': s['id'], 'verdict': 'PASS', 'source_quote': s['source'],
                 'target_quote': d_new['text'], 'reason': reason})

assert len(source['segments']) == len(old['segments']) == len(new['segments']) == len(prior['segments']) == len(rows) == 192
assert len(changed_ids) == 19 and len(unchanged_ids) == 173
assert {int(s[-4:]) for s in changed_ids} == set(changed_reasons)

review = {
    'package_hash': source['package_hash'], 'candidate_hash': digest(new),
    'verdict': 'PASS', 'checks': {name: True for name in CHECKS},
    'literary_checks': {name: True for name in ['natural_vietnamese', 'spelling_grammar', 'genre_voice', 'address_consistency', 'dialogue_format']},
    'segments': rows, 'issues': [], 'model': 'codex/gpt-inherited',
    'identity_basis': 'codex_subagent', 'agent_session': '/root/gpt_literary_audit',
    'scope': 'Independent local source-bound semantic and literary re-audit; 19 changed paragraphs reread against source, 173 paragraphs verified UTF-8 byte-identical to independently audited text. Not official BNS certification.',
    'verification': {'prior_candidate_hash': digest(old), 'changed_count': 19, 'unchanged_utf8_count': 173,
                     'changed_ids': changed_ids, 'unchanged_ids': unchanged_ids},
    'independence': 'No peer reviews or semantic_findings read; no model API/OAuth; source and both candidates left untouched.',
}
validate_review(source, new, review)
(OUT / 'literary_review.final.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

lines = [
    '# Re-audit độc lập bản đã sửa – Chương 1', '',
    '**PASS** cho đúng bản `draft.gpt_edited.json` có hash bên dưới. Không còn lỗi chắc chắn trong 19 đoạn sửa sau khi đối chiếu lại với nguyên văn. 173 đoạn còn lại được xác nhận byte-identical ở nội dung UTF-8 và object đoạn với bản đã audit độc lập; giữ kết luận PASS từng đoạn sau khi kiểm mạch nối với các câu mới.', '',
    f'- Source package hash: `{source["package_hash"]}`',
    f'- Candidate mới: `{digest(new)}`',
    f'- Candidate trước: `{digest(old)}`',
    '- Agent: `/root/gpt_literary_audit`; model `codex/gpt-inherited`; identity basis `codex_subagent`.',
    '- Bao phủ 192 đoạn đúng id/thứ tự; tám chiều ngữ nghĩa và năm chiều văn phong đều đã kiểm. Các cờ true xác nhận đã kiểm, không phải bảo đảm tuyệt đối không có lỗi.',
    '- Không đọc peer reviews, auditor files của người khác hoặc semantic_findings; không dùng model API/OAuth; không sửa bản truyện.',
    '- Đây là phán quyết biên tập cục bộ, không phải chứng nhận/phê duyệt chính thức BNS.', '',
    '## Đối chiếu lại 19 đoạn thay đổi', '',
]
for sid in changed_ids:
    num = int(sid[-4:])
    lines.extend([f'### {sid} — PASS', '',
                  f'- Nguyên văn: {source["segments"][num-1]["source"]}',
                  f'- Bản mới: {new["segments"][num-1]["text"]}',
                  f'- Kết quả: {changed_reasons[num]}', ''])
lines.extend([
    '## Mạch văn, xưng hô và lựa chọn tùy chọn', '',
    'Các câu mới nối đúng mạch phỏng vấn → lớp luyện thi → vay nợ → mẹ rời nhà → người xuyên việt tỉnh dậy → ký ức nợ và mất điện. p0019 thêm tốt nghiệp đúng nguồn; p0037 khôi phục sọt rác không làm đổi cảnh; p0103 hai mươi nghìn đúng trị số, không mặc định quy đổi VND; p0177 giữ cả dùng thuốc và học thêm cùng vòng vay mới trả khoản cũ.', '',
    'Mẹ/con trong gia đình, em/thầy cô trong lần phỏng vấn đầu và bạn/chúng tôi trong lời chào hàng của các trường khác vẫn hợp cảnh. Anh ta ở giai đoạn tỉnh lại trước nhận diện, rồi cậu sau khi hòa ký ức học sinh có căn cứ. p0149 dùng mình liền giọng tự sự hiện đại. p0186 vẫn dùng ta trong câu tự nói giận dữ: có thể thống nhất thành mình, nhưng riêng biến thể này chưa đủ căn cứ để reject và không chuyển ngôi/người nói.', '',
    'Giữ châm biếm khô, không thêm hào khí, lời giảng đạo hay hành động không có nguồn. Tên và thuật ngữ khóa trong các đoạn sửa đúng; số/biên so sánh, phủ định, điều kiện, thời gian và nhân quả được kiểm. Không dùng PASS để chứng thực nội dung quảng cáo của lớp luyện thi là sự thật.', '',
    'SMS đầu chương và thoại dùng ngoặc theo nguồn; SMS mẹ về sau có nhãn Mẹ; một lượt thoại kéo qua p0042–p0047 vẫn mở/đóng đúng. Các dòng tự hỏi/nhớ nguồn đặt trong ngoặc không được bản mới tự thêm nói thành tiếng. Không báo lỗi format chỉ vì nguồn có nhiều hình thức thể hiện.', '',
    'Các chỉnh tùy chọn còn có thể thực hiện: p0010 Tại sao em thay Em tại sao; p0016 hỏi bâng quơ thay tùy tiện hỏi; p0080 kiến thức chung thay giáo dục đại cương; p0124 làm gọn câu ba tháng; p0154 hai chiếc cúc đen thay hai cúc nút đen; p0169 Ông đây là học bá cơ đấy; p0175 mở mục tin nhắn thay lật hộp tin nhắn. Đây là gợi ý nhuận sắc, không phải lỗi nghĩa chắc chắn để chặn bản hiện tại.', '',
    'p0111 đã nêu rõ không có các chuyện miễn phí/ưu ái/quà tặng như lời nhân vật kể và toàn bộ tiền là khoản vay. Nếu muốn câu cân đối hơn có thể làm rõ cậu được ưu ái trong kết cấu liệt kê, nhưng câu hiện tại không còn gán trực tiếp khoản tiền được trân trọng; không báo lỗi bắt buộc.', '',
    '173 đoạn byte-identical không có nghĩa nguyên file JSON byte-identical: file mới khác do 19 câu và metadata/định dạng có thể khác. Phép kiểm ở đây so nội dung text UTF-8 và serialization canonical của từng object đoạn, đủ để xác nhận các đoạn còn lại không bị biên tập.', '',
    'Báo cáo chỉ có hiệu lực với candidate hash đã ghi. Nếu chỉnh tiếp phải kiểm hash và các đoạn bị thay đổi một lần nữa.', ''
])
(OUT / 'literary_findings.final.md').write_text('\n'.join(lines), encoding='utf-8')

after_file_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
assert before_file_hashes == after_file_hashes, 'Input was changed during final audit'
print(json.dumps({'verdict': 'PASS', 'rows': len(rows), 'changed': len(changed_ids),
                  'unchanged_utf8': len(unchanged_ids), 'package_hash': source['package_hash'],
                  'candidate_hash': digest(new), 'schema_validation': 'PASS',
                  'input_files_untouched': before_file_hashes == after_file_hashes}, ensure_ascii=False))
