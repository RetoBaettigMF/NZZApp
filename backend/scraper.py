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
from openrouter_client import OpenRouterClient

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
        self.tracking_file = self.output_dir / 'scraped_articles.json'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.use_browser = False
        self.browser = None
        self.browser_context = None
        self.browser_page = None
        self.playwright = None

        # OpenRouter für AI-basierte Bereinigung
        try:
            self.ai_client = OpenRouterClient()
            print("✓ OpenRouter AI-Client initialisiert")
        except ValueError as e:
            print(f"⚠ OpenRouter nicht verfügbar: {e}")
            self.ai_client = None
        
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

            # Click login button (force=True umgeht allfällige Overlays)
            page.locator('text=Anmelden').first.click(force=True, timeout=10000)

            # Warte aktiv bis id-eu.piano.io geladen ist (max. 15s)
            # Hostname-Vergleich statt Substring (buy-eu.piano.io enthält id-eu.piano.io im Query-String)
            from urllib.parse import urlparse
            login_frame = None
            for _ in range(30):
                page.wait_for_timeout(500)
                for frame in page.frames:
                    if urlparse(frame.url).hostname == 'id-eu.piano.io':
                        login_frame = frame
                        break
                if login_frame:
                    break

            if not login_frame:
                raise Exception("Could not find Piano login iframe (id-eu.piano.io)")

            # Wait for inputs to be ready
            login_frame.wait_for_selector('input[name="email"]', timeout=10000)

            # Fill credentials in iframe
            login_frame.fill('input[name="email"]', self.email)
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

    def load_tracked_articles(self):
        """Lädt die Liste bereits gescrapter Artikel-URLs."""
        if not self.tracking_file.exists():
            return {'articles': [], 'last_updated': None}

        try:
            with open(self.tracking_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠ Tracking-Datei beschädigt, erstelle neue")
            return {'articles': [], 'last_updated': None}

    def save_tracked_articles(self, tracking_data):
        """Speichert die aktualisierte Tracking-Liste."""
        tracking_data['last_updated'] = datetime.now().isoformat()

        with open(self.tracking_file, 'w', encoding='utf-8') as f:
            json.dump(tracking_data, f, indent=2, ensure_ascii=False)

        print(f"✓ Tracking aktualisiert: {len(tracking_data['articles'])} Artikel total")

    def is_article_scraped(self, url, tracking_data):
        """Prüft ob Artikel bereits gescrapt wurde."""
        scraped_urls = {article['url'] for article in tracking_data['articles']}
        return url in scraped_urls

    def add_to_tracking(self, tracking_data, article_info, date_str):
        """Fügt einen gescrapten Artikel zur Tracking-Liste hinzu."""
        tracking_data['articles'].append({
            'url': article_info['url'],
            'scraped_date': date_str,
            'scraped_at': datetime.now().isoformat(),
            'filename': f"{date_str}/{article_info['category']}/{article_info.get('filename', 'unknown.md')}",
            'title': article_info['title']
        })

    def delete_recent_articles(self, hours=12):
        """Löscht Artikel der letzten N Stunden und entfernt sie aus dem Tracking."""
        print(f"\n→ Lösche Artikel der letzten {hours} Stunden...")
        cutoff = datetime.now() - timedelta(hours=hours)

        tracking_data = self.load_tracked_articles()
        urls_to_remove = set()
        affected_dates = set()

        for article in tracking_data['articles']:
            # Prüfe scraped_at Timestamp (neu) oder Datei-Mtime (alt)
            remove = False
            scraped_at = article.get('scraped_at')
            if scraped_at:
                try:
                    if datetime.fromisoformat(scraped_at) >= cutoff:
                        remove = True
                except ValueError:
                    pass

            if not remove:
                # Fallback: Datei-Mtime prüfen
                filepath = self.output_dir / article.get('filename', '')
                if filepath.exists() and datetime.fromtimestamp(filepath.stat().st_mtime) >= cutoff:
                    remove = True

            if remove:
                urls_to_remove.add(article['url'])
                affected_dates.add(article.get('scraped_date', ''))
                # Datei löschen
                filepath = self.output_dir / article.get('filename', '')
                if filepath.exists():
                    filepath.unlink()
                    print(f"  ✗ Gelöscht: {filepath.name}")

        # Tracking bereinigen
        before = len(tracking_data['articles'])
        tracking_data['articles'] = [
            a for a in tracking_data['articles'] if a['url'] not in urls_to_remove
        ]
        removed = before - len(tracking_data['articles'])
        self.save_tracked_articles(tracking_data)

        # ZIP und Manifest für betroffene Tage neu erstellen
        for date_str in affected_dates:
            if not date_str:
                continue
            date_folder = self.output_dir / date_str
            if date_folder.exists():
                self.create_zip(date_folder)
                self.update_manifest(date_folder)

        print(f"✓ {removed} Artikel gelöscht und aus Tracking entfernt")
        return removed

    def clean_article_html(self, soup):
        """Grundlegende HTML-Bereinigung (Bilder, Scripts, Ads)."""

        # Bilder entfernen
        for img in soup.find_all('img'):
            img.decompose()
        for figure in soup.find_all('figure'):
            figure.decompose()

        # Scripts und Styles entfernen
        for elem in soup.find_all(['script', 'style', 'noscript']):
            elem.decompose()

        # Offensichtliche Ads entfernen
        for elem in soup.find_all(class_=re.compile('ad-|advertisement', re.I)):
            elem.decompose()

        return soup

    def clean_markdown_content(self, content):
        """Basis-Bereinigung vor AI-Processing."""

        # Nur mehrfache Leerzeilen entfernen
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content.strip()

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

            # IMPORTANT: Clean unwanted content BEFORE removing images
            article = self.clean_article_html(article)

            # Remove ads and other noise
            for elem in article.find_all(class_=re.compile('ad-|advertisement|paywall|subscribe', re.I)):
                elem.decompose()

            # Content zu Markdown
            content = self.html_to_markdown(article)
            content = self.clean_text(content)

            # Basis-Bereinigung
            content = self.clean_markdown_content(content)

            # AI-BASED CLEANING (NEW)
            summary = ''
            if self.ai_client:
                print(f"    🤖 Bereinige Inhalt mit AI...")
                cleaned_content = self.ai_client.clean_article_content(content, title)

                if cleaned_content:
                    content = cleaned_content
                    print(f"    ✓ AI-Bereinigung erfolgreich ({len(content)} Zeichen)")
                else:
                    print(f"    ⚠ AI-Bereinigung fehlgeschlagen, verwende Original")

                print(f"    🤖 Erstelle Zusammenfassung...")
                generated_summary = self.ai_client.generate_summary(content, title)
                if generated_summary:
                    summary = generated_summary
                    print(f"    ✓ Zusammenfassung erstellt ({len(summary)} Zeichen)")
                else:
                    print(f"    ⚠ Zusammenfassung fehlgeschlagen")

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
                'content': content,
                'summary': summary
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

            # IMPORTANT: Clean unwanted content BEFORE removing images
            article = self.clean_article_html(article)

            # Content zu Markdown
            content = self.html_to_markdown(article)
            content = self.clean_text(content)

            # Basis-Bereinigung
            content = self.clean_markdown_content(content)

            # AI-BASED CLEANING (NEW)
            summary = ''
            if self.ai_client:
                print(f"    🤖 Bereinige Inhalt mit AI...")
                cleaned_content = self.ai_client.clean_article_content(content, title)

                if cleaned_content:
                    content = cleaned_content
                    print(f"    ✓ AI-Bereinigung erfolgreich ({len(content)} Zeichen)")
                else:
                    print(f"    ⚠ AI-Bereinigung fehlgeschlagen, verwende Original")

                print(f"    🤖 Erstelle Zusammenfassung...")
                generated_summary = self.ai_client.generate_summary(content, title)
                if generated_summary:
                    summary = generated_summary
                    print(f"    ✓ Zusammenfassung erstellt ({len(summary)} Zeichen)")
                else:
                    print(f"    ⚠ Zusammenfassung fehlgeschlagen")

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
                'content': content,
                'summary': summary
            }

        except Exception as e:
            print(f"✗ Fehler beim Scrapen von {url}: {e}")
            return None
    
    def get_article_links_with_browser(self):
        """Holt Artikel-Links mit Browser und Scrolling für lazy-loaded content."""
        print(f"→ Lade Artikel-Liste von {self.base_url} (mit Scrolling)...")

        try:
            page = self.browser_page
            page.goto(self.base_url, timeout=30000)

            # Wait for initial content
            try:
                page.wait_for_selector('a[href]', timeout=5000)
            except:
                pass

            links = set()
            pages_to_scroll = 10

            print(f"→ Scrolle durch {pages_to_scroll} Seiten für lazy-loaded Artikel...")

            for i in range(pages_to_scroll):
                # Scroll to bottom
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')

                # Wait for new content to load
                page.wait_for_timeout(2000)  # 2 seconds between scrolls

                # Extract links from current page state
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

                new_links_count = 0
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    # NZZ Artikel-URLs haben das Format /[kategorie]/[slug].[id]
                    if re.match(r'^/[\w-]+/[\w-]+\.\d+$', href):
                        full_url = urljoin('https://www.nzz.ch', href)
                        if full_url not in links:
                            new_links_count += 1
                            links.add(full_url)

                print(f"    Seite {i+1}/{pages_to_scroll}: {new_links_count} neue Links gefunden (Total: {len(links)})")

                # Stop if no new links found after scrolling
                if i > 2 and new_links_count == 0:
                    print(f"    → Keine neuen Links mehr, stoppe früher")
                    break

            print(f"✓ {len(links)} Artikel-Links gefunden nach Scrolling")
            return list(links)[:200]  # Limit auf 200 Artikel (mehr als vorher)

        except Exception as e:
            print(f"✗ Fehler beim Laden der Artikel-Liste mit Browser: {e}")
            return []

    def get_article_links(self):
        """Holt alle Artikel-Links von der neueste-artikel Seite."""
        # Use browser-based scraping if available (supports lazy-loading)
        if hasattr(self, 'use_browser') and self.use_browser and self.browser_page:
            return self.get_article_links_with_browser()

        # Fallback to simple requests (no lazy-loading support)
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

            print(f"✓ {len(links)} Artikel-Links gefunden (ohne Scrolling)")
            return list(links)[:100]  # Limit auf 100 Artikel

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

            # Filename in article speichern (für Tracking)
            article['filename'] = filename

            # Markdown-Datei schreiben
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# {article['title']}\n\n")
                f.write(f"**[→ Original auf NZZ.ch öffnen]({article['url']})**\n\n")
                f.write(f"**Datum:** {article['date']}\n\n")
                f.write(f"**Kategorie:** {article['category']}\n\n")
                if article.get('summary'):
                    f.write(f"**Zusammenfassung:** {article['summary']}\n\n")
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

    def update_manifest(self, date_folder):
        """Erstellt/aktualisiert Manifest für das Tages-Verzeichnis."""
        # Zähle ALLE Artikel im Ordner (nicht nur neu gescrapte)
        categories = {}
        total = 0

        for cat_folder in date_folder.iterdir():
            if cat_folder.is_dir():
                article_count = len(list(cat_folder.glob('*.md')))
                if article_count > 0:
                    categories[cat_folder.name] = article_count
                    total += article_count

        manifest = {
            'date': date_folder.name,
            'total_articles': total,
            'categories': categories
        }

        manifest_path = date_folder / 'manifest.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        print(f"✓ Manifest aktualisiert: {manifest_path}")

    def run(self):
        """Hauptfunktion - Scrapt nur neue Artikel und archiviert sie."""
        print(f"\n{'='*50}")
        print(f"NZZ Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*50}\n")

        # 1. Tracking laden
        tracking_data = self.load_tracked_articles()
        print(f"ℹ {len(tracking_data['articles'])} Artikel bereits gescrapt")

        # 2. Login
        if not self.login():
            print("✗ Abbruch: Login fehlgeschlagen")
            return False

        # 3. Artikel-Links holen
        all_links = self.get_article_links()
        if not all_links:
            print("✗ Keine Artikel gefunden")
            return False

        # 4. NEUE ARTIKEL filtern
        new_links = [link for link in all_links
                     if not self.is_article_scraped(link, tracking_data)]

        print(f"ℹ {len(all_links)} Links gefunden, {len(new_links)} sind NEU")

        if len(new_links) == 0:
            print("✓ Keine neuen Artikel zum Scrapen")
            self.cleanup_browser()
            return True

        # 5. Datum-Ordner (heutiger Tag)
        today = datetime.now().strftime('%Y-%m-%d')
        date_folder = self.output_dir / today
        date_folder.mkdir(parents=True, exist_ok=True)

        # 6. NUR NEUE Artikel scrapen
        print(f"→ Scraping {len(new_links)} neue Artikel...")
        articles = []
        for i, link in enumerate(new_links, 1):
            print(f"  [{i}/{len(new_links)}] {link}")
            article = self.scrape_article(link)
            if article:
                articles.append(article)
                # Sofort zum Tracking hinzufügen
                self.add_to_tracking(tracking_data, article, today)

        print(f"✓ {len(articles)} neue Artikel erfolgreich gescrapt")

        # 7. Neue Artikel speichern
        saved = self.save_articles(articles, date_folder)
        print(f"✓ {saved} neue Artikel gespeichert in {date_folder}")

        # 8. Tracking-Datei speichern
        self.save_tracked_articles(tracking_data)

        # 9. ZIP für HEUTE erstellen (überschreibt bestehendes)
        zip_path = self.create_zip(date_folder)
        print(f"✓ ZIP aktualisiert: {zip_path}")

        # 10. Manifest aktualisieren
        self.update_manifest(date_folder)

        # 11. Browser aufräumen
        self.cleanup_browser()

        print(f"\n{'='*50}")
        print("✓ Scraping abgeschlossen!")
        print(f"{'='*50}\n")

        return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='NZZ Artikel Scraper')
    parser.add_argument(
        '--rescrape',
        nargs='?',
        const=12,
        type=int,
        metavar='STUNDEN',
        help='Löscht Artikel der letzten N Stunden und scrapt neu (Standard: 12)'
    )
    args = parser.parse_args()

    scraper = NZZScraper()

    if args.rescrape is not None:
        scraper.delete_recent_articles(hours=args.rescrape)

    scraper.run()


if __name__ == '__main__':
    main()
