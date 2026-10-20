"""Repair only unescaped quote characters in single-line JSON text fields.

No story word is removed/replaced. Missing content, commas or broken schema are
not recovered. Original malformed artifact is preserved and repair is recorded.
"""
import json
import re
from pathlib import Path


def escape_unescaped_quotes(value):
    result=[]
    for i,char in enumerate(value):
        preceding=0
        j=i-1
        while j>=0 and value[j]=='\\':
            preceding+=1
            j-=1
        if char=='"' and preceding%2==0:
            result.append('\\')
        result.append(char)
    return ''.join(result)


def repair_text_fields(text):
    try:
        return json.loads(text),False
    except json.JSONDecodeError:
        pass
    lines=[]
    changed=False
    for line in text.splitlines():
        match=re.fullmatch(r'(\s*"text"\s*:\s*)"(.*)"(,?\s*)',line)
        if match:
            try:
                json.loads('"'+match[2]+'"')
            except json.JSONDecodeError:
                line=match[1]+'"'+escape_unescaped_quotes(match[2])+'"'+match[3]
                changed=True
        lines.append(line)
    payload=json.loads('\n'.join(lines))
    if not changed or not isinstance(payload,dict) or not isinstance(payload.get('segments'),list):
        raise ValueError('Cannot safely repair this artifact')
    return payload,True
