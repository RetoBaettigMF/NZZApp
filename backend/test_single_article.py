#!/usr/bin/env python3
"""Test scraping a single article to check content."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Import scraper
from scraper import NZZScraper

def test_single_article():
    """Test scraping one article."""
    scraper = NZZScraper()

    # Login
    print("Logging in...")
    if not scraper.login():
        print("Login failed")
        return

    # Test article URL
    test_url = "https://www.nzz.ch/schweiz/fdp-mann-will-psychotherapien-aus-der-grundversicherung-kippen-ld.1924921"

    print(f"\nScraping article: {test_url}")
    article = scraper.scrape_article(test_url)

    if article:
        print(f"\nTitle: {article['title']}")
        print(f"Category: {article['category']}")
        print(f"Content length: {len(article['content'])} characters")
        print(f"\nFirst 500 characters of content:")
        print(article['content'][:500])
        print("\n...")
        print(f"\nLast 300 characters of content:")
        print(article['content'][-300:])
    else:
        print("Failed to scrape article")

    # Cleanup
    scraper.cleanup_browser()

if __name__ == '__main__':
    test_single_article()
