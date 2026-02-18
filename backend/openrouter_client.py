#!/usr/bin/env python3
"""OpenRouter API Client für AI-basierte Textbereinigung."""
import os
import time
import requests
from typing import Optional


class OpenRouterClient:
    """Client für OpenRouter API."""

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key (falls None, wird aus .env gelesen)
            model: Model ID (default: google/gemini-2.5-flash-lite)
        """
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        self.model = model or os.getenv('OPENROUTER_MODEL', 'google/gemini-2.5-flash-lite')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.last_request_time = 0
        self.min_request_interval = 2.0  # Minimum 2 Sekunden zwischen Requests

        if not self.api_key:
            raise ValueError("OpenRouter API key nicht gefunden. Bitte OPENROUTER_API_KEY in .env setzen.")

    def clean_article_content(self, raw_content: str, title: str) -> Optional[str]:
        """
        Bereinigt Artikelinhalt mit AI.

        Args:
            raw_content: Roher Markdown-Content vom Scraper
            title: Artikel-Titel für Kontext

        Returns:
            Bereinigter und formatierter Markdown-Content oder None bei Fehler
        """
        prompt = self._build_cleaning_prompt(raw_content, title)

        # Rate limiting: wait if needed
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)

        try:
            self.last_request_time = time.time()
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Du bist ein Experte für die Bereinigung von Nachrichtenartikeln. Deine Aufgabe ist es, nur den reinen Artikelinhalt zu extrahieren und schön zu formatieren."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.1,  # Low temperature für konsistente Ergebnisse
                },
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            cleaned_content = result['choices'][0]['message']['content'].strip()
            return cleaned_content

        except requests.exceptions.Timeout:
            print(f"  ⚠ OpenRouter Timeout - verwende Original-Content")
            return None
        except requests.exceptions.RequestException as e:
            print(f"  ⚠ OpenRouter API Fehler: {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"  ⚠ Ungültiges Response-Format: {e}")
            return None

    def _build_cleaning_prompt(self, raw_content: str, title: str) -> str:
        """Erstellt den Prompt für die AI-Bereinigung."""
        return f"""Bereinige den folgenden NZZ-Artikel und entferne alle unerwünschten Elemente.

**ARTIKEL-TITEL:** {title}

**ROHER CONTENT:**
{raw_content}

**ANWEISUNGEN:**

**ENTFERNEN:**
1. Alle Website-Navigationselemente (Breadcrumbs, Menüs, Footer-Links)
2. Alle Verweise zu anderen Artikeln (z.B. "Lesen Sie auch...", "Mehr zum Thema...")
3. Social-Media-Buttons und -Texte (Teilen, Merken, etc.)
4. Autor-Bylines und Meta-Informationen AUSSER den Haupttext
5. Werbung, Promotion, Newsletter-Hinweise
6. Inline-Links zu anderen NZZ-Artikeln (aber externe Links behalten!)
7. Spiele-Verweise, Footer-Inhalte
8. "Zusammenfassung", "Teilen", "Merken" Texte

**BEHALTEN:**
1. Die Hauptüberschrift (als h1)
2. Den kompletten Artikeltext mit allen Absätzen
3. Zwischenüberschriften (als h2, h3)
4. Listen und Aufzählungen
5. Blockquotes/Zitate
6. Externe Links (z.B. zu Studien, Quellen)

**FORMATIERUNG:**
- Verwende sauberes Markdown
- Eine Leerzeile zwischen Absätzen
- Klare Überschriftenstruktur
- Listen mit `-` für Aufzählungen
- Blockquotes mit `>`

**OUTPUT:**
Gib NUR den bereinigten Markdown-Text zurück, OHNE zusätzliche Erklärungen oder Kommentare."""

    def test_connection(self) -> bool:
        """Testet die Verbindung zur OpenRouter API."""
        try:
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": "Test"}
                    ],
                    "max_tokens": 10
                },
                timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"OpenRouter Connection Test fehlgeschlagen: {e}")
            return False
