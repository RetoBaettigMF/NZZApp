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
        self.use_browser = False
        self.browser = None
        self.browser_context = None
        self.browser_page = None
        self.playwright = None
        
    def login_with_browser(self):
        """Login using Playwright browser automation and return browser context."""
        from playwright.sync_api import sync_playwright

        print("→ Starte Browser für Authentifizierung...")

        # Start Playwright and keep it alive
        self.playwright = sync_playwright().start()
        browser = self.playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Navigate to NZZ
            page.goto('https://www.nzz.ch', timeout=30000)

            # Accept cookie consent if it appears
            try:
                page.click('text=Alle Anbieter akzeptieren', timeout=5000)
            except:
                pass  # No cookie consent dialog

            # Click login button
            page.click('text=Anmelden', timeout=10000)

            # Wait for Piano iframe to load
            page.wait_for_timeout(3000)

            # Find the Piano iframe
            login_frame = None
            for frame in page.frames:
                if 'piano.io' in frame.url:
                    login_frame = frame
                    break

            if not login_frame:
                raise Exception("Could not find Piano login iframe")

            # Wait for inputs to be ready
            login_frame.wait_for_selector('input[type="text"]', timeout=10000)

            # Fill credentials in iframe
            login_frame.fill('input[type="text"]', self.email)
            login_frame.fill('input[type="password"]', self.password)

            # Submit form
            login_frame.click('button[type="submit"]')

            # Wait for login to complete (iframe closes)
            page.wait_for_timeout(5000)

            print(f"✓ Browser-Session authentifiziert")

            # Store browser context for article scraping
            self.browser = browser
            self.browser_context = context
            self.browser_page = page

            return True

        except Exception as e:
            print(f"✗ Browser-Login fehlgeschlagen: {e}")
            page.screenshot(path='login_error.png')
            browser.close()
            self.playwright.stop()
            raise

    def login(self):
        """Login bei NZZ mit Browser-Automation."""
        if not self.email or not self.password:
            print("ℹ Keine Login-Daten konfiguriert - fahre ohne Authentifizierung fort")
            self.use_browser = False
            return True  # Continue with public scraping

        print("→ Authentifiziere mit NZZ...")

        try:
            # Perform browser-based login and keep browser alive
            self.login_with_browser()
            self.use_browser = True
            print("✓ Login erfolgreich - vollständiger Zugriff auf Artikel")
            return True

        except Exception as e:
            print(f"✗ Login-Fehler: {e}")
            print("ℹ Fahre mit öffentlichen Artikeln fort")
            self.use_browser = False
            return True  # Graceful fallback

    def cleanup_browser(self):
        """Close browser and cleanup resources."""
        if hasattr(self, 'browser') and self.browser:
            try:
                self.browser.close()
                self.playwright.stop()
                print("✓ Browser-Session beendet")
            except:
                pass
    
    def is_paywalled(self, soup):
        """Detect if article content is behind paywall."""
        # Piano paywall indicators
        paywall_indicators = [
            soup.find(id=re.compile('piano.*paywall', re.I)),
            soup.find(class_=re.compile('paywall|subscribe-wall', re.I)),
            'Abonnieren Sie' in soup.get_text(),
            'Jetzt abonnieren' in soup.get_text()
        ]

        return any(paywall_indicators)

    def validate_content_length(self, content, url):
        """Check if content seems complete."""
        min_length = 500  # Typical NZZ article

        if len(content) < min_length:
            print(f"    ⚠ Kurzer Inhalt ({len(content)} Zeichen) - möglicherweise unvollständig")
            return False
        return True

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
    
    def scrape_article_with_browser(self, url):
        """Scrapt einen einzelnen Artikel mit Browser-Session."""
        try:
            # Use existing browser page
            page = self.browser_page
            page.goto(url, timeout=30000)

            # Wait for article content to load
            try:
                page.wait_for_selector('article, main', timeout=5000)
            except:
                pass  # Continue anyway

            # Brief wait for dynamic content
            page.wait_for_timeout(2000)

            # Get page HTML
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

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

            # Artikel-Content finden - NZZ-specific selectors first
            article = None

            # Try NZZ-specific content selectors
            content_selectors = [
                'article',
                '[class*="articleContent"]',
                '[class*="article-content"]',
                '[class*="ArticleContent"]',
                'main [class*="content"]',
                'main',
                '[role="main"]',
                'div[class*="article"]'
            ]

            for selector in content_selectors:
                article = soup.select_one(selector)
                if article and len(article.get_text(strip=True)) > 200:
                    break

            if not article:
                article = soup.find('body')

            # Bilder entfernen
            for img in article.find_all('img'):
                img.decompose()
            for figure in article.find_all('figure'):
                figure.decompose()
            # Remove ads and other noise
            for elem in article.find_all(class_=re.compile('ad-|advertisement|paywall|subscribe', re.I)):
                elem.decompose()

            # Content zu Markdown
            content = self.html_to_markdown(article)
            content = self.clean_text(content)

            # Kategorie bestimmen
            category = self.extract_category(soup, url)

            # Add paywall detection
            if self.is_paywalled(soup):
                print(f"    ⚠ Paywall erkannt auf {url}")

            # Validate content length
            self.validate_content_length(content, url)

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

    def scrape_article(self, url):
        """Scrapt einen einzelnen Artikel."""
        # Use browser if available, otherwise fall back to requests
        if hasattr(self, 'use_browser') and self.use_browser:
            return self.scrape_article_with_browser(url)

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

            # Add paywall detection
            if self.is_paywalled(soup):
                print(f"    ⚠ Paywall erkannt auf {url}")

            # Validate content length
            self.validate_content_length(content, url)

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

        # Cleanup browser if used
        self.cleanup_browser()

        print(f"\n{'='*50}")
        print("✓ Scraping abgeschlossen!")
        print(f"{'='*50}\n")

        return True


def main():
    scraper = NZZScraper()
    scraper.run()


if __name__ == '__main__':
    main()
