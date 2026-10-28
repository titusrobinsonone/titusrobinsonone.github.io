"""Validate editable content, static file references and hosting boundaries."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import json
import re

ROOT=Path(__file__).resolve().parents[1]; DOCS=ROOT/'docs'
projects=json.loads((DOCS/'projects.json').read_text());site=json.loads((DOCS/'site.json').read_text())
assert isinstance(site.get('name'),str) and site['name'].strip(),'Missing portfolio name'
assert len({p['id'] for p in projects})==len(projects),'Duplicate project ID'
required={'id','number','title','name','category','summary','question','thumbnail','tags','proof','source','download','problem','approach','finding','validation','limitations','run'}
errors=[]

def check_link(value,base):
    url=urlsplit(value)
    if url.scheme or url.netloc:return
    if not url.path:return
    target=(DOCS/unquote(url.path.lstrip('/'))) if url.path.startswith('/') else base/unquote(url.path)
    if target.is_dir():target=target/'index.html'
    if not target.exists():errors.append(f'Missing local target: {target.relative_to(ROOT)}')

for p in projects:
    if required-set(p):errors.append(f'{p.get("id")}: missing {required-set(p)}')
    if not re.fullmatch('[a-z0-9-]+',p['id']):errors.append('Unsafe project ID')
    for key in ['thumbnail','download','demo','data']:
        if p.get(key):check_link(p[key],DOCS)

class Links(HTMLParser):
    def __init__(self,base):super().__init__();self.base=base
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('src','href') and value:check_link(value,self.base)

for f in DOCS.rglob('*.html'):
    if f.name.startswith('qa-'):continue
    parser=Links(f.parent);parser.feed(f.read_text())
for f in DOCS.rglob('*'):
    if f.is_file() and f.suffix in {'.html','.js','.css','.json','.md'} and not f.name.startswith('qa-'):
        if re.search(r'https?://[^\s"<>)]*chatgpt\.',f.read_text()):errors.append(f'Non-GitHub hosting link in {f.name}')
if errors:raise SystemExit('\n'.join(errors))
print(f'Validated {len(projects)} project entries, static local links and GitHub hosting boundaries.')
