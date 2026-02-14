#!/usr/bin/env python3
"""
Scheduler - Startet den Scraper täglich um 06:00 Uhr.
"""
import os
import sys
import time
import schedule
from datetime import datetime
from pathlib import Path

# Füge das Backend-Verzeichnis zum Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import NZZScraper

def job():
    """Die tägliche Scraping-Job."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starte täglichen Scraper...")
    scraper = NZZScraper()
    success = scraper.run()
    if success:
        print("✓ Job erfolgreich abgeschlossen")
    else:
        print("✗ Job fehlgeschlagen")
    print(f"Nächster Lauf: {schedule.next_run()}")

def run_scheduler():
    """Startet den Scheduler."""
    print("="*50)
    print("NZZ Scraper Scheduler")
    print("="*50)
    print(f"Startzeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Job läuft täglich um 06:00 Uhr")
    print("="*50)
    
    # Job für 06:00 Uhr planen
    schedule.every().day.at("06:00").do(job)
    
    # Optional: Beim Start direkt einmal ausführen
    if len(sys.argv) > 1 and sys.argv[1] == '--run-now':
        print("→ Führe sofortigen Lauf aus...")
        job()
    
    print(f"Nächster Lauf: {schedule.next_run()}")
    print("\nScheduler läuft... (Ctrl+C zum Beenden)\n")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Jede Minute prüfen
    except KeyboardInterrupt:
        print("\n✓ Scheduler beendet")

if __name__ == '__main__':
    run_scheduler()
