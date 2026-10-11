"""Compare an edited HTML review with the frozen original. Does not modify the app."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

VOID_TAGS={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
class CopyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.fields={}
        self.current=None
        self.depth=0
        self.blocks=set()
    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        attrs=dict(attrs)
        block=attrs.get('data-block-id')
        self.stack.append(block)
        if block:
            self.blocks.add(block)
        field=attrs.get('data-copy-id')
        if field:
            if field in self.fields:
                raise ValueError('Duplicate editable field: '+field)
            self.current=field
            self.depth=len(self.stack)
            self.fields[field]={'text':'','block':next((b for b in reversed(self.stack) if b),None)}
    def handle_data(self, data):
        if self.current:
            self.fields[self.current]['text']+=data
    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if self.current and len(self.stack)==self.depth:
            self.current=None
        if self.stack:
            self.stack.pop()

def compare(edited, baseline_path=None):
    root=Path(__file__).resolve().parent
    baseline_path=Path(baseline_path or root/'baseline.json')
    baseline=json.loads(baseline_path.read_text(encoding='utf-8-sig'))
    original=root/'original.html'
    if hashlib.sha256(original.read_bytes()).hexdigest()!=baseline['original_html_sha256']:
        raise ValueError('Original review changed; cannot establish a reliable comparison')
    parser=CopyParser()
    parser.feed(Path(edited).read_text(encoding='utf-8-sig'))
    for value in parser.fields.values():
        value['text']=re.sub(r'\s+',' ',value['text']).strip()
    removed={}
    removed_fields=[]
    changed=[]
    policy=json.loads((root / "removal_policy.json").read_text(encoding="utf-8"))
    block_headings=policy["block_headings"]
    originals=baseline['fields']
    for field,before in originals.items():
        after=parser.fields.get(field)
        marked=after is None or not after['text'] or (after['text'].startswith('(') and after['text'].endswith(')'))
        if marked:
            if field in block_headings:
                removed.setdefault(block_headings[field],[]).append(field)
            else:
                removed_fields.append({'field_id':field,'block_id':before['block'],'before':before['text']})
        elif before['text']!=after['text']:
            changed.append({'field_id':field,'block_id':before['block'],
                            'before':before['text'],'after':after['text']})
    return {'schema_version':'motomedic-ui-copy-diff-v2',
            'edited_file':str(Path(edited).resolve()),
            'original_html_sha256':baseline['original_html_sha256'],
            'edited_html_sha256':hashlib.sha256(Path(edited).read_bytes()).hexdigest(),
            'remove_blocks':[{'block_id':block,'marked_fields':fields} for block,fields in sorted(removed.items())],
            'remove_fields':[item for item in removed_fields if item['block_id'] not in removed],
            'text_changes':[item for item in changed if item['block_id'] not in removed],
            'unmapped_fields':sorted(set(parser.fields)-set(originals)),
            'app_modified':False,'github_pushed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('edited_html',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    result=compare(args.edited_html)
    serialized=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(serialized,encoding='utf-8')
    print(serialized)
