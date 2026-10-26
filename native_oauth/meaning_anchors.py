"""Literal source spans requiring semantic attention, never automatic rewrites."""
import re

RULES = (
    ('negation_scope', r'(?:不甘(?:心)?|未必|並非|并非|不得不|不能不|未曾|從未|从未)',
     'Check the full clause and negation scope. 不甘 is unwillingness to accept, not acceptance; double negation may express necessity. Do not prescribe a Vietnamese word without context.'),
    ('royal_self_reference', r'孤(?=[，。！？、：「」“”\s]|曰|說|说|要|會|会|不|的|已|也)',
     'Check whether 孤 is a royal first-person self-reference in dialogue. It does not establish gender or the narrator\'s third-person pronoun.'),
    ('prospective_relation', r'(?:準|准)(?:嫂子|丈夫|妻子|女婿|兒媳|儿媳|媳婦|媳妇|公公|婆婆|岳父|岳母)',
     'Preserve that this relationship is prospective, and whose memory/viewpoint asserts it.'),
    ('elapsed_duration', r'(?:說|说|等|住|找|學|学|認識|认识|結婚|结婚)了(?:好|整整)?[幾几一二三四五六七八九十百兩两\d]+(?:年|個月|个月|天)',
     'Inspect elapsed duration versus a future date; retain tense/aspect and event scope.'),
    ('liking_or_habit', r'(?:喜歡|喜欢|習慣|习惯)(?:聞|闻|看|聽|听|吃|喝|用)?',
     'Keep liking distinct from being accustomed; do not infer emotional history.'),
    ('speech_volume', r'(?:低聲|低声|輕聲|轻声|小聲|小声)(?:說|说|道|問|问)',
     'Speech volume alone does not establish anger, gentleness or hostility.'),
    ('viewpoint_qualifier', r'(?:記憶[裡里中]|记忆[里中]|以為|以为|似乎|也許|也许|或許|或许|應該|应该|大概|可能)',
     'Preserve viewpoint/uncertainty rather than turn a belief into an objective fact.'),
    ('domain_frontier', r'前沿(?:物理|科學|科学|技術|技术)',
     'Read the academic/domain sense in context; do not confuse a scientific frontier with a romantic affinity.'),
    ('explicit_quantity', r'[一二三四五六七八九十百千萬万兩两\d]+(?:口煙|口烟|次|遍|步|天|年|個月|个月)',
     'Preserve the stated count, unit and scope; fluent Vietnamese must not turn two into several.'),
)


def source_anchors(segments):
    output = []
    for row in segments:
        for kind, pattern, instruction in RULES:
            for match in re.finditer(pattern, row['source']):
                output.append({'source_id': row['id'], 'kind': kind, 'start': match.start(),
                               'end': match.end(), 'source_quote': match.group(),
                               'review_instruction': instruction, 'authority': 'literal cue; not inferred fact'})
    return output


def semantic_guidance(segments, glossary):
    return {'version': 'source-meaning-guidance-1', 'source_anchors': source_anchors(segments),
            'lexical_suggestions': {key: value[0] for key, value in glossary.items() if value[1] != 'character_name'},
            'rules': ['Check whole source paragraphs; do not replace words automatically from these cues.',
                      'Do not add shape, emotion, force, motive or physical actions just to make prose vivid.',
                      'Understand idiomatic Vietnamese by its contextual meaning, not literal keywords.',
                      'Qualifiers, elapsed time, beliefs and who knows a fact remain tied to the original viewpoint.']}
