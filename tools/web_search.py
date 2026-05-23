import time
import random
from typing import Optional
from langchain_core.tools import tool

# Playwright is an optional heavy dependency; we gracefully fall back to
# a requests-based approach so the project runs even without a browser.
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

try:
    import requests
    from bs4 import BeautifulSoup
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def _search_playwright(query: str, max_results: int = 5) -> str:
    """Use a headless Chromium browser to query DuckDuckGo."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=random.choice(_USER_AGENTS),
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        # Random human-like delay
        time.sleep(random.uniform(0.5, 1.5))

        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15_000)

        try:
            page.wait_for_selector(".result__body", timeout=8_000)
        except PWTimeout:
            pass  # page may have loaded with different selectors

        results = page.query_selector_all(".result__body")[:max_results]
        snippets = []
        for i, r in enumerate(results, 1):
            title_el = r.query_selector(".result__title")
            snippet_el = r.query_selector(".result__snippet")
            url_el = r.query_selector(".result__url")
            title = title_el.inner_text().strip() if title_el else "—"
            snippet = snippet_el.inner_text().strip() if snippet_el else ""
            link = url_el.inner_text().strip() if url_el else ""
            snippets.append(f"[{i}] {title}\n{link}\n{snippet}")

        browser.close()
        return "\n\n".join(snippets) if snippets else "No results found."


def _search_requests(query: str, max_results: int = 5) -> str:
    """Fallback: plain HTTP request to DuckDuckGo HTML endpoint."""
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
    }
    url = "https://html.duckduckgo.com/html/"
    resp = requests.post(
        url,
        data={"q": query},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = soup.select(".result__body")[:max_results]
    snippets = []
    for i, r in enumerate(results, 1):
        title = r.select_one(".result__title")
        snippet = r.select_one(".result__snippet")
        link = r.select_one(".result__url")
        snippets.append(
            f"[{i}] {title.get_text(strip=True) if title else '—'}\n"
            f"{link.get_text(strip=True) if link else ''}\n"
            f"{snippet.get_text(strip=True) if snippet else ''}"
        )
    return "\n\n".join(snippets) if snippets else "No results found."


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return text snippets.

    Args:
        query: The search query string.
        max_results: Number of result snippets to return (default 5).

    Returns:
        Numbered list of result snippets with title, URL, and description.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, 4):  # up to 3 retries
        try:
            if _PLAYWRIGHT_AVAILABLE:
                return _search_playwright(query, max_results)
            elif _REQUESTS_AVAILABLE:
                return _search_requests(query, max_results)
            else:
                return (
                    "ERROR: Neither playwright nor requests+beautifulsoup4 is installed. "
                    "Run: pip install playwright beautifulsoup4 requests && "
                    "playwright install chromium"
                )
        except Exception as exc:
            last_exc = exc
            wait = 2 ** attempt + random.uniform(0, 1)
            time.sleep(wait)

    return f"Search failed after 3 attempts. Last error: {last_exc}"
