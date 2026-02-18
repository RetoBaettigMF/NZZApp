#!/usr/bin/env python3
"""Test AI-basierte Inhaltsbereinigung."""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from openrouter_client import OpenRouterClient

# Test-Content (beispielhaft mit unwünschten Elementen)
TEST_CONTENT = """# Testüberschrift

Autor: Max Mustermann

Teilen

Merken

Zusammenfassung

Dies ist der erste Absatz des eigentlichen Artikels. Hier steht wichtiger Inhalt.

[Lesen Sie auch: Ein anderer Artikel](/link/zu/artikel)

## Zwischenüberschrift

Mehr Artikelinhalt hier. Dies ist wichtig und sollte behalten werden.

[Externe Quelle](https://externe-website.com) - sollte bleiben!

### Noch eine Überschrift

Weiterer wichtiger Text.

[Mehr zum Thema: Related Article](/related)
## Mehr zum Thema

[Related Article 1](/link1)
[Related Article 2](/link2)

- Kontakt
- AGB und Datenschutz
"""

def main():
    print("=== OpenRouter AI Cleaning Test ===\n")

    # 1. Test Connection
    print("1. Teste OpenRouter Verbindung...")
    try:
        client = OpenRouterClient()
    except ValueError as e:
        print(f"✗ Initialisierung fehlgeschlagen: {e}")
        print("\nBitte setze OPENROUTER_API_KEY in der .env Datei:")
        print("  OPENROUTER_API_KEY=sk-or-v1-...")
        print("  OPENROUTER_MODEL=google/gemini-flash-1.5")
        return False

    if not client.test_connection():
        print("✗ Verbindung fehlgeschlagen")
        return False

    print("✓ Verbindung erfolgreich\n")

    # 2. Test Cleaning
    print("2. Teste AI-Bereinigung...")
    print(f"Input-Länge: {len(TEST_CONTENT)} Zeichen\n")

    cleaned = client.clean_article_content(TEST_CONTENT, "Test-Artikel")

    if cleaned:
        print("✓ Bereinigung erfolgreich\n")
        print("=== BEREINIGTER CONTENT ===")
        print(cleaned)
        print("\n=== ENDE ===\n")
        print(f"Output-Länge: {len(cleaned)} Zeichen")
        reduction = 100 * (1 - len(cleaned)/len(TEST_CONTENT))
        print(f"Reduktion: {len(TEST_CONTENT) - len(cleaned)} Zeichen ({reduction:.1f}%)")
        return True
    else:
        print("✗ Bereinigung fehlgeschlagen")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
