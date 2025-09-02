import time
import random
import logging
import re
from dataclasses import dataclass, asdict
from typing import List, Iterable, Optional, Tuple
import requests
from bs4 import BeautifulSoup, Tag
import pandas as pd
from urllib.parse import quote_plus

logging.basicConfig(level=logging.INFO, format="%(message)s")

USER_AGENTS = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16 Safari/605.1.15",
  "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0",
]

AMAZON_BASE = "https://www.amazon.in"
BADGE_PREFIX = "amazon's choice"


@dataclass
class ChoiceProduct:
  keyword: str
  asin: str
  title: Optional[str]
  price: Optional[str]
  url: Optional[str]
  badge_for: Optional[str]


class AmazonChoiceScraper:
  def __init__(
    self,
    session: Optional[requests.Session] = None,
    min_delay: float = 20.0,
    max_delay: float = 40.0,
    max_retries: int = 6,
  ):
    self.session = session or requests.Session()
    self.min_delay = min_delay
    self.max_delay = max_delay
    self.max_retries = max_retries

  def build_search_url(self, keyword: str) -> str:
    return f"{AMAZON_BASE}/s?k={quote_plus(keyword)}"

  def _request(self, url: str) -> BeautifulSoup:
    # small random wait before making the request to avoid bursts
    time.sleep(random.uniform(1.0, 3.0))

    headers = {
      "User-Agent": random.choice(USER_AGENTS),
      "Accept-Language": "en-US,en;q=0.9",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Referer": AMAZON_BASE + "/",
    }

    last_exc = None
    for attempt in range(1, self.max_retries + 1):
      try:
        resp = self.session.get(url, headers=headers, timeout=15)
        status = resp.status_code
        if status in (429, 503):  # rate-limited or service unavailable
          backoff = min(60, (2 ** attempt) + random.uniform(1, 6))
          logging.warning(f"Got {status} for {url} (attempt {attempt}/{self.max_retries}), backing off {backoff:.1f}s")
          time.sleep(backoff)
          # rotate user-agent for the next try
          headers["User-Agent"] = random.choice(USER_AGENTS)
          continue
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
      except requests.RequestException as e:
        last_exc = e
        backoff = min(60, (2 ** attempt) + random.uniform(1, 6))
        logging.warning(f"Request failed ({e}), attempt {attempt}/{self.max_retries}, retrying in {backoff:.1f}s...")
        time.sleep(backoff)
        # rotate user-agent between attempts
        headers["User-Agent"] = random.choice(USER_AGENTS)

    # exhausted retries
    raise last_exc if last_exc else RuntimeError("Unknown request failure")

  def _extract_badge_for(self, text: str) -> Optional[str]:
    # Try to extract the "for <keyword>" part from badge text
    m = re.search(r"amazon's\s+choice(?:\s+for\s+(.+))?$", text, re.I)
    if m:
      tail = m.group(1)
      if tail:
        return tail.strip(" .\u2019\"'")
    return None

  def _has_choice_badge(self, item: Tag) -> Tuple[bool, Optional[str]]:
    # search for badge-like text in several common places
    candidates = item.select("span.a-badge-text, span.a-size-small, span.a-badge-text, div.a-badge, span")
    for tag in candidates:
      raw = tag.get_text(" ", strip=True)
      if not raw:
        continue
      norm = re.sub(r"\s+", " ", raw).strip().lower()
      if BADGE_PREFIX in norm and "choice" in norm:
        return True, self._extract_badge_for(raw)
    # sometimes badge is represented differently; check aria-labels
    aria = item.get("aria-label", "")
    if aria and BADGE_PREFIX in aria.lower():
      return True, self._extract_badge_for(aria)
    return False, None

  def parse_products(self, soup: BeautifulSoup, keyword: str) -> List[ChoiceProduct]:
    products: List[ChoiceProduct] = []
    # common selectors for search results
    containers = soup.select("div[data-asin], div.s-result-item")
    for item in containers:
      asin = (item.attrs.get("data-asin") or "").strip()
      if not asin:
        continue
      has_badge, badge_for = self._has_choice_badge(item)
      if not has_badge:
        continue
      title_tag = item.select_one("h2 a span") or item.select_one("h2 span.a-size-medium")
      price_tag = item.select_one("span.a-price span.a-offscreen")
      link_tag = item.select_one("h2 a") or item.select_one("a.a-link-normal")
      href = link_tag.get("href") if link_tag else None
      url = (AMAZON_BASE + href) if href and href.startswith("/") else href
      products.append(
        ChoiceProduct(
          keyword=keyword,
          asin=asin,
          title=title_tag.get_text(strip=True) if title_tag else None,
          price=price_tag.get_text(strip=True) if price_tag else None,
          url=url,
          badge_for=badge_for,
        )
      )
    return products

  def scrape_keyword(self, keyword: str) -> List[ChoiceProduct]:
    url = self.build_search_url(keyword)
    soup = self._request(url)
    # polite pause after fetching to avoid being rate-limited
    time.sleep(random.uniform(8, 18))
    return self.parse_products(soup, keyword)

  def scrape(self, keywords: Iterable[str]) -> List[ChoiceProduct]:
    all_items: List[ChoiceProduct] = []
    for kw in keywords:
      logging.info(f"Scraping: {kw}")
      try:
        items = self.scrape_keyword(kw)
        logging.info(f"Found {len(items)} items for '{kw}'")
        all_items.extend(items)
      except Exception as e:
        logging.warning(f"Error for '{kw}': {e}")
      # long randomized sleep between keywords to reduce 503/429 chance
      time.sleep(random.uniform(self.min_delay, self.max_delay))
    return all_items

  def to_csv(self, products: List[ChoiceProduct], path: str):
    df = pd.DataFrame([asdict(p) for p in products])
    df.to_csv(path, index=False)
    return path


def main():
  keywords = [
    "wireless earbuds",
    "office chair",
    "gaming laptop",
    "blender",
    "running shoes",
    "coffee maker",
  ]
  scraper = AmazonChoiceScraper(min_delay=20, max_delay=40, max_retries=6)
  products = scraper.scrape(keywords)
  out = scraper.to_csv(products, "amazons_choice.csv")
  logging.info(f"Saved: {out}")


if __name__ == "__main__":
  main()
