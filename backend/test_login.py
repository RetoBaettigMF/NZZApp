#!/usr/bin/env python3
"""Test NZZ login flow with browser automation."""
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

def test_login():
    """Test browser automation login and extract cookies."""
    email = os.getenv('NZZ_EMAIL')
    password = os.getenv('NZZ_PASSWORD')

    if not email or not password:
        print("✗ NZZ_EMAIL and NZZ_PASSWORD must be set in .env")
        return None

    print(f"Testing login with email: {email}")

    with sync_playwright() as p:
        # Run in headless mode (set to False if you have a display for debugging)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Enable console logs for debugging
        page.on('console', lambda msg: print(f"Browser: {msg.text}"))

        try:
            print("1. Navigating to NZZ...")
            page.goto('https://www.nzz.ch', timeout=30000)

            print("2. Accepting cookies...")
            try:
                # Accept cookie consent if it appears
                page.click('text=Alle Anbieter akzeptieren', timeout=5000)
                print("   ✓ Cookie consent accepted")
            except:
                print("   (No cookie consent dialog)")

            print("3. Clicking Anmelden...")
            page.click('text=Anmelden', timeout=10000)

            print("4. Waiting for Piano login iframe...")
            # Wait for Piano iframe to load
            page.wait_for_timeout(3000)

            # Find the Piano iframe
            login_frame = None
            for frame in page.frames:
                if 'piano.io' in frame.url:
                    login_frame = frame
                    print(f"   ✓ Found Piano iframe: {frame.url[:60]}")
                    break

            if not login_frame:
                raise Exception("Could not find Piano login iframe")

            # Wait for inputs to be ready in the iframe
            login_frame.wait_for_selector('input[type="text"]', timeout=10000)

            print("5. Filling email...")
            login_frame.fill('input[type="text"]', email)

            print("6. Filling password...")
            login_frame.fill('input[type="password"]', password)

            print("7. Clicking submit...")
            login_frame.click('button[type="submit"]')

            print("8. Waiting for login to complete...")
            # Wait for the iframe to close (login complete)
            page.wait_for_timeout(5000)

            # Check for login success indicators
            page_content = page.content()
            is_logged_in = False

            # Check various login indicators
            if 'abmelden' in page_content.lower():
                is_logged_in = True
                print("✓ Login successful! (found 'Abmelden')")
            elif 'mein konto' in page_content.lower() or 'my account' in page_content.lower():
                is_logged_in = True
                print("✓ Login successful! (found account menu)")
            elif 'logout' in page_content.lower() or 'sign out' in page_content.lower():
                is_logged_in = True
                print("✓ Login successful! (found logout)")
            else:
                # Try checking cookies for session
                cookies = context.cookies()
                session_cookies = [c for c in cookies if 'session' in c['name'].lower() or 'auth' in c['name'].lower()]
                if session_cookies:
                    is_logged_in = True
                    print(f"✓ Login appears successful! (found {len(session_cookies)} session cookies)")
                else:
                    print("⚠ Could not confirm login status")

            if not is_logged_in:
                print("\n⚠ Login status unclear - check screenshot")
                page.screenshot(path='login_complete.png')
                print("Screenshot saved to login_complete.png")

            # Extract cookies
            cookies = context.cookies()
            print(f"✓ Extracted {len(cookies)} cookies")

            # Print cookie names (not values for security)
            for cookie in cookies:
                print(f"  - {cookie['name']}")

            browser.close()
            return cookies

        except Exception as e:
            print(f"✗ Login failed: {e}")
            # Take screenshot for debugging
            page.screenshot(path='login_error.png')
            print("Screenshot saved to login_error.png")
            browser.close()
            raise

if __name__ == '__main__':
    test_login()
