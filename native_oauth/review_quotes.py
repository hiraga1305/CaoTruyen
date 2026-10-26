"""Deterministic verbatim evidence choices; reviewers still decide meaning/verdict."""
import json


def quote_choices(text, width):
    starts = (0, max(0, (len(text)-width)//2), max(0, len(text)-width))
    return {str(i): text[start:start+width] for i, start in enumerate(starts)}


def resolve_quote(row, key, text):
    ref = key + '_ref'
    if ref not in row:
        return row.get(key)
    choices = quote_choices(text, 24 if key == 'source_quote' else 48)
    if not isinstance(row[ref], str) or row[ref] not in choices:
        raise ValueError('Invalid evidence reference: ' + ref)
    quote = choices[row[ref]]
    if key in row and row[key] != quote:
        raise ValueError('Conflicting literal quote and evidence reference')
    return quote


def evidence_catalog(package, candidate, budget=36000):
    rows = [{'id': raw['id'], 'source': quote_choices(raw['source'], 24),
             'target': quote_choices(target['text'], 48)}
            for raw, target in zip(package['segments'], candidate['segments'])]
    text = json.dumps(rows, ensure_ascii=False, separators=(',', ':'))
    if len(text) > budget:
        return ''
    return ('\nVERBATIM_EVIDENCE_CHOICES:\n' + text +
            '\nPrefer source_quote_ref and target_quote_ref (string 0, 1 or 2) from the assigned ID. '
            'These select exact source/draft spans; they are not findings or approval. '
            'A different exact literal quote remains allowed. Never use ellipses to join spans. '
            'Inspect the WHOLE paragraph, not just these excerpts, and explain your own verdict.')
