#!/usr/bin/env python3
"""
Migration Script - Initialisiert Tracking-Datei aus bestehenden Artikeln.

Dieses Script durchsucht alle bestehenden Artikel-Verzeichnisse und
erstellt eine scraped_articles.json mit allen URLs, die bereits
heruntergeladen wurden.
"""
from pathlib import Path
import json
import re
from datetime import datetime


def extract_url_from_markdown(md_file):
    """Extrahiert die URL aus einer Markdown-Datei."""
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                # Suche nach dem Link-Pattern: **[→ Original auf NZZ.ch öffnen](URL)**
                if 'Original auf NZZ.ch' in line:
                    match = re.search(r'\((https://www\.nzz\.ch/[^\)]+)\)', line)
                    if match:
                        return match.group(1)
    except Exception as e:
        print(f"  ⚠ Fehler beim Lesen von {md_file}: {e}")
    return None


def extract_title_from_markdown(md_file):
    """Extrahiert den Titel aus einer Markdown-Datei."""
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            # Titel ist in der ersten Zeile: # Titel
            if first_line.startswith('# '):
                return first_line[2:].strip()
    except Exception:
        pass
    return md_file.stem  # Fallback: Dateiname ohne Endung


def main():
    output_dir = Path('./articles')
    tracking_file = output_dir / 'scraped_articles.json'

    print(f"\n{'='*50}")
    print("NZZ Scraper - Tracking Migration")
    print(f"{'='*50}\n")

    # Prüfe ob Tracking-Datei bereits existiert
    if tracking_file.exists():
        print(f"⚠ Tracking-Datei existiert bereits: {tracking_file}")
        response = input("  Überschreiben? (y/n): ")
        if response.lower() != 'y':
            print("✗ Migration abgebrochen")
            return

    tracking = {'articles': [], 'last_updated': None}
    urls_seen = set()  # Zur Duplikatserkennung

    # Durchsuche alle Datum-Ordner (Format: 2026-02-17)
    date_folders = sorted([d for d in output_dir.glob('20*-*-*') if d.is_dir()])

    if not date_folders:
        print("ℹ Keine bestehenden Artikel-Ordner gefunden")
        print("✓ Leere Tracking-Datei wird erstellt")
    else:
        print(f"ℹ {len(date_folders)} Datum-Ordner gefunden\n")

        # Durchsuche jeden Datum-Ordner
        for date_folder in date_folders:
            print(f"→ Verarbeite {date_folder.name}...")
            articles_in_folder = 0

            # Durchsuche Kategorie-Ordner
            for cat_folder in date_folder.iterdir():
                if not cat_folder.is_dir():
                    continue

                category = cat_folder.name

                # Durchsuche Markdown-Dateien
                for md_file in cat_folder.glob('*.md'):
                    url = extract_url_from_markdown(md_file)
                    if not url:
                        print(f"  ⚠ Keine URL gefunden in {md_file.name}")
                        continue

                    # Duplikate überspringen
                    if url in urls_seen:
                        print(f"  ⚠ Duplikat übersprungen: {md_file.name}")
                        continue

                    urls_seen.add(url)
                    title = extract_title_from_markdown(md_file)

                    tracking['articles'].append({
                        'url': url,
                        'scraped_date': date_folder.name,
                        'filename': f"{date_folder.name}/{category}/{md_file.name}",
                        'title': title
                    })

                    articles_in_folder += 1

            print(f"  ✓ {articles_in_folder} Artikel gefunden\n")

    # Tracking-Datei speichern
    tracking['last_updated'] = datetime.now().isoformat()

    with open(tracking_file, 'w', encoding='utf-8') as f:
        json.dump(tracking, f, indent=2, ensure_ascii=False)

    print(f"{'='*50}")
    print(f"✓ Tracking-Datei erstellt: {tracking_file}")
    print(f"✓ {len(tracking['articles'])} Artikel zum Tracking hinzugefügt")
    print(f"{'='*50}\n")


if __name__ == '__main__':
    main()
