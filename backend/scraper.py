#!/usr/bin/env python3
"""
NZZ Artikel Scraper - Scrapt Artikel und speichert sie als Markdown.
"""
import os
import sys
import re
import json
import zipfile
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from dateutil import parser as date_parser

load_dotenv()

class NZZScraper:
    CATEGORIES = {
        'sport': ['sport', 'fussball', 'tennis', 'ski', 'formel 1'],
        'wirtschaft': ['wirtschaft', 'finanzen', 'börse', 'unternehmen', 'geld'],
        'wissenschaft': ['wissenschaft', 'forschung', 'technologie', 'medizin', 'gesundheit'],
        'lokal': ['zürich', 'schweiz', 'zuerich', 'bern', 'basel', 'genf'],
        'welt': ['international', 'ausland', 'europa', 'usa', 'asien']
    }
    
    def __init__(self):
        self.email = os.getenv('NZZ_EMAIL')
        self.password = os.getenv('NZZ_PASSWORD')
        self.output_dir = Path(os.getenv('OUTPUT_DIR', './articles'))
        self.base_url = os.getenv('BASE_URL', 'https://www.nzz.ch/neueste-artikel')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def login(self):
        """Login bei NZZ."""
        print("→ Login bei NZZ...")
        
        # Zuerst die Login-Seite laden
        login_url = "https://login.nzz.ch/"
        resp = self.session.get(login_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Login-Formular finden und absenden
        login_data = {
            'email': self.email,
            'password': self.password,
        }
        
        # CSRF Token extrahieren falls vorhanden
        csrf = soup.find('input', {'name': '_csrf'})
        if csrf:
            login_data['_csrf'] = csrf.get('value')
        
        resp = self.session.post(login_url, data=login_data, allow_redirects=True)
        
        if 'abmelden' in resp.text.lower() or resp.status_code == 200:
            print("✓ Login erfolgreich")
            return True
        else:
            print("✗ Login fehlgeschlagen")
            return False
    
    def extract_category(self, article_soup, url):
        """Extrahiert die Kategorie aus dem Artikel."""
        # Versuche aus Breadcrumbs oder Meta-Tags zu lesen
        category = 'allgemein'
        
        # Aus URL extrahieren
        url_parts = url.replace('https://www.nzz.ch/', '').split('/')
        if len(url_parts) > 0:
            url_cat = url_parts[0].lower()
            
            for cat_name, keywords in self.CATEGORIES.items():
                if any(kw in url_cat or kw in url.lower() for kw in keywords):
                    return cat_name
        
        # Aus Artikel-Text extrahieren
        text_content = article_soup.get_text().lower()
        for cat_name, keywords in self.CATEGORIES.items():
            if any(kw in text_content[:500] for kw in keywords):
                return cat_name
        
        return category
    
    def clean_text(self, text):
        """Bereinigt den Text."""
        # Mehrfache Leerzeilen entfernen
        text = re.sub(r'\n{3,}', '\n\n', text)
        # HTML-Entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        return text.strip()
    
    def html_to_markdown(self, soup):
        """Konvertiert HTML zu Markdown."""
        md_lines = []
        
        for elem in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li', 'a', 'strong', 'em', 'blockquote']):
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
    
    def scrape_article(self, url):
        """Scrapt einen einzelnen Artikel."""
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Titel extrahieren
            title_tag = soup.find('h1') or soup.find('title')
            title = title_tag.get_text(strip=True) if title_tag else "Unbekannter Titel"
            
            # Datum extrahieren
            date = datetime.now()
            time_tag = soup.find('time')
            if time_tag and time_tag.get('datetime'):
                try:
                    date = date_parser.parse(time_tag['datetime'])
                except:
                    pass
            
            # Artikel-Content finden
            article = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile('article|content'))
            if not article:
                article = soup.find('body')
            
            # Bilder entfernen
            for img in article.find_all('img'):
                img.decompose()
            for figure in article.find_all('figure'):
                figure.decompose()
            
            # Content zu Markdown
            content = self.html_to_markdown(article)
            content = self.clean_text(content)
            
            # Kategorie bestimmen
            category = self.extract_category(soup, url)
            
            return {
                'title': title,
                'url': url,
                'date': date.isoformat(),
                'category': category,
                'content': content
            }
            
        except Exception as e:
            print(f"✗ Fehler beim Scrapen von {url}: {e}")
            return None
    
    def get_article_links(self):
        """Holt alle Artikel-Links von der neueste-artikel Seite."""
        print(f"→ Lade Artikel-Liste von {self.base_url}...")
        
        try:
            resp = self.session.get(self.base_url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            links = set()
            for a in soup.find_all('a', href=True):
                href = a['href']
                # NZZ Artikel-URLs haben das Format /[kategorie]/[slug].[id]
                if re.match(r'^/[\w-]+/[\w-]+\.\d+$', href):
                    full_url = urljoin('https://www.nzz.ch', href)
                    links.add(full_url)
            
            print(f"✓ {len(links)} Artikel-Links gefunden")
            return list(links)[:50]  # Limit auf 50 Artikel
            
        except Exception as e:
            print(f"✗ Fehler beim Laden der Artikel-Liste: {e}")
            return []
    
    def save_articles(self, articles, date_folder):
        """Speichert Artikel als Markdown-Dateien."""
        saved = 0
        
        for article in articles:
            if not article:
                continue
            
            # Kategorie-Ordner erstellen
            cat_folder = date_folder / article['category']
            cat_folder.mkdir(parents=True, exist_ok=True)
            
            # Dateiname aus Titel generieren
            safe_title = re.sub(r'[^\w\s-]', '', article['title'])[:50].strip()
            filename = f"{safe_title.replace(' ', '_')}.md"
            filepath = cat_folder / filename
            
            # Markdown-Datei schreiben
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# {article['title']}\n\n")
                f.write(f"**Datum:** {article['date']}\n\n")
                f.write(f"**Kategorie:** {article['category']}\n\n")
                f.write(f"**URL:** {article['url']}\n\n")
                f.write(f"---\n\n")
                f.write(article['content'])
            
            saved += 1
        
        return saved
    
    def create_zip(self, date_folder):
        """Erstellt ein ZIP-Archiv des Tages."""
        zip_path = date_folder.with_suffix('.zip')
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in date_folder.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(date_folder.parent)
                    zf.write(file_path, arcname)
        
        print(f"✓ ZIP erstellt: {zip_path}")
        return zip_path
    
    def run(self):
        """Hauptfunktion - Scrapt Artikel und archiviert sie."""
        print(f"\n{'='*50}")
        print(f"NZZ Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*50}\n")
        
        # Login
        if not self.login():
            print("✗ Abbruch: Login fehlgeschlagen")
            return False
        
        # Artikel-Links holen
        links = self.get_article_links()
        if not links:
            print("✗ Keine Artikel gefunden")
            return False
        
        # Datum-Ordner erstellen
        today = datetime.now().strftime('%Y-%m-%d')
        date_folder = self.output_dir / today
        date_folder.mkdir(parents=True, exist_ok=True)
        
        # Artikel scrapen
        print(f"→ Scraping {len(links)} Artikel...")
        articles = []
        for i, link in enumerate(links, 1):
            print(f"  [{i}/{len(links)}] {link}")
            article = self.scrape_article(link)
            if article:
                articles.append(article)
        
        print(f"✓ {len(articles)} Artikel erfolgreich gescrapt")
        
        # Speichern
        saved = self.save_articles(articles, date_folder)
        print(f"✓ {saved} Artikel gespeichert in {date_folder}")
        
        # ZIP erstellen
        zip_path = self.create_zip(date_folder)
        
        # Manifest erstellen
        manifest = {
            'date': today,
            'total_articles': len(articles),
            'categories': {}
        }
        for article in articles:
            cat = article['category']
            manifest['categories'][cat] = manifest['categories'].get(cat, 0) + 1
        
        manifest_path = date_folder / 'manifest.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"✓ Manifest erstellt: {manifest_path}")
        print(f"\n{'='*50}")
        print("✓ Scraping abgeschlossen!")
        print(f"{'='*50}\n")
        
        return True


def main():
    scraper = NZZScraper()
    scraper.run()


if __name__ == '__main__':
    main()
