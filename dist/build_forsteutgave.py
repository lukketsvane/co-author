#!/usr/bin/env python3
"""
build_forsteutgave.py — Bygg printklar førsteutgåve av Tractatus Formae.

Typografi og layout er modellert etter Gyldendal Fakkel-utgåva av
Wittgensteins Tractatus Logico-Philosophicus (1999), analysert frå
sideskann i digibok_2009032304095/.

Font: EB Garamond 12 (open source, nærast Sabon/Garamond i originalen)
Format: 130 × 200 mm pocketbok + A4 for skjermlesing
Proposisjonslayout: nummer i venstre kolonne, tekst i høgre blokk

Køyr:
    python3 "formgjevars traktat/redaksjon/build_forsteutgave.py"
"""

import re
import os
import sys
import markdown as md
from weasyprint import HTML

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
BIB_FILE = os.path.join(PROJECT_DIR, "references.bib")
INPUT = os.path.join(BASE_DIR, "utkast_03.md")
OUTPUT_POCKET = os.path.join(BASE_DIR, "forsteutgave.pdf")
OUTPUT_A4 = os.path.join(BASE_DIR, "forsteutgave_a4.pdf")


# ---------------------------------------------------------------------------
# BibTeX parser
# ---------------------------------------------------------------------------

def parse_bibtex(path):
    """Parse .bib file into dict of key -> {author, year, title}."""
    entries = {}
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    pattern = re.compile(r'@\w+\{([^,]+),\s*(.*?)\n\}', re.DOTALL)
    for m in pattern.finditer(text):
        key = m.group(1).strip()
        body = m.group(2)
        entry = {}
        for field_m in re.finditer(r'(\w+)\s*=\s*\{(.*?)\}', body, re.DOTALL):
            fname = field_m.group(1).lower()
            fval = field_m.group(2).strip()
            fval = re.sub(r'\\textit\{([^}]+)\}', r'\1', fval)
            fval = re.sub(r'\{\\[a-z]+\s+([^}]*)\}', r'\1', fval)
            fval = re.sub(r'[{}]', '', fval)
            fval = re.sub(r'\\[a-z]+', '', fval)
            entry[fname] = fval.strip()
        entries[key] = entry
    return entries


def make_citation_label(entry):
    """Create (Author, Year) label."""
    author = entry.get('author', '')
    year = entry.get('year', '')
    title = entry.get('title', '')
    if author:
        parts = author.split(' and ')
        first = parts[0].strip()
        if ',' in first:
            surname = first.split(',')[0].strip()
        else:
            surname = first.split()[-1] if first.split() else first
        if len(parts) > 2 or 'others' in author:
            surname += ' et al.'
        elif len(parts) == 2:
            second = parts[1].strip()
            s2 = second.split(',')[0].strip() if ',' in second else (second.split()[-1] if second.split() else second)
            if s2 != 'others':
                surname += ' og ' + s2
            else:
                surname += ' et al.'
    else:
        surname = title[:40] + ('...' if len(title) > 40 else '')
    return f'({surname}, {year})' if year else f'({surname})'


def resolve_citations(text, bib):
    """Replace [bibtex_key] and [key1; key2] with (Author, Year)."""
    def replace_cite(m):
        keys_str = m.group(1)
        keys = [k.strip() for k in keys_str.split(';')]
        labels = []
        for key in keys:
            if key in bib:
                labels.append(make_citation_label(bib[key]))
            elif key.startswith('M:'):
                return m.group(0)
            else:
                labels.append(f'[{key}]')
        return '; '.join(labels)
    text = re.sub(
        r'\[([a-z][a-z0-9_]+(?:;\s*[a-z][a-z0-9_]+)*)\]',
        replace_cite, text
    )
    return text


# ---------------------------------------------------------------------------
# Math notation → Unicode
# ---------------------------------------------------------------------------

SUB_MAP = {
    'C': '\u1D04', 'c': '\u1D04', 'i': '\u1D62', 'j': '\u2C7C',
    'k': '\u2096', 'm': '\u2098', 'n': '\u2099', 's': '\u209B',
    't': '\u209C', 'x': '\u2093', 'a': '\u2090', 'e': '\u2091',
    'o': '\u2092', 'r': '\u1D63', 'u': '\u1D64',
    '0': '\u2080', '1': '\u2081', '2': '\u2082', '3': '\u2083',
    '4': '\u2084', '5': '\u2085', '6': '\u2086', '7': '\u2087',
    '8': '\u2088', '9': '\u2089',
}
SUP_MAP = {
    'n': '\u207F', 'i': '\u2071', 'k': '\u1D4F',
    '0': '\u2070', '1': '\u00B9', '2': '\u00B2', '3': '\u00B3',
    '4': '\u2074', '5': '\u2075', '6': '\u2076', '7': '\u2077',
    '8': '\u2078', '9': '\u2079',
    '+': '\u207A', '-': '\u207B', '=': '\u207C',
    '(': '\u207D', ')': '\u207E',
}

def to_sub(s): return ''.join(SUB_MAP.get(c, c) for c in s)
def to_sup(s): return ''.join(SUP_MAP.get(c, c) for c in s)

def convert_math(text):
    """Convert _X subscripts and ^X superscripts to Unicode."""
    text = re.sub(r'([A-Za-z\w])\^(\{[^}]+\}|[A-Za-z0-9])',
                  lambda m: m.group(1) + to_sup(m.group(2).strip('{}')), text)
    text = re.sub(r'(?<![_a-z])([A-Za-z])_([A-Za-z0-9])(?![_a-z])',
                  lambda m: m.group(1) + to_sub(m.group(2)), text)
    text = re.sub(r'([A-Za-z])_\{([^}]+)\}',
                  lambda m: m.group(1) + to_sub(m.group(2)), text)
    text = text.replace(' -> ', ' \u2192 ')
    text = text.replace('nabla(', '\u2207(')
    text = text.replace('nabla ', '\u2207')
    text = re.sub(r'\bdelta([A-Z])', lambda m: '\u03B4' + m.group(1), text)
    text = re.sub(r'\bsigma\b', '\u03C3', text)
    text = re.sub(r'\bgamma\b', '\u03B3', text)
    text = text.replace(' . ', ' \u00B7 ')
    return text


# ---------------------------------------------------------------------------
# Preprocess markdown
# ---------------------------------------------------------------------------

def preprocess(md_text, bib):
    """Citations + math notation."""
    md_text = resolve_citations(md_text, bib)
    md_text = convert_math(md_text)
    return md_text


# ---------------------------------------------------------------------------
# HTML post-processing: Tractatus proposition layout
# ---------------------------------------------------------------------------

TAG_ABBREV = {
    'Definisjon': 'd', 'Aksiom': 'a', 'Teorem': 't',
    'Observasjon': 'o', 'Illustrasjon': 'i',
}

def tractatus_html(html_body):
    """Convert proposition patterns to Tractatus two-column layout."""

    # Proposition with logical status tag: **1.1** [Definisjon] text
    def prop_with_tag(m):
        num = m.group(1)
        tag = m.group(2)
        abbr = TAG_ABBREV.get(tag, tag[0].lower())
        depth = 0
        if '.' in num:
            decimal = num.split('.')[1]
            depth = min(len(decimal), 4)
        return (f'</p><div class="prop depth-{depth}">'
                f'<span class="prop-num">{num}<sup class="prop-tag">{abbr}</sup></span>'
                f'<div class="prop-body">')

    html_body = re.sub(
        r'<strong>([\d.]+)</strong>\s*\[([^\]]+)\]',
        prop_with_tag,
        html_body
    )

    # Proposition without tag: **1.1** text (less common)
    def prop_without_tag(m):
        num = m.group(1)
        depth = 0
        if '.' in num:
            decimal = num.split('.')[1]
            depth = min(len(decimal), 4)
        return (f'</p><div class="prop depth-{depth}">'
                f'<span class="prop-num">{num}</span>'
                f'<div class="prop-body">')

    html_body = re.sub(
        r'<strong>([\d.]+)</strong>\s+(?!\[)',
        prop_without_tag,
        html_body
    )

    # Close open prop divs before next prop or heading or hr
    html_body = re.sub(
        r'(</p>)\s*(<div class="prop |<h[12]|<hr)',
        r'</div></div>\1\2',
        html_body
    )

    # Close any trailing open prop div
    if '<div class="prop ' in html_body:
        html_body = re.sub(r'(<hr\s*/?>|</body>)',
                           r'</div></div>\1', html_body)

    # Section headings → Tractatus small-caps style
    # h2 headings that start with a digit are main propositions
    html_body = re.sub(
        r'<h2>(\d+)\s+(.+?)</h2>',
        r'<h2><span class="section-num">\1</span>  \2</h2>',
        html_body
    )

    return html_body


# ---------------------------------------------------------------------------
# CSS: Tractatus typography (EB Garamond, pocket book format)
# ---------------------------------------------------------------------------

def tractatus_css(page_size='130mm 200mm', page_name='pocket'):
    """Generate CSS matching Gyldendal Fakkel Tractatus layout."""
    return f"""
/* ===== Page setup ===== */
@page {{
    size: {page_size};
    margin: 15mm 14mm 18mm 14mm;
    @bottom-center {{
        content: counter(page);
        font-family: 'EB Garamond', 'EB Garamond 12', Georgia, serif;
        font-size: 9pt;
        color: #333;
    }}
}}
@page :first {{
    @bottom-center {{ content: none; }}
}}
@page :blank {{
    @bottom-center {{ content: none; }}
}}
@page title {{
    @bottom-center {{ content: none; }}
}}
@page frontmatter {{
    @bottom-center {{
        content: counter(page, lower-roman);
        font-family: 'EB Garamond', 'EB Garamond 12', Georgia, serif;
        font-size: 9pt;
        color: #333;
    }}
}}

/* ===== Base typography ===== */
body {{
    font-family: 'EB Garamond', 'EB Garamond 12', 'EB Garamond 08', Georgia, 'DejaVu Serif', serif;
    font-size: 10.5pt;
    line-height: 1.40;
    color: #111;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
    orphans: 3;
    widows: 3;
}}

/* ===== Title page ===== */
.title-page {{
    page: title;
    page-break-after: always;
    text-align: center;
    padding-top: 20%;
}}
.tp-author {{
    font-size: 14pt;
    margin-bottom: 2em;
}}
.title-page h1 {{
    font-family: 'EB Garamond SC', 'EB Garamond SC 12', 'EB Garamond', Georgia, serif;
    font-size: 22pt;
    font-weight: normal;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 0.2em;
    text-align: center;
    border: none;
}}
.title-page .subtitle {{
    font-size: 11pt;
    font-style: italic;
    margin-bottom: 0;
    color: #222;
}}

/* ===== Half-title ===== */
.half-title {{
    page: title;
    page-break-after: always;
    text-align: center;
    padding-top: 35%;
}}
.half-title h1 {{
    font-family: 'EB Garamond SC', 'EB Garamond SC 12', 'EB Garamond', Georgia, serif;
    font-size: 16pt;
    font-weight: normal;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    border: none;
}}

/* ===== Colophon ===== */
.colophon {{
    page: title;
    page-break-after: always;
    font-size: 8.5pt;
    color: #444;
    line-height: 1.5;
    padding-top: 60%;
}}
.colophon p {{
    text-align: left;
    margin: 0.2em 0;
}}

/* (author-page fjerna — forfattar er no på tittelsida) */

/* ===== Headings (Tractatus style: small caps, centered) ===== */
h1 {{
    font-family: 'EB Garamond SC', 'EB Garamond SC 12', 'EB Garamond', Georgia, serif;
    font-size: 14pt;
    font-weight: normal;
    text-align: center;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-top: 2em;
    margin-bottom: 1.2em;
    page-break-after: avoid;
    border: none;
}}

h2 {{
    font-family: 'EB Garamond SC', 'EB Garamond SC 12', 'EB Garamond', Georgia, serif;
    font-size: 10.5pt;
    font-weight: normal;
    text-align: left;
    letter-spacing: 0.05em;
    margin-top: 2em;
    margin-bottom: 1em;
    page-break-before: always;
    page-break-after: avoid;
}}
h2:first-of-type {{
    page-break-before: avoid;
}}
.section-num {{
    font-weight: bold;
    font-size: 12pt;
    margin-right: 0.3em;
}}

h3 {{
    font-family: 'EB Garamond SC', 'EB Garamond SC 12', 'EB Garamond', Georgia, serif;
    font-size: 10pt;
    font-weight: normal;
    letter-spacing: 0.04em;
    margin-top: 1.2em;
    margin-bottom: 0.6em;
    page-break-after: avoid;
}}

/* ===== Paragraphs ===== */
p {{
    margin: 0.3em 0;
    text-indent: 0;
}}

/* ===== Proposition layout (Tractatus two-column) ===== */
.prop {{
    display: flex;
    align-items: flex-start;
    margin-top: 0.7em;
    margin-bottom: 0.3em;
    page-break-inside: avoid;
}}
.prop-num {{
    font-weight: normal;
    font-size: 10.5pt;
    min-width: 2.8em;
    max-width: 3.8em;
    flex-shrink: 0;
    padding-right: 0.6em;
    text-align: left;
    color: #111;
}}
.prop-body {{
    flex: 1;
    text-align: justify;
}}
.prop-body p {{
    margin: 0.2em 0;
}}
.prop-tag {{
    font-style: italic;
    font-size: 6pt;
    color: #aaa;
    vertical-align: super;
    margin-left: 0.1em;
    font-weight: normal;
}}

/* Depth-based styling: main props get extra weight */
.depth-0 {{
    margin-top: 1.5em;
}}
.depth-0 .prop-num {{
    font-weight: bold;
    font-size: 12pt;
}}
.depth-1 .prop-num {{
    font-size: 10.5pt;
}}
.depth-2 .prop-num {{
    font-size: 10pt;
    color: #222;
}}
.depth-3 .prop-num,
.depth-4 .prop-num {{
    font-size: 9.5pt;
    color: #333;
}}

/* ===== Blockquotes ===== */
blockquote {{
    margin: 0.6em 0 0.6em 1.2em;
    padding: 0;
    border: none;
    font-size: 10pt;
    font-style: italic;
    color: #222;
}}
blockquote p {{
    text-align: left;
    margin: 0.15em 0;
    font-style: italic;
}}
/* Math/formula blockquotes: not italic */
blockquote p strong {{
    font-style: normal;
}}

/* ===== Tables ===== */
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 0.8em 0;
    font-size: 8.5pt;
    page-break-inside: avoid;
}}
th, td {{
    border-bottom: 0.5pt solid #999;
    padding: 4px 6px;
    text-align: left;
    vertical-align: top;
}}
th {{
    border-bottom: 1pt solid #333;
    font-weight: bold;
    font-family: 'EB Garamond SC', 'EB Garamond SC 12', 'EB Garamond', Georgia, serif;
    font-size: 8pt;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}
tr:last-child td {{
    border-bottom: 0.5pt solid #999;
}}

/* ===== Horizontal rules ===== */
hr {{
    border: none;
    border-top: 0.4pt solid #aaa;
    margin: 2em auto;
    width: 30%;
}}

/* ===== Lists ===== */
ul, ol {{
    margin: 0.4em 0 0.4em 1.2em;
    padding: 0;
}}
li {{
    margin: 0.15em 0;
}}

/* ===== Code ===== */
code {{
    font-family: 'DejaVu Sans Mono', monospace;
    font-size: 9pt;
}}

/* ===== Front matter style ===== */
.front-matter {{
    page: frontmatter;
}}

/* ===== Logical connective intro (italic block before props) ===== */
.prop-body em:first-child {{
    display: block;
    font-size: 9.5pt;
    color: #444;
    margin-bottom: 0.3em;
}}

/* ===== Appendix ===== */
.appendix h2 {{
    page-break-before: always;
}}
"""


# ---------------------------------------------------------------------------
# Build HTML document
# ---------------------------------------------------------------------------

def build_html(md_text, page_size='130mm 200mm'):
    """Build complete HTML with Tractatus typography."""

    # Convert markdown to HTML
    html_body = md.markdown(md_text, extensions=['tables', 'smarty', 'attr_list'])

    # Apply Tractatus proposition layout
    html_body = tractatus_html(html_body)

    # Remove the markdown title block (we build our own title pages)
    # Remove everything up to first <h2> or first <hr>
    title_end = re.search(r'(<h2|<hr)', html_body)
    if title_end:
        preamble = html_body[:title_end.start()]
        # Check if preamble has the title/author info
        if 'TRACTATUS FORMAE' in preamble.upper() or 'Iver Raknes' in preamble:
            html_body = html_body[title_end.start():]

    css = tractatus_css(page_size=page_size)

    return f"""<!DOCTYPE html>
<html lang="nn">
<head>
<meta charset="utf-8">
<style>
{css}
</style>
</head>
<body>

<!-- Smutstittel (half-title) -->
<div class="half-title">
    <h1 style="border:none;">Tractatus Formae</h1>
</div>

<!-- Tittelside (title page) -->
<div class="title-page">
    <div class="tp-author">Iver Raknes Finne</div>
    <h1 style="border:none;">Tractatus<br>Formae</h1>
    <div class="subtitle">Ei substrat-uavhengig formteori</div>
</div>

<!-- Kolofon (verso av tittelsida) -->
<div class="colophon">
    <p>&copy; Iver Raknes Finne, 2026</p>
    <p>Institutt for design, Arkitektur- og designh&oslash;gskolen i Oslo</p>
    <p style="margin-top: 1em;">F&oslash;rsteutg&aring;ve</p>
    <p>Sett og brote av forfattaren</p>
</div>

<!-- Body -->
{html_body}

</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("TRACTATUS FORMAE — Byggjeskript for f\u00f8rsteutg\u00e5ve")
    print("=" * 55)

    # Load bibliography
    bib = parse_bibtex(BIB_FILE)
    print(f"  Bibliografi: {len(bib)} oppf\u00f8ringar")

    # Read markdown
    with open(INPUT, 'r', encoding='utf-8') as f:
        md_text = f.read()
    print(f"  Utkast: {len(md_text.splitlines())} liner")

    # Preprocess
    processed = preprocess(md_text, bib)

    # Build pocket format (130 × 200 mm)
    print("\n  Byggjer pocketbok (130 \u00d7 200 mm)...")
    html_pocket = build_html(processed, page_size='130mm 200mm')
    HTML(string=html_pocket).write_pdf(OUTPUT_POCKET)
    size_kb = os.path.getsize(OUTPUT_POCKET) // 1024
    print(f"  \u2713 {OUTPUT_POCKET} ({size_kb} KB)")

    # Build A4 for screen reading
    print("\n  Byggjer A4-versjon...")
    html_a4 = build_html(processed, page_size='A4')
    HTML(string=html_a4).write_pdf(OUTPUT_A4)
    size_kb = os.path.getsize(OUTPUT_A4) // 1024
    print(f"  \u2713 {OUTPUT_A4} ({size_kb} KB)")

    print("\n  Ferdig.")


if __name__ == '__main__':
    main()
