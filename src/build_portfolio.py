"""Regenerate Titus Robinson's synthetic analytical outputs and source bundles.

No website build is required for content edits. This script is only for data,
chart covers and downloadable bundles. Python 3.10+; optional PNG cover uses Pillow.
"""
from __future__ import annotations
import argparse
import ast
import html
import json
import zipfile
from pathlib import Path
import inventory_lab
import revenue_forensics
import experiment_studio

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'docs/assets'
SOURCE=ROOT/'src'


def svg_frame(bg,fg,title,subtitle,body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="760" height="500" viewBox="0 0 760 500"><rect width="760" height="500" fill="{bg}"/><text x="44" y="50" fill="{fg}" font-family="Arial,sans-serif" font-size="13" letter-spacing="2">{title}</text><text x="44" y="104" fill="{fg}" font-family="Georgia,serif" font-size="35">{subtitle}</text>{body}<text x="44" y="466" fill="{fg}" opacity=".65" font-family="Arial,sans-serif" font-size="12">TITUS ROBINSON  /  SYNTHETIC PORTFOLIO STUDY</text></svg>'''


def covers(inventory,revenue,experiment):
    selected=next(s for s in inventory['scenarios'] if s['policy']=='seasonal' and s['leadDays']==7 and s['buffer']==1.645)
    trace=selected['skus'][0]['trace'][-42:]; maximum=max(max(r['demand'],r['forecast']) for r in trace)*1.15
    x=lambda i:50+i/41*658; y=lambda v:355-v/maximum*160
    body='<text x="44" y="165" fill="#b4cfda" font-family="Arial" font-size="14">DEMAND VS FORECAST · SKU-01</text>'
    for i in range(4):body+=f'<line x1="45" y1="{205+i*50}" x2="712" y2="{205+i*50}" stroke="#ffffff" opacity=".12"/>'
    for key,color in [('demand','#d4e5de'),('forecast','#c6a76b')]:
        points=' '.join(f'{x(i):.1f},{y(r[key]):.1f}' for i,r in enumerate(trace))
        body+=f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3.5"/>'
    body+='<text x="44" y="413" fill="#dce8e9" font-family="Arial" font-size="15">12 SKUs   /   24 scenarios   /   140 test days</text>'
    (ASSETS/'inventory-cover.svg').write_text(svg_frame('#203b46','#edf3f3','DEMAND &amp; INVENTORY','The service / stock trade-off.',body))
    end=revenue['meta']['end']; closing=sum(r['closing'] for r in revenue['bridges'] if r['month']==end)/100
    body=f'<text x="44" y="168" fill="#3e6656" font-family="Georgia" font-size="48">${closing:,.0f}</text><text x="290" y="164" fill="#66816c" font-family="Arial" font-size="12">CLOSING MRR · SEP 2026</text>'
    cohorts=sorted({r['cohort'] for r in revenue['cohorts']})[:7]
    for i,cohort in enumerate(cohorts):
        rows=[r for r in revenue['cohorts'] if r['cohort']==cohort]
        base=sum(r['original_customers'] for r in rows if r['month']==cohort)
        body+=f'<text x="44" y="{220+i*27}" fill="#69806b" font-family="Arial" font-size="11">{cohort}</text>'
        for j,month in enumerate(sorted({r['month'] for r in rows})[:12]):
            rate=sum(r['active_customers'] for r in rows if r['month']==month)/base
            body+=f'<rect x="{121+j*47}" y="{205+i*27}" width="41" height="21" fill="#3e6656" opacity="{.12+rate*.8:.3f}"/>'
    body+='<text x="44" y="426" fill="#577360" font-family="Arial" font-size="13">Cohort retention  /  360 accounts  /  0¢ reconciliation residual</text>'
    (ASSETS/'revenue-cover.svg').write_text(svg_frame('#e8eee1','#2f523f','SUBSCRIPTION REVENUE','Every movement, explained.',body))
    balanced=next(s for s in experiment['scenarios'] if s['id']=='balanced'); c=balanced['conversion']
    x=lambda v:80+(v+.005)/.025*610
    body=f'<text x="44" y="175" fill="#5d5878" font-family="Georgia" font-size="55">+{c["delta"]*100:.2f} pp</text><text x="350" y="170" fill="#7d7894" font-family="Arial" font-size="12">OBSERVED CONVERSION LIFT</text>'
    for t in [0,.005,.01,.015,.02]:
        body+=f'<line x1="{x(t)}" y1="210" x2="{x(t)}" y2="335" stroke="#d6d2e0"/><text x="{x(t)}" y="360" text-anchor="middle" fill="#7c7690" font-family="Arial" font-size="12">{t*100:.1f} pp</text>'
    body+=f'<line x1="{x(.002)}" y1="205" x2="{x(.002)}" y2="338" stroke="#b99c60" stroke-dasharray="6 5" stroke-width="2"/><line x1="{x(c["lower"])}" y1="270" x2="{x(c["upper"])}" y2="270" stroke="#62597f" stroke-width="7"/><circle cx="{x(c["delta"])}" cy="270" r="11" fill="#4f476c"/>'
    body+='<text x="44" y="413" fill="#665e80" font-family="Arial" font-size="14">95% interval  /  Practical lift  /  Allocation &amp; error gates</text>'
    (ASSETS/'experiment-cover.svg').write_text(svg_frame('#eeeaf3','#4f476c','EXPERIMENT DECISIONS','Is the evidence enough?',body))


def png_cover():
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new('RGB',(1200,630),'#fafaf7');draw=ImageDraw.Draw(image)
    sans='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';serif='/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'
    def text(x,y,value,size=20,color='#253d31',font=sans):draw.text((x,y),value,font=ImageFont.truetype(font,size),fill=color)
    text(55,35,'TITUS ROBINSON',25);text(55,78,'DATA  /  DECISIONS  /  AUTOMATION',13,'#6a786b')
    draw.line((55,120,1145,120),fill='#dbe1d6',width=2)
    text(55,156,'Good analysis makes the',48,font=serif);text(55,214,'next decision clearer.',48,font=serif)
    panels=[('#203b46','#e4eeeb','INVENTORY','Service / stock'),('#e8eee1','#365642','REVENUE','Every dollar explained'),('#eeeaf3','#5a507a','EXPERIMENTS','Evidence before action')]
    for i,(bg,fg,small,big) in enumerate(panels):
        left=55+i*370;draw.rectangle((left,325,left+350,535),fill=bg);text(left+22,346,small,13,fg);text(left+22,379,big,20,fg)
        for j,h in enumerate([37,58,43,76,65,88,74,100]):draw.rectangle((left+22+j*38,508-h,left+44+j*38,508),fill=fg)
    text(55,574,'5 practical projects  ·  Working demos  ·  Reproducible Python & SQL',20,'#667164')
    image.save(ASSETS/'portfolio-cover.png',optimize=True)


def bundles(projects):
    tests=(SOURCE/'test_portfolio_projects.py').read_text(); tree=ast.parse(tests)
    mapping={
        'inventory':(['inventory_lab.py'],['inventory-demand.csv','inventory-data.json'],'InventoryTests','import copy\nimport inventory_lab as inv'),
        'revenue':(['revenue_forensics.py','revenue_model.sql'],['revenue-events.csv','revenue-rejected.csv','revenue-bridge.csv','revenue-data.json'],'RevenueTests','import revenue_forensics as rev'),
        'experiment':(['experiment_studio.py'],['experiment-users.csv','experiment-data.json'],'ExperimentTests','import math\nimport experiment_studio as exp')}
    for key,(sources,data,class_name,imports) in mapping.items():
        p=next(p for p in projects if p['id']==key)
        readme=f'# {p["name"]}\n\nPortfolio owner and maintainer: **Titus Robinson**. Independent, AI-assisted portfolio implementation, created October 2026. All bundled inputs and results are synthetic.\n\n{p["problem"]}\n\n## Run\n\nPython 3.10+; no third-party packages.\n\n```bash\npython {sources[0]} --output output\npython -m unittest discover -s tests -v\n```\n\nUse `--input data/{data[0]}` to run the included source CSV. Keep output separate from input. The Python and SQL files can also be adapted to your own inputs; check their schema and validation rules first.\n\n## Method\n\n'+''.join(f'- {x}\n' for x in p['approach'])+f'\n## Example finding\n\n{p["finding"]}\n\n## Limitations\n\n{p["limitations"]}\n\n## Links\n\n- [Interactive case study](https://titusrobinsonone.github.io/project.html?id={key})\n- [Full portfolio repository](https://github.com/titusrobinsonone/titusrobinsonone.github.io)\n'
        if p['methods']:readme+='\n## Method references\n\n'+''.join(f'- [{x["label"]}]({x["url"]})\n' for x in p['methods'])
        (SOURCE/f'{key.upper()}_README.md').write_text(readme.replace(f'python {sources[0]}',f'python src/{sources[0]}').replace('`--input data/','`--input docs/assets/').replace('python -m unittest discover -s tests -v',"python -m unittest discover -s src -p 'test_portfolio_projects.py' -v"))
        selected=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==class_name)
        standalone='import unittest\nimport sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parents[1]))\n'+imports+'\n\n'+ast.get_source_segment(tests,selected)+'\n\nif __name__=="__main__": unittest.main()\n'
        with zipfile.ZipFile(ASSETS/f'{key}-project.zip','w',zipfile.ZIP_DEFLATED) as z:
            for name in sources:z.write(SOURCE/name,name)
            for name in data:z.write(ASSETS/name,'data/'+name)
            z.writestr('README.md',readme);z.writestr(f'tests/test_{key}.py',standalone)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reuse-data',action='store_true');parser.add_argument('--png',action='store_true');args=parser.parse_args()
    ASSETS.mkdir(parents=True,exist_ok=True)
    if args.reuse_data: datasets=[json.loads((ASSETS/f'{name}-data.json').read_text()) for name in ['inventory','revenue','experiment']]
    else: datasets=[inventory_lab.export(ASSETS),revenue_forensics.export(ASSETS),experiment_studio.export(ASSETS)]
    covers(*datasets);bundles(json.loads((ROOT/'docs/projects.json').read_text()))
    if args.png:png_cover()
    print('Built analytical covers, documentation and three standalone project bundles.')


if __name__=='__main__':main()
