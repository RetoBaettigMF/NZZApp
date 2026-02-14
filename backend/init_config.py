#!/usr/bin/env python3
"""
Initialisiert die .env Datei mit dem NZZ Passwort.
Wird beim ersten Mal ausgeführt.
"""
import os
import getpass

env_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(env_path):
    print("✓ .env Datei existiert bereits.")
    exit(0)

print("=== NZZ Reader - Ersteinrichtung ===")
print("Bitte gib dein NZZ Login-Passwort ein:")
password = getpass.getpass("Passwort: ")

with open(env_path, 'w') as f:
    f.write(f"NZZ_EMAIL=reto@baettig.org\n")
    f.write(f"NZZ_PASSWORD={password}\n")
    f.write(f"OUTPUT_DIR=./articles\n")
    f.write(f"BASE_URL=https://www.nzz.ch/neueste-artikel\n")

print("✓ .env Datei erstellt.")
print("✓ Setup abgeschlossen!")
