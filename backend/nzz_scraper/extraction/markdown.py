"""HTML-Bereinigung und Markdown-Konvertierung.

Wörtlich aus scraper.py übernommen (clean_article_html, html_to_markdown,
clean_text, clean_markdown_content) – die Ausgabe muss bit-identisch bleiben,
weil das Frontend die erzeugten Dateien parst.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

_MD_TAGS = ['h1', 'h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li', 'a',
            'strong', 'em', 'blockquote']
_AD_PATTERN = re.compile('ad-|advertisement', re.I)
_NOISE_PATTERN = re.compile('ad-|advertisement|paywall|subscribe', re.I)


def clean_article_html(soup: BeautifulSoup) -> BeautifulSoup:
    """Entfernt Bilder, Scripts/Styles und offensichtliche Werbung."""
    for img in soup.find_all('img'):
        img.decompose()
    for figure in soup.find_all('figure'):
        figure.decompose()
    for elem in soup.find_all(['script', 'style', 'noscript']):
        elem.decompose()
    for elem in soup.find_all(class_=_AD_PATTERN):
        elem.decompose()
    return soup


def remove_noise(soup: BeautifulSoup) -> BeautifulSoup:
    """Entfernt zusätzlich Paywall-/Abo-Container aus dem Artikel-Container."""
    for elem in soup.find_all(class_=_NOISE_PATTERN):
        elem.decompose()
    return soup


def html_to_markdown(soup: BeautifulSoup) -> str:
    """Konvertiert HTML zu Markdown."""
    md_lines = []

    for elem in soup.find_all(_MD_TAGS):
        text = elem.get_text(strip=True)
        if not text:
            continue

        if elem.name == 'h1':
            md_lines.append(f"# {text}\n")
        elif elem.name == 'h2':
            md_lines.append(f"## {text}\n")
        elif elem.name == 'h3':
            md_lines.append(f"### {text}\n")
        elif elem.name == 'h4':
            md_lines.append(f"#### {text}\n")
        elif elem.name == 'p':
            md_lines.append(f"{text}\n")
        elif elem.name == 'li':
            md_lines.append(f"- {text}")
        elif elem.name == 'blockquote':
            md_lines.append(f"> {text}\n")
        elif elem.name == 'a':
            href = elem.get('href', '')
            if href and not href.startswith('#'):
                md_lines.append(f"[{text}]({href})")

    return '\n'.join(md_lines)


def clean_text(text: str) -> str:
    """Bereinigt den Text."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    return text.strip()


def clean_markdown_content(content: str) -> str:
    """Basis-Bereinigung vor AI-Processing."""
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def html_fragment_to_markdown(html: str) -> str:
    """Kompletter Pfad: HTML-Fragment → bereinigtes Markdown."""
    soup = BeautifulSoup(html, 'html.parser')
    soup = clean_article_html(soup)
    soup = remove_noise(soup)
    return clean_markdown_content(clean_text(html_to_markdown(soup)))


def link_text_ratio(html: str) -> float:
    """Anteil des Textes, der in <a>-Tags steckt – entlarvt Übersichtsseiten."""
    soup = BeautifulSoup(html, 'html.parser')
    total = len(soup.get_text(strip=True))
    if not total:
        return 1.0
    linked = sum(len(a.get_text(strip=True)) for a in soup.find_all('a'))
    return linked / total


def paragraph_count(markdown: str) -> int:
    """Zählt Absätze im erzeugten Markdown."""
    return len([b for b in re.split(r'\n\s*\n', markdown) if b.strip()])
