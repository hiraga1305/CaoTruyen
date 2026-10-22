"""Conservative, source-grounded hints. These are not semantic approval.

Identity aliases are explicit editorial data, never inferred from equal Vietnamese
names. Attribution only recognizes a small set of local speech constructions;
everything else remains UNKNOWN for the translator and independent reviewer.
"""
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re

from native_oauth.scene_contract import EntityRecord

UNKNOWN = "UNKNOWN"
SAY = r"(?:說道|说道|問道|问道|回答|答道|回道|喊道|叫道|笑道|說|说|問|问)"
QUOTE_PAIRS = {'“': '”', '「': '」', '『': '』', '"': '"'}


@dataclass(frozen=True)
class QuoteSpan:
    begin: int
    finish: int

    def start(self):
        return self.begin

    def end(self):
        return self.finish


def quote_spans(text):
    """Complete outer quotes only; nested same-style Chinese quotes are common.
    Unclosed multi-paragraph quotations remain for semantic review.
    """
    stack, result, start = [], [], 0
    for pos, char in enumerate(text):
        if stack and char == stack[-1]:
            stack.pop()
            if not stack:
                result.append(QuoteSpan(start, pos + 1))
        elif char in QUOTE_PAIRS:
            if not stack:
                start = pos
            stack.append(QUOTE_PAIRS[char])
    return result


def entity_aliases(entity):
    return tuple(dict.fromkeys((entity.zh, *entity.aliases)))


def alias_index(entities):
    index = {}
    for entity in entities:
        for alias in entity_aliases(entity):
            if alias in index and index[alias] is not entity:
                raise ValueError("Ambiguous entity alias: " + alias)
            index[alias] = entity
    return index


def normalize_profile(book_id, entities, pronouns, lore):
    """Unify only declared identities; preserve surface titles independently."""
    data = json.loads(Path(__file__).with_name("semantic_profiles.json").read_text(encoding="utf-8"))
    configured = data.get(str(book_id), {}).get("entities", [])
    base = {e.zh: e for e in entities}
    for zh, vi in lore.get("characters", {}).items():
        if isinstance(vi, str) and zh not in base:
            base[zh] = EntityRecord(zh, vi, "N", "", "", "")
    normalized, consumed = [], set()
    for item in configured:
        aliases = tuple(item.get("aliases", []))
        names = (item["zh"], *aliases)
        seed = next((base[name] for name in names if name in base),
                    EntityRecord(item["zh"], item["vi"], "N", "", "", ""))
        normalized.append(replace(seed, zh=item["zh"], vi=item["vi"],
                                  entity_id=f"{book_id}:{item['id']}", aliases=aliases,
                                  surface_vi=item.get("surface_vi", {}),
                                  legacy_vi_variants=tuple(item.get("legacy_vi_variants", ())),
                                  narr_lock=item.get("narrator", seed.narr_lock),
                                  realm_title=item.get("role", ""),
                                  archetype=item.get("disposition", "")))
        consumed.update(names)
    for zh, entity in base.items():
        if zh not in consumed:
            stable = hashlib.sha256(zh.encode()).hexdigest()[:12]
            normalized.append(replace(entity, entity_id=entity.entity_id or f"{book_id}:{stable}", realm_title="", archetype=""))
    index = alias_index(normalized)
    rules = []
    for rule in pronouns:
        if rule.src_zh not in index or rule.dst_zh not in index:
            raise ValueError("Pronoun rule references an unknown identity")
        rule = replace(rule, src_zh=index[rule.src_zh].zh, dst_zh=index[rule.dst_zh].zh,
                       known_by=index[rule.known_by].zh if rule.known_by in index else rule.known_by,
                       tone="" if rule.scope == "editorial_default" else rule.tone)
        if rule.src_zh == rule.dst_zh:
            raise ValueError("Pronoun rule aliases collapse to the same person")
        if rule not in rules:
            rules.append(rule)
    # Include all glossary categories, but never treat biography/relations as terms.
    glossary = {}
    for category in ("terms", "factions_and_places", "cultivation_and_tech"):
        glossary.update({k: (v, category) for k, v in lore.get(category, {}).items() if isinstance(v, str)})
    for entity in normalized:
        for alias in entity_aliases(entity):
            glossary[alias] = (entity.surface_vi.get(alias, entity.vi), "character_name")
    return normalized, rules, glossary


def scoped_rules(rules, chapter, scene, source_text):
    result = []
    for rule in rules:
        if not (rule.valid_from_chapter <= chapter and
                (rule.valid_to_chapter is None or chapter <= rule.valid_to_chapter)):
            continue
        if rule.scene_id is not None and rule.scene_id != scene:
            continue
        if rule.scope != "editorial_default" and (not rule.evidence or rule.evidence not in source_text):
            continue
        result.append(rule)
    return result


def dialogue_cues(text, entities, source_before=""):
    index = alias_index(entities)
    if not index:
        names = r"(?!)"
    else:
        names = "(?:" + "|".join(re.escape(n) for n in sorted(index, key=lambda n: (-len(n), n))) + ")"
    # No crossing another name, punctuation, quote or speech verb to select a
    # distant protagonist. Missing or conflicting attribution always abstains.
    gap = rf"(?:(?!{names}|{SAY})[^。！？!?；;：:“”「」『』\"\n]){{0,14}}?"
    recipient = r"(?:對(?:著|着)?|对(?:著|着)?|向|跟(?!著|着))"
    direct = re.compile(rf"(?P<s>{names}){gap}{recipient}\s*(?P<d>{names}){gap}{SAY}")
    speaker_only = re.compile(rf"(?P<s>{names}){gap}{SAY}")

    def subject_position(fragment, match):
        if re.search(r"(?:對|对|向|跟|看|望|盯|朝|面對|面对|看向|望向|問|问)(?:著|着)?\s*$",
                     fragment[:match.start()]):
            return False
        return not fragment[match.end('s'):].startswith(('的', '之'))

    cues = []
    quotes = quote_spans(text)
    for qi, quote in enumerate(quotes):
        boundary = quotes[qi - 1].end() if qi else 0
        prefix = text[boundary:quote.start()]
        suffix = text[quote.end():quotes[qi + 1].start() if qi + 1 < len(quotes) else len(text)]
        # Only a directly preceding, unfinished attribution can cross paragraphs.
        inherited = ""
        if qi == 0 and not prefix.strip() and source_before:
            last_line = source_before.rstrip().splitlines()[-1]
            if re.search(r"[：:]\s*$", last_line) and not any(c in last_line for c in '“”「」『』"'):
                inherited = last_line
        # Prefix must end at this quote, not a separate completed sentence.
        before = re.split(r"[。！？!?；;]", inherited + prefix)[-1]
        # Post-quote evidence must begin here, not after a different sentence.
        after = re.split(r"[。！？!?；;]", suffix.lstrip("，, "))[0]
        candidates = []
        for side, fragment in (("prefix", before), ("suffix", after)):
            if re.search(r"(?:沒|没|沒有|没有|未|不|想|準備|准备|如果|假如|要是)\S{0,16}" + SAY, fragment):
                continue
            # A suffix ending in a colon introduces the *next* quotation.
            if side == "suffix" and re.search(r"[：:]\s*$", fragment):
                continue
            matches = list(direct.finditer(fragment))
            if matches:
                for match in matches:
                    if not subject_position(fragment, match):
                        continue
                    if side == "prefix" and fragment[match.end():].strip("：: "):
                        continue
                    if side == "suffix" and fragment[:match.start()].strip("，, "):
                        continue
                    candidates.append((index[match['s']].zh, index[match['d']].zh,
                                       match.group(), side))
            else:
                for match in speaker_only.finditer(fragment):
                    # An unnamed subject can speak TO a named person. Looking
                    # at/following someone also does not make them the speaker.
                    if not subject_position(fragment, match):
                        continue
                    if side == "prefix" and fragment[match.end():].strip("：: "):
                        continue
                    if side == "suffix" and fragment[:match.start()].strip("，, "):
                        continue
                    candidates.append((index[match['s']].zh, UNKNOWN, match.group(), side))
        speakers = {c[0] for c in candidates}
        speaker = next(iter(speakers)) if len(speakers) == 1 else UNKNOWN
        listeners = {c[1] for c in candidates if c[1] != UNKNOWN}
        listener = next(iter(listeners)) if speaker != UNKNOWN and len(listeners) == 1 else UNKNOWN
        if listener == speaker:
            listener = UNKNOWN
        cues.append({"quote_index": qi + 1, "start": quote.start(), "end": quote.end(),
                     "speaker": speaker, "listener": listener,
                     "speaker_id": index[speaker].entity_id if speaker in index else "",
                     "listener_id": index[listener].entity_id if listener in index else "",
                     "status": "EXPLICIT_LOCAL" if speaker != UNKNOWN else "UNRESOLVED",
                     "evidence": [{"text": c[2], "side": c[3]} for c in candidates],
                     "review_required": speaker == UNKNOWN or listener == UNKNOWN})
    return cues


def context_tail(paragraphs, limit=1600, count=4):
    """Whole source paragraphs only. Author notes stay labeled as source context;
    they cannot create attributions unless they contain an explicit construction.
    """
    selected, size = [], 0
    for paragraph in reversed(paragraphs):
        if size + len(paragraph) > limit or len(selected) >= count:
            break
        selected.insert(0, paragraph)
        size += len(paragraph)
    return "\n".join(selected)


def continuation_boundary(before, following):
    """Risk of separating an introduction/open quote from its continuation.

    This is only a local boundary heuristic, not scene segmentation or NLP.
    A hard budget can still force a boundary; read-only overlap remains required.
    """
    if not before:
        return False
    text = "\n".join(before)
    open_quote = any(text.count(left) > text.count(right)
                     for left, right in (("“", "”"), ("「", "」"), ("『", "』")))
    open_quote = open_quote or text.count('"') % 2 == 1
    return open_quote or (before[-1].rstrip().endswith(('：', ':'))
                          and following.lstrip().startswith(('“', '「', '『', '"')))
