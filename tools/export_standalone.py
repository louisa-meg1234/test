# Builds single-file, offline-shareable copies of the prototype variants (assets inlined as data URIs).
import base64, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'export')
VARIANTS = [('index.html', 'sleep-prototype-base.html'),
            ('hypnogram.html', 'sleep-prototype-hypnogram.html'),
            ('sleep-synthesis.html', 'sleep-prototype-synthesis.html')]
assets = {}
for d, _, fs in os.walk(os.path.join(ROOT, 'assets')):
    for f in fs:
        p = os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, '/')
        assets[p] = 'data:image/svg+xml;base64,' + base64.b64encode(open(os.path.join(d, f), 'rb').read()).decode()
os.makedirs(OUT, exist_ok=True)
for src, dst in VARIANTS:
    s = open(os.path.join(ROOT, src), encoding='utf-8').read()
    # dynamic paths: keep only assets whose stem appears somewhere in the page
    used = {p for p in assets if os.path.splitext(os.path.basename(p))[0] in s or os.path.basename(p).startswith('tip-')}
    s = re.sub(r"\"assets/' \+ ([^']+?) \+ '\.svg\"", r"\"' + __A['assets/' + \1 + '.svg'] + '\"", s)
    s = re.sub(r"(?<!__A\[)'assets/([a-z0-9/-]*)' \+ ([^']+?) \+ '\.svg'", r"__A['assets/\1' + \2 + '.svg']", s)
    s = re.sub(r"assets/[A-Za-z0-9_/-]+\.svg", lambda m: assets[m.group(0)] if m.group(0) in assets else m.group(0), s)
    left = sorted(set(re.findall(r"assets/[^\"' )]*", s)))
    shim = '<script>var __A=' + json.dumps({p: assets[p] for p in sorted(used)}) + ';</script>\n'
    s = s.replace('<body>\n', '<body>\n' + shim, 1)
    open(os.path.join(OUT, dst), 'w', encoding='utf-8').write(s)
    print(dst, round(len(s) / 1e6, 1), 'MB; unresolved:', left)
