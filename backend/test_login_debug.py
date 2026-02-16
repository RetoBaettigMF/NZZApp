#!/usr/bin/env python3
"""Debug NZZ login - check what's on the page."""
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

def debug_login():
    """Debug what appears after clicking Anmelden."""
    email = os.getenv('NZZ_EMAIL')
    password = os.getenv('NZZ_PASSWORD')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            print("1. Navigating to NZZ...")
            page.goto('https://www.nzz.ch', timeout=30000)

            print("2. Accepting cookies...")
            try:
                page.click('text=Alle Anbieter akzeptieren', timeout=5000)
            except:
                print("   (No cookie consent)")

            print("3. Clicking Anmelden...")
            page.click('text=Anmelden', timeout=10000)

            print("4. Waiting for page to update...")
            page.wait_for_timeout(3000)

            print("\n5. Checking for iframes...")
            frames = page.frames
            print(f"   Total frames: {len(frames)}")
            for i, frame in enumerate(frames):
                print(f"   Frame {i}: {frame.url[:80]}")

            print("\n6. Looking for login inputs in main page...")
            email_inputs = page.query_selector_all('input[type="text"], input[type="email"], input[placeholder*="mail"], input[placeholder*="Mail"]')
            print(f"   Found {len(email_inputs)} potential email inputs in main page")

            print("\n7. Looking for login inputs in frames...")
            for i, frame in enumerate(frames):
                email_in_frame = frame.query_selector_all('input')
                if email_in_frame:
                    print(f"   Frame {i} has {len(email_in_frame)} inputs")
                    for inp in email_in_frame:
                        placeholder = inp.get_attribute('placeholder') or ''
                        input_type = inp.get_attribute('type') or ''
                        print(f"      - type='{input_type}', placeholder='{placeholder}'")

            print("\n8. Checking for Piano-specific elements...")
            piano_elements = page.query_selector_all('[class*="piano"], [id*="piano"]')
            print(f"   Found {len(piano_elements)} Piano elements")

            page.screenshot(path='login_debug.png')
            print("\n✓ Debug screenshot saved to login_debug.png")

            browser.close()

        except Exception as e:
            print(f"\n✗ Error: {e}")
            page.screenshot(path='login_debug_error.png')
            browser.close()
            raise

if __name__ == '__main__':
    debug_login()
