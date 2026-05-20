#!/usr/bin/env python3
"""Web search + fetch tool using DuckDuckGo (no API key required).

Usage:
    python3 search.py "search keywords"          # search mode
    python3 search.py --fetch "https://..."       # fetch page content
"""

import json
import re
import sys
import os

import requests

MAX_FETCH_CHARS = 2000   # hard cap for token budget
FETCH_PREVIEW = 1500     # chars shown before truncation marker

# ============================================================
# Search
# ============================================================

def search_ddg(query: str, max_results: int = 8) -> str:
    results = []

    # Phase 1: Instant Answer API
    try:
        resp = requests.get("https://api.duckduckgo.com/", params={
            "q": query, "format": "json", "no_html": 1, "skip_disambig": 1,
        }, timeout=10, headers={"User-Agent": "Safe-CLI-Agent/1.0"})

        if resp.status_code == 200:
            data = resp.json()
            abstract = data.get("Abstract", "").strip()
            if abstract:
                results.append(f"[Answer] {abstract}")
                src = data.get("AbstractURL", "")
                if src:
                    results.append(f"Source: {src}")
            definition = data.get("Definition", "").strip()
            if definition:
                results.append(f"[Definition] {definition}")
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append(
                        f"- {topic['Text']}\n  {topic.get('FirstURL', '')}"
                    )

        if results:
            return _fmt("Search", query, results)

    except Exception as e:
        results.append(f"[DDG API error: {e}]")

    # Phase 2: HTML fallback (DuckDuckGo Lite)
    try:
        resp = requests.post("https://lite.duckduckgo.com/lite/",
                             data={"q": query},
                             timeout=10,
                             headers={"User-Agent": "Safe-CLI-Agent/1.0"})
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a", class_="result-link")
            snippets = soup.find_all("td", class_="result-snippet")
            for i, (link, snip) in enumerate(zip(links, snippets)):
                if i >= max_results:
                    break
                title = link.get_text(strip=True)
                url = link.get("href", "")
                desc = snip.get_text(strip=True)
                results.append(f"- {title}\n  {url}\n  {desc}")
            if results:
                return _fmt("Search", query, results)
    except Exception as e:
        results.append(f"[Lite fallback error: {e}]")

    if not results:
        return f"No results for: {query}"
    return _fmt("Search", query, results)


# ============================================================
# Fetch (URL → clean text)
# ============================================================

def fetch_url(url: str) -> str:
    """Fetch a web page, extract main content, return clean text."""
    try:
        resp = requests.get(url, timeout=12,
                            headers={"User-Agent": "Safe-CLI-Agent/1.0"})
        if resp.status_code != 200:
            return f"HTTP {resp.status_code} — cannot fetch {url}"

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip noise
        for tag in soup(["script", "style", "nav", "footer",
                         "header", "aside", "noscript", "iframe",
                         "form", "button", "input"]):
            tag.decompose()

        # Find main content container
        body = (soup.find("article")
                or soup.find("main")
                or soup.find(role="main")
                or soup.find(class_=re.compile(r"content|article|post|body", re.I))
                or soup.body)

        if not body:
            return "No readable content found."

        text = body.get_text(separator="\n", strip=True)

        # Collapse whitespace
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        text = "\n".join(lines)

        # Hard cap
        if len(text) > MAX_FETCH_CHARS:
            skipped = len(text) - MAX_FETCH_CHARS
            text = text[:FETCH_PREVIEW] + \
                   f"\n\n[... {skipped} more chars — use --fetch again for section ...]\n\n" + \
                   text[-300:]

        return _fmt("Fetch", url, [text])

    except Exception as e:
        return f"Fetch error: {e}"


# ============================================================
# Helpers
# ============================================================

def _fmt(label: str, query: str, results: list) -> str:
    header = f"{label}: {query}\n{'=' * 50}"
    return header + "\n" + "\n\n".join(results)


# ============================================================
# CLI
# ============================================================

def main():
    args = sys.argv[1:]

    # Mode: --fetch
    if args and args[0] == "--fetch":
        if len(args) < 2:
            print("Usage: search.py --fetch <url>")
            sys.exit(1)
        print(fetch_url(args[1]))
        return

    # Mode: search (default)
    query = ""

    # --json-data fallback (ExecContainerPlugin without command param)
    if len(args) >= 2 and args[0] == "--json-data":
        try:
            data = json.loads(" ".join(args[1:]))
            query = data.get("command", data.get("query", ""))
        except (json.JSONDecodeError, KeyError):
            pass

    if not query:
        query = " ".join(args)
    if not query and not os.isatty(0):
        query = sys.stdin.read().strip()
    if not query:
        print("Usage: search.py <keywords>  or  search.py --fetch <url>")
        sys.exit(1)

    print(search_ddg(query))


if __name__ == "__main__":
    main()
