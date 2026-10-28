#!/usr/bin/env python3
"""Render precise portfolio media from the runnable survey pipeline's outputs."""
from __future__ import annotations

import json
import math
import subprocess
import statistics
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs' / 'assets'
TMP = ROOT / 'tmp' / 'portfolio-media'
TMP.mkdir(parents=True, exist_ok=True)
DATA = json.loads((ASSETS / 'portfolio-data.json').read_text())


def exact_measure(rows):
    """Recalculate from rows so one-decimal display never double-rounds."""
    completed = [row for row in rows if row['completed']]
    return {
        'responses': len(rows),
        'completed': len(completed),
        'completionRate': 100 * len(completed) / len(rows),
        'csat': 100 * sum(row['score'] >= 4 for row in completed) / len(completed),
        'medianDuration': statistics.median(row['duration'] for row in completed),
    }


DATA['summary'] = exact_measure(DATA['rows'])
for group, key in [('markets', 'market'), ('weekly', 'week'), ('channels', 'channel')]:
    DATA[group] = [
        {key: value, **exact_measure([row for row in DATA['rows'] if row[key] == value])}
        for value in sorted({row[key] for row in DATA['rows']})
    ]
META, SUMMARY = DATA['meta'], DATA['summary']
LOG = (ASSETS / 'pipeline-run.txt').read_text().splitlines()
ORIGIN = 'https://titusrobinsonone.github.io'
INK, MUTED, TEAL, MINT = '#172a3a', '#647786', '#087e82', '#d8efec'
PAPER, LINE, GOLD = '#f3f6f6', '#dce5e8', '#b47a31'
WHITE, DARK, LIGHT = '#ffffff', '#102535', '#cfe5e3'
FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')
REG = FONT_DIR / 'DejaVuSans.ttf'
BOLD = FONT_DIR / 'DejaVuSans-Bold.ttf'
MONO = FONT_DIR / 'DejaVuSansMono.ttf'


def pct(n: float) -> str:
    return f'{n:.1f}%'


def duration(n: float) -> str:
    return f'{int(n // 60)}:{int(round(n % 60)):02d}'


def font(size: int, bold: bool = False, mono: bool = False):
    return ImageFont.truetype(str(MONO if mono else BOLD if bold else REG), size)


def wrap(text: str, width: float, measure):
    lines, line = [], ''
    for word in text.split():
        candidate = (line + ' ' + word).strip()
        if line and measure(candidate) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def pillow_text(draw, xy, text, size=20, fill=INK, bold=False, mono=False, anchor=None):
    draw.text(xy, text, font=font(size, bold, mono), fill=fill, anchor=anchor)


def rr(draw, box, fill=WHITE, radius=18, outline=LINE):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1)


def pdf_text(c, x, y, text, size=12, color=INK, bold=False):
    c.setFillColor(HexColor(color))
    c.setFont('DVB' if bold else 'DV', size)
    c.drawString(x, y, text)


def pdf_right(c, x, y, text, size=12, color=INK, bold=False):
    c.setFillColor(HexColor(color))
    c.setFont('DVB' if bold else 'DV', size)
    c.drawRightString(x, y, text)


def pdf_wrap(c, x, y, text, width, size=10, color=MUTED, leading=15, bold=False):
    name = 'DVB' if bold else 'DV'
    for line in wrap(text, width, lambda s: pdfmetrics.stringWidth(s, name, size)):
        pdf_text(c, x, y, line, size, color, bold)
        y -= leading
    return y


def pdf_panel(c, x, y, w, h):
    c.setFillColor(HexColor(WHITE))
    c.setStrokeColor(HexColor(LINE))
    c.roundRect(x, y, w, h, 16, stroke=1, fill=1)


def make_pdf():
    pdfmetrics.registerFont(TTFont('DV', str(REG)))
    pdfmetrics.registerFont(TTFont('DVB', str(BOLD)))
    path = ASSETS / 'survey-dashboard.pdf'
    c = canvas.Canvas(str(path), pagesize=(1200, 800), pageCompression=1)
    c.setTitle('Survey Operations Dashboard | Titus Robinson')
    c.setAuthor('Titus Robinson')
    c.setSubject('Synthetic portfolio demonstration: survey operations and data quality')
    c.setFillColor(HexColor(PAPER))
    c.rect(0, 0, 1200, 800, fill=1, stroke=0)
    pdf_text(c, 44, 756, 'TITUS ROBINSON  /  DATA & BI PORTFOLIO', 11, TEAL, True)
    c.setFillColor(HexColor(MINT))
    c.roundRect(884, 741, 272, 29, 14, fill=1, stroke=0)
    pdf_text(c, 900, 751, 'Synthetic portfolio demonstration', 10, TEAL, True)
    pdf_text(c, 44, 699, 'Survey Operations Dashboard', 36, INK, True)
    pdf_text(c, 44, 671, 'From survey data to clear, auditable reporting.', 16, MUTED)
    pdf_text(c, 44, 640, 'AUG 3 - OCT 25, 2026   |   6 MARKETS   |   3 CHANNELS   |   FULL DATASET VIEW', 10, MUTED)
    c.linkURL(ORIGIN + '/survey.html', (44, 690, 740, 731), relative=0)

    metrics = [
        ('USABLE RESPONSES', f"{SUMMARY['responses']:,}", 'Validated survey records'),
        ('COMPLETION RATE', pct(SUMMARY['completionRate']), f"{SUMMARY['completed']:,} completed / 7,200 usable"),
        ('CUSTOMER SATISFACTION', pct(SUMMARY['csat']), 'CSAT: scores 4-5 / completed'),
        ('MEDIAN COMPLETION TIME', duration(SUMMARY['medianDuration']), 'Minutes : seconds - completed only'),
    ]
    for i, (label, value, note) in enumerate(metrics):
        x, y, w, h = 44 + i * 282, 510, 266, 105
        pdf_panel(c, x, y, w, h)
        if i == 0:
            c.setStrokeColor(HexColor(TEAL)); c.setLineWidth(3)
            c.line(x + 17, y + h - 1, x + w - 17, y + h - 1)
            c.setLineWidth(1)
        pdf_text(c, x + 19, y + 79, label, 9, MUTED, True)
        pdf_text(c, x + 18, y + 37, value, 33, INK, True)
        pdf_text(c, x + 19, y + 17, note, 9, MUTED)

    # Weekly response volume; stacked counts start from zero.
    pdf_panel(c, 44, 278, 740, 213)
    pdf_text(c, 65, 463, 'Response volume over time', 16, INK, True)
    pdf_text(c, 65, 444, 'Weekly survey records, split by completion status', 9, MUTED)
    gx, gy, gw, gh = 96, 309, 660, 112
    max_y = 650
    for tick in [0, 200, 400, 600]:
        yy = gy + gh * tick / max_y
        c.setStrokeColor(HexColor('#e6edef')); c.line(gx, yy, gx + gw, yy)
        pdf_right(c, gx - 10, yy - 3, str(tick), 8, MUTED)
    weekly = DATA['weekly']
    unit = gw / len(weekly)
    for i, row in enumerate(weekly):
        x = gx + unit * (i + .5) - 14
        done = gh * row['completed'] / max_y
        incomplete = gh * (row['responses'] - row['completed']) / max_y
        c.setFillColor(HexColor(TEAL)); c.rect(x, gy, 28, done, stroke=0, fill=1)
        c.setFillColor(HexColor('#c8e6e2')); c.rect(x, gy + done, 28, incomplete, stroke=0, fill=1)
        if i % 2 == 0 or i == len(weekly) - 1:
            import datetime
            date = datetime.date.fromisoformat(row['week']).strftime('%b %d')
            pdf_text(c, x - 5, gy - 17, date, 8, MUTED)
    c.setFillColor(HexColor(TEAL)); c.rect(602, 465, 7, 7, fill=1, stroke=0)
    pdf_text(c, 614, 465, 'Completed', 8, MUTED)
    c.setFillColor(HexColor('#c8e6e2')); c.rect(680, 465, 7, 7, fill=1, stroke=0)
    pdf_text(c, 692, 465, 'Incomplete', 8, MUTED)

    # Market table.
    pdf_panel(c, 44, 72, 740, 190)
    pdf_text(c, 65, 235, 'Market performance', 16, INK, True)
    pdf_text(c, 65, 216, 'Ranked by CSAT - read satisfaction alongside completion and sample size.', 9, MUTED)
    headers = [('MARKET', 65), ('RESPONSES', 438), ('COMPLETION', 548), ('CSAT', 642), ('MEDIAN TIME', 761)]
    for name, x in headers:
        if name == 'MARKET': pdf_text(c, x, 195, name, 8, MUTED, True)
        else: pdf_right(c, x, 195, name, 8, MUTED, True)
    for i, row in enumerate(sorted(DATA['markets'], key=lambda r: r['csat'], reverse=True)):
        yy = 176 - i * 17
        if i:
            c.setStrokeColor(HexColor('#edf1f2')); c.line(65, yy + 12, 761, yy + 12)
        pdf_text(c, 65, yy, row['market'], 10, INK, True)
        pdf_right(c, 438, yy, f"{row['responses']:,}", 10)
        pdf_right(c, 548, yy, pct(row['completionRate']), 10)
        pdf_right(c, 642, yy, pct(row['csat']), 10, TEAL, True)
        pdf_right(c, 761, yy, duration(row['medianDuration']), 10)

    # Quality card.
    pdf_panel(c, 806, 72, 350, 419)
    pdf_text(c, 828, 463, 'Quality gate', 16, INK, True)
    pdf_text(c, 828, 444, 'Full import - before dashboard filters', 9, MUTED)
    pass_rate = META['cleanRows'] / META['inputRows'] * 100
    pdf_text(c, 828, 395, pct(pass_rate), 34, TEAL, True)
    pdf_text(c, 828, 374, 'of imported rows passed validation', 10, MUTED)
    c.setFillColor(HexColor('#f5e8d5')); c.roundRect(828, 352, 306, 8, 4, stroke=0, fill=1)
    c.setFillColor(HexColor(TEAL)); c.roundRect(828, 352, 306 * pass_rate / 100, 8, 4, stroke=0, fill=1)
    pdf_text(c, 828, 332, f"{META['cleanRows']:,} passed", 9, MUTED)
    pdf_right(c, 1134, 332, f"{META['rejectedRows']:,} isolated", 9, MUTED)
    labels = ['Duplicate response ID', 'Missing response ID', 'Invalid satisfaction score', 'Invalid duration']
    for i, (row, label) in enumerate(zip(META['quality'], labels)):
        yy = 293 - i * 38
        pdf_text(c, 828, yy, label, 10)
        pdf_right(c, 1134, yy, str(row['count']), 10, INK, True)
        c.setFillColor(HexColor('#edf1f2')); c.roundRect(828, yy - 12, 306, 4, 2, fill=1, stroke=0)
        c.setFillColor(HexColor('#cfaa70')); c.roundRect(828, yy - 12, 306 * row['count'] / META['rejectedRows'], 4, 2, fill=1, stroke=0)
    pdf_wrap(c, 828, 140, 'Flagged rows remain in a separate export with their rejection reason. Only validated responses enter the dashboard.', 306, 9, MUTED, 13)
    pdf_text(c, 828, 92, 'Explore the interactive dashboard online', 10, TEAL, True)
    c.linkURL(ORIGIN + '/survey.html', (828, 86, 1135, 106), relative=0)

    pdf_text(c, 44, 45, 'DEFINITIONS', 8, TEAL, True)
    pdf_text(c, 129, 45, 'Completion = completed / usable. CSAT = completed scores 4-5 / completed. Median time uses completed responses.', 8, MUTED)
    pdf_text(c, 44, 27, 'Generated synthetic survey data. Created October 2026. Explore the pipeline, source code and audit trail:', 8, MUTED)
    pdf_text(c, 802, 27, 'Python automation demo', 8, TEAL, True)
    c.linkURL(ORIGIN + '/automation/', (802, 21, 956, 37), relative=0)
    c.showPage(); c.save()
    return path


def brand(draw, width, dark=False):
    ink = WHITE if dark else INK
    rr(draw, (44, 34, 92, 82), TEAL if dark else INK, 13, outline=None)
    pillow_text(draw, (68, 57), 'TR', 21, WHITE, True, anchor='mm')
    pillow_text(draw, (106, 37), 'Titus Robinson', 20, ink, True)
    pillow_text(draw, (106, 65), 'DATA & BI PORTFOLIO', 10, '#a8c5cc' if dark else MUTED, True)
    badge = 'SYNTHETIC PORTFOLIO DEMONSTRATION'
    f = font(10, True)
    tw = draw.textlength(badge, font=f)
    box = (width - tw - 72, 43, width - 44, 74)
    rr(draw, box, '#1c464c' if dark else MINT, 15, outline=None)
    pillow_text(draw, (box[0] + 14, 52), badge, 10, '#a7dfd3' if dark else TEAL, True)


def dashboard_preview():
    im = Image.new('RGB', (1200, 630), PAPER)
    d = ImageDraw.Draw(im); brand(d, 1200)
    pillow_text(d, (44, 114), 'Survey Operations Dashboard', 37, INK, True)
    pillow_text(d, (44, 166), '6 markets. 12 weeks. One clear view of reporting quality.', 19, MUTED)
    cards = [
        ('USABLE RESPONSES', f"{SUMMARY['responses']:,}", 'Validated records'),
        ('COMPLETION RATE', pct(SUMMARY['completionRate']), 'Completed / usable'),
        ('CSAT', pct(SUMMARY['csat']), 'Scores 4-5 / completed'),
        ('MEDIAN TIME', duration(SUMMARY['medianDuration']), 'Minutes : seconds'),
    ]
    for i, (label, val, note) in enumerate(cards):
        x = 44 + 282 * i
        rr(d, (x, 218, x + 266, 324))
        pillow_text(d, (x + 18, 233), label, 10, MUTED, True)
        pillow_text(d, (x + 17, 251), val, 34, INK, True)
        pillow_text(d, (x + 18, 297), note, 11, MUTED)
    rr(d, (44, 344, 785, 576)); rr(d, (806, 344, 1156, 576))
    pillow_text(d, (65, 363), 'Weekly response volume', 18, INK, True)
    gx, gy, gw, gh, ceiling = 96, 534, 660, 116, 650
    for tick in [0, 200, 400, 600]:
        yy = gy - gh * tick / ceiling
        d.line((gx, yy, gx + gw, yy), fill='#e6edef', width=1)
        pillow_text(d, (gx - 10, yy), str(tick), 10, MUTED, anchor='rm')
    for i, row in enumerate(DATA['weekly']):
        x = gx + (i + .5) * gw / 12 - 14
        done = gh * row['completed'] / ceiling
        incomplete = gh * (row['responses'] - row['completed']) / ceiling
        d.rectangle((x, gy - done, x + 28, gy), fill=TEAL)
        d.rectangle((x, gy - done - incomplete, x + 28, gy - done), fill='#c8e6e2')
        if i % 2 == 0 or i == 11:
            import datetime
            label = datetime.date.fromisoformat(row['week']).strftime('%b %d')
            pillow_text(d, (x + 14, 551), label, 9, MUTED, anchor='mm')
    d.rectangle((588, 369, 596, 377), fill=TEAL)
    pillow_text(d, (602, 366), 'Completed', 10, MUTED)
    d.rectangle((675, 369, 683, 377), fill='#c8e6e2')
    pillow_text(d, (689, 366), 'Incomplete', 10, MUTED)
    pillow_text(d, (828, 363), 'Quality gate', 18, INK, True)
    pillow_text(d, (828, 398), pct(META['cleanRows'] / META['inputRows'] * 100), 38, TEAL, True)
    pillow_text(d, (828, 448), 'of imported rows passed validation', 11, MUTED)
    for i, (row, label) in enumerate(zip(META['quality'], ['Duplicate IDs', 'Missing IDs', 'Invalid scores', 'Invalid durations'])):
        yy = 477 + i * 20
        pillow_text(d, (828, yy), label, 12, MUTED)
        pillow_text(d, (1135, yy), str(row['count']), 12, INK, True, anchor='rt')
    pillow_text(d, (44, 601), 'Interactive filters  /  Clear KPI definitions  /  Downloadable Python source', 11, TEAL, True)
    pillow_text(d, (1156, 601), 'Created October 2026', 10, MUTED, anchor='rt')
    im.save(ASSETS / 'dashboard-preview.png', optimize=True)


def automation_poster():
    im = Image.new('RGB', (1200, 675), DARK); d = ImageDraw.Draw(im)
    brand(d, 1200, True)
    pillow_text(d, (50, 121), 'PYTHON / DATA QUALITY AUTOMATION', 12, '#7cd0c1', True)
    pillow_text(d, (47, 155), 'Python → BI-ready data', 49, WHITE, True)
    pillow_text(d, (50, 225), 'A reproducible pipeline, from CSV import to validated reporting.', 20, '#a8c5cc')
    for i, (value, label, color) in enumerate([(META['inputRows'], 'INPUT ROWS', '#d6e5e9'), (META['cleanRows'], 'VALIDATED', '#7bd3bf'), (META['rejectedRows'], 'ISOLATED', '#e7bb7c')]):
        x = 50 + i * 374
        rr(d, (x, 287, x + 352, 429), '#183646', 16, '#294b5b')
        pillow_text(d, (x + 25, 310), f'{value:,}', 46, color, True)
        pillow_text(d, (x + 27, 380), label, 12, '#a8c5cc', True)
    rr(d, (50, 466, 1150, 550), '#0b1e2b', 12, '#294b5b')
    pillow_text(d, (75, 493), '$ python3 survey_pipeline.py --generate-demo --output out', 20, '#bbe6dc', mono=True)
    pillow_text(d, (50, 570), '38-second walkthrough  /  Actual script output  /  Source included', 16, '#a8c5cc')
    im.save(ASSETS / 'automation-poster.png', optimize=True)
    return im


def video_base(title, eyebrow='PYTHON / DATA QUALITY AUTOMATION'):
    im = Image.new('RGB', (1280, 720), DARK); d = ImageDraw.Draw(im)
    # A smaller fixed identity band leaves room for large technical content.
    rr(d, (46, 30, 86, 70), TEAL, 11, outline=None)
    pillow_text(d, (66, 50), 'TR', 18, WHITE, True, anchor='mm')
    pillow_text(d, (99, 34), 'Titus Robinson', 18, WHITE, True)
    pillow_text(d, (99, 59), 'DATA & BI PORTFOLIO', 9, '#a8c5cc', True)
    rr(d, (883, 34, 1234, 69), '#1c464c', 16, outline=None)
    pillow_text(d, (1059, 51), 'SYNTHETIC PORTFOLIO DEMONSTRATION', 10, '#a7dfd3', True, anchor='mm')
    pillow_text(d, (46, 103), eyebrow, 11, '#7cd0c1', True)
    pillow_text(d, (44, 130), title, 34, WHITE, True)
    d.line((46, 663, 1234, 663), fill='#294b5b', width=1)
    pillow_text(d, (46, 685), 'SYNTHETIC PORTFOLIO DEMONSTRATION', 11, '#7cd0c1', True)
    pillow_text(d, (1234, 685), 'Paced walkthrough of actual Python output', 11, '#a8c5cc', anchor='rt')
    return im, d


def terminal_frame(lines, subtitle):
    im, d = video_base('One command. Every row accounted for.')
    pillow_text(d, (46, 183), subtitle, 17, '#a8c5cc')
    rr(d, (46, 225, 1234, 630), '#0b1e2b', 15, '#294b5b')
    for i, color in enumerate(['#ca796d', '#d4ae69', '#72bda8']):
        d.ellipse((68 + i * 20, 244, 77 + i * 20, 253), fill=color)
    pillow_text(d, (68, 276), '$ python3 survey_pipeline.py --generate-demo --output out', 19, '#a5ded1', mono=True)
    y = 324
    for line in lines:
        color = '#85d6be' if line.startswith(('RECONCILED', 'SUCCESS')) else '#d0e2e5'
        pillow_text(d, (68, y), line, 17, color, mono=True)
        y += 27
    return im


def make_video(poster):
    scenes = []
    poster_frame = poster.resize((1280, 720), Image.Resampling.LANCZOS)
    scenes.append((poster_frame, 6))
    scenes.append((terminal_frame(LOG[:3], '01 / Generate a deterministic synthetic CSV and inspect its schema.'), 3))
    scenes.append((terminal_frame(LOG[:4], '02 / Validate IDs, categories, dates, durations and scores.'), 3))
    scenes.append((terminal_frame(LOG[:8], 'Quality failures are isolated with their exact rejection reason.'), 5))
    im, d = video_base('100 rows isolated. Nothing silently dropped.')
    pillow_text(d, (46, 185), 'Quality checks run before data reaches the dashboard.', 18, '#a8c5cc')
    labels = ['Duplicate response IDs', 'Missing response IDs', 'Invalid satisfaction scores', 'Invalid durations']
    for i, (row, label) in enumerate(zip(META['quality'], labels)):
        y = 250 + i * 86
        pillow_text(d, (50, y), label, 20, '#d0e2e5')
        pillow_text(d, (1230, y - 5), str(row['count']), 28, '#e7bb7c', True, anchor='rt')
        rr(d, (50, y + 41, 1230, y + 49), '#294b5b', 4, outline=None)
        rr(d, (50, y + 41, 50 + 1180 * row['count'] / META['rejectedRows'], y + 49), '#d3ac73', 4, outline=None)
    scenes.append((im, 10))
    im, d = video_base('Clean data. Consistent metrics. An audit trail.')
    for i, (value, label) in enumerate([(META['inputRows'], 'INPUT'), (META['cleanRows'], 'VALIDATED'), (META['rejectedRows'], 'ISOLATED')]):
        x = 46 + i * 403
        rr(d, (x, 210, x + 383, 342), '#183646', 15, '#294b5b')
        pillow_text(d, (x + 24, 229), f'{value:,}', 44, '#7bd3bf' if i == 1 else '#d6e5e9', True)
        pillow_text(d, (x + 26, 300), label, 12, '#a8c5cc', True)
    rr(d, (46, 374, 1234, 613), '#0b1e2b', 15, '#294b5b')
    result_lines = [LOG[9], LOG[10], LOG[11], LOG[12], LOG[14]]
    for i, line in enumerate(result_lines):
        pillow_text(d, (68, 399 + i * 37), line, 17, '#85d6be' if line.startswith(('RECONCILED', 'SUCCESS')) else '#d0e2e5', mono=True)
    scenes.append((im, 7))
    im, d = video_base('Reproducible code. Auditable outputs.')
    pillow_text(d, (46, 220), 'Explore the dashboard.', 37, '#7bd3bf', True)
    pillow_text(d, (46, 280), 'Download the Python source.', 37, WHITE, True)
    pillow_text(d, (46, 340), 'Inspect the data-quality rules.', 37, WHITE, True)
    pillow_text(d, (46, 446), 'Seed 20261028  /  Standard-library Python  /  Source + tests included', 19, '#a8c5cc')
    rr(d, (46, 520, 739, 586), TEAL, 12, outline=None)
    pillow_text(d, (70, 540), 'Titus Robinson  |  Data & BI Portfolio', 23, WHITE, True)
    scenes.append((im, 4))
    assert sum(seconds for _, seconds in scenes) == 38
    concat = []
    for i, (frame, seconds) in enumerate(scenes):
        path = TMP / f'scene-{i:02d}.png'
        frame.save(path, optimize=True)
        concat.append(f"file '{path}'\nduration {seconds}\n")
    concat.append(f"file '{TMP / f'scene-{len(scenes)-1:02d}.png'}'\n")
    concat_path = TMP / 'scenes.txt'
    concat_path.write_text(''.join(concat))
    video = ASSETS / 'python-pipeline-demo.mp4'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_path), '-t', '38', '-r', '15', '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', str(video)], check=True)
    (ASSETS / 'demo-captions.vtt').write_text('''WEBVTT

00:00:00.000 --> 00:00:06.000
Titus Robinson: a synthetic survey data-quality pipeline.
7,300 input rows, 7,200 validated responses, 100 isolated rows.

00:00:06.000 --> 00:00:12.000
Run the included Python script with one command.
Generate deterministic synthetic data, then validate the schema and response fields.

00:00:12.000 --> 00:00:17.000
The actual run isolates duplicate IDs, missing IDs, invalid satisfaction scores and invalid durations.

00:00:17.000 --> 00:00:27.000
48 duplicate IDs, 24 missing IDs, 18 invalid scores and 10 invalid durations.
Each flagged row retains a reason in a separate export.

00:00:27.000 --> 00:00:34.000
The totals reconcile: 7,300 input equals 7,200 clean plus 100 flagged.
Export clean data, market summaries, dashboard JSON and an audit trail.

00:00:34.000 --> 00:00:38.000
Reproducible code. Auditable outputs.
Explore the dashboard and download the Python source, synthetic data and tests.
''')


if __name__ == '__main__':
    make_pdf()
    dashboard_preview()
    poster = automation_poster()
    make_video(poster)
    print(json.dumps({'assets': [p.name for p in [ASSETS / 'survey-dashboard.pdf', ASSETS / 'dashboard-preview.png', ASSETS / 'automation-poster.png', ASSETS / 'python-pipeline-demo.mp4', ASSETS / 'demo-captions.vtt']], 'data': SUMMARY, 'videoSeconds': 38}, indent=2))
