"""
C.O.R.A Web Tools Module
Version: 1.0.0
Unity AI Lab

Web search, URL fetching, and content summarization.
"""

import requests
import re
import time
from typing import Optional, Dict, List, Any
from urllib.parse import quote_plus, urlparse
from html.parser import HTMLParser


# Simple rate limiting to prevent API abuse
class RateLimiter:
    """Simple token bucket rate limiter for web requests."""

    def __init__(self, requests_per_second: float = 2.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self._last_request_time = 0.0

    def wait(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.time()


# Global rate limiter (2 requests per second default)
_rate_limiter = RateLimiter(requests_per_second=2.0)


class HTMLTextExtractor(HTMLParser):
    """Extract text content from HTML."""

    def __init__(self):
        super().__init__()
        self.result = []
        self.skip_tags = {'script', 'style', 'head', 'meta', 'link'}
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag

    def handle_endtag(self, tag):
        self.current_tag = None

    def handle_data(self, data):
        if self.current_tag not in self.skip_tags:
            text = data.strip()
            if text:
                self.result.append(text)

    def get_text(self) -> str:
        return ' '.join(self.result)


def extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML content."""
    parser = HTMLTextExtractor()
    try:
        parser.feed(html)
        return parser.get_text()
    except Exception:
        # Fallback: strip tags with regex
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()


def instant_answer(query: str) -> Dict[str, Any]:
    """
    Get instant answer from DuckDuckGo API.

    This uses DDG's instant answer API which returns direct answers,
    summaries, and related topics - much faster than HTML scraping.

    Args:
        query: Search query string

    Returns:
        Dict with 'success', 'answer', 'abstract', 'related', etc.
    """
    if not query or not query.strip():
        return {'success': False, 'error': 'Empty query'}

    try:
        # Apply rate limiting
        _rate_limiter.wait()

        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"
        headers = {'User-Agent': 'CORA/1.0.0'}

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        result = {
            'success': True,
            'query': query,
            'answer': data.get('Answer', ''),
            'abstract': data.get('AbstractText', ''),
            'abstract_source': data.get('AbstractSource', ''),
            'abstract_url': data.get('AbstractURL', ''),
            'definition': data.get('Definition', ''),
            'definition_source': data.get('DefinitionSource', ''),
            'related': []
        }

        # Extract related topics
        for topic in data.get('RelatedTopics', [])[:5]:
            if isinstance(topic, dict) and topic.get('Text'):
                result['related'].append({
                    'text': topic['Text'][:200],
                    'url': topic.get('FirstURL', '')
                })

        # Check if we got any useful info
        has_content = any([
            result['answer'],
            result['abstract'],
            result['definition'],
            result['related']
        ])

        if not has_content:
            result['message'] = 'No instant answer available. Try web_search() for more results.'

        return result

    except requests.Timeout:
        return {'success': False, 'error': 'Request timed out'}
    except requests.RequestException as e:
        return {'success': False, 'error': f'Request failed: {e}'}
    except Exception as e:
        return {'success': False, 'error': f'Error: {e}'}


_BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}


def _strip_tags(html: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html or '')).strip()


def _search_bing(query: str, num_results: int) -> List[Dict[str, str]]:
    """Bing's HTML results page (no key). Used when DuckDuckGo answers with a
    challenge page (HTTP 202, no results) as it did on 2026-10-14."""
    url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=en&count={max(5, num_results)}"
    r = requests.get(url, headers=_BROWSER_HEADERS, timeout=10)
    r.raise_for_status()
    out: List[Dict[str, str]] = []
    for block in re.split(r'<li class="b_algo"', r.text)[1:]:
        m = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        snippet = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
        out.append({'title': _strip_tags(m.group(2)), 'url': m.group(1),
                    'snippet': _strip_tags(snippet.group(1)) if snippet else ''})
        if len(out) >= num_results:
            break
    return out


def _relevant(results: List[Dict[str, str]], query: str) -> List[Dict[str, str]]:
    """Drop a result set that ignores the query (Bing answers non-browser
    clients with results for the first word only: 'Kansas' for a Chiefs
    question). Keep it when any result mentions a query word of 4+ letters
    other than the first word."""
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) >= 4]
    if len(words) < 2:
        return results
    rest = words[1:]
    for r in results:
        hay = f"{r.get('title', '')} {r.get('snippet', '')}".lower()
        if any(w in hay for w in rest):
            return results
    return []


_BROWSER_ENGINES = (
    # name, url template, result container, title, snippet
    ('duckduckgo', 'https://duckduckgo.com/?q={q}&ia=web&kl=us-en',
     'li[data-layout="organic"], [data-testid="result"], article', 'h2', '[data-result="snippet"], .result__snippet'),
    ('brave', 'https://search.brave.com/search?q={q}&source=web',
     '#results [data-type="web"], #results .snippet', '.title, .snippet-title', '.snippet-description, .snippet-content, .desc'),
    ('bing', 'https://www.bing.com/search?q={q}&setlang=en', 'li.b_algo', 'h2 a', '.b_caption p, p'),
)


def _search_playwright(query: str, num_results: int, timeout_ms: int = 20000) -> List[Dict[str, str]]:
    """Real results pages in the full Chromium build, headless (Playwright
    channel='chromium'). The plain HTML endpoints answer bots with a challenge
    page, Bing degrades to a first-word result over HTTP and the headless-shell
    build is detected; the full build is not. One launch, engines in turn:
    DuckDuckGo, Brave, Bing. ~3-6 s."""
    from playwright.sync_api import sync_playwright
    out: List[Dict[str, str]] = []
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True, channel='chromium')
        except Exception:
            browser = pw.chromium.launch(headless=True)      # headless shell: last resort
        try:
            ctx = browser.new_context(user_agent=_BROWSER_HEADERS['User-Agent'], locale='en-US',
                                      viewport={'width': 1280, 'height': 900})
            for name, tmpl, container, title_sel, snip_sel in _BROWSER_ENGINES:
                page = ctx.new_page()
                try:
                    page.goto(tmpl.format(q=quote_plus(query)), timeout=timeout_ms, wait_until='domcontentloaded')
                    try:
                        page.wait_for_selector(container, timeout=8000)
                    except Exception:
                        pass
                    page.wait_for_timeout(1200)
                    answer = ''
                    try:
                        answer = page.evaluate("""() => {
                            const sels = ['#results .infobox', '[data-type="infobox"]', '.answer', '[data-testid="module"]',
                                          '#b_context', '.b_ans', '[data-area="mainline"] .module'];
                            for (const sel of sels) { const n = document.querySelector(sel); if (n && n.innerText.trim().length > 40) return n.innerText.trim().slice(0, 900); }
                            return '';
                        }""") or ''
                    except Exception:
                        answer = ''
                    rows = page.evaluate("""([container, titleSel, snipSel]) => {
                        const text = (el, sel) => { const n = el.querySelector(sel); return n ? n.innerText.trim() : ''; };
                        const link = (el, sel) => { const t = el.querySelector(sel); const a = (t && t.tagName === 'A') ? t : (t ? t.closest('a') || t.querySelector('a') : el.querySelector('a[href^="http"]')); return a ? a.href : ''; };
                        return Array.from(document.querySelectorAll(container)).map(el => ({
                            title: text(el, titleSel), url: link(el, titleSel), snippet: text(el, snipSel)
                        })).filter(r => r.title && r.url && !r.url.includes('duckduckgo.com/y.js'));
                    }""", [container, title_sel, snip_sel])
                    seen = set()   # real engines in a real browser: no relevance guard (it only guards Bing-over-HTTP)
                    for r in rows:
                        if r.get('url') in seen:
                            continue
                        seen.add(r.get('url'))
                        out.append({'title': r.get('title', ''), 'url': r.get('url', ''),
                                    'snippet': r.get('snippet', ''), 'engine': name})
                        if len(out) >= num_results:
                            break
                    if out:
                        if answer:
                            out[0]['answer_box'] = re.sub(r'\s+', ' ', answer)
                        break
                except Exception as e:
                    print(f"[web] {name} in browser: {str(e)[:100]}")
                finally:
                    page.close()
        finally:
            browser.close()
    return out


def web_search(query: str, num_results: int = 5, show_window: bool = False) -> Dict[str, Any]:
    """
    Search the web using DuckDuckGo HTML API.

    Args:
        query: Search query string
        num_results: Maximum number of results to return
        show_window: also open the results in a modal window (off: she reads
            the results back; a window that just sat there was confusing)

    Returns:
        Dict with 'success', 'results' list, and optional 'error'
    """
    if not query or not query.strip():
        return {
            'success': False,
            'error': 'Empty search query',
            'results': []
        }

    try:
        # Apply rate limiting
        _rate_limiter.wait()

        # DuckDuckGo HTML search
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        html = response.text
        results = []

        # Parse DuckDuckGo results
        # Look for result links and snippets
        result_pattern = r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
        snippet_pattern = r'<a[^>]+class="result__snippet"[^>]*>([^<]+(?:<[^>]+>[^<]*</[^>]+>)*[^<]*)</a>'

        links = re.findall(result_pattern, html)
        snippets = re.findall(snippet_pattern, html)

        for i, (link, title) in enumerate(links[:num_results]):
            snippet = snippets[i] if i < len(snippets) else ''
            # Clean snippet of any remaining tags
            snippet = re.sub(r'<[^>]+>', '', snippet)

            results.append({
                'title': title.strip(),
                'url': link,
                'snippet': snippet.strip()
            })

        result = {
            'success': True,
            'query': query,
            'results': results,
            'count': len(results),
            'engine': 'duckduckgo'
        }

        if not results:
            # DuckDuckGo answered with a challenge page (or changed its markup): a real browser, then Bing
            for name, fn in (('browser', _search_playwright), ('bing', _search_bing)):
                try:
                    results = fn(query, num_results)
                    if name == 'bing':
                        results = _relevant(results, query)
                except Exception as e:
                    result[f'{name}_error'] = str(e)[:160]
                    results = []
                if results:
                    result.update(results=results, count=len(results), engine=name)
                    break
        if not results:
            result['success'] = False
            result['error'] = 'no results from any search path (blocked or markup changed)'

        # Show results in modal window only when asked
        if show_window and results:
            try:
                from ui.modals import show_web_modal, show_modal_threadsafe
                content = f"Search: {query}\n\n"
                for i, r in enumerate(results, 1):
                    content += f"{i}. {r['title']}\n   {r['url']}\n   {r.get('snippet', '')}\n\n"
                show_modal_threadsafe(show_web_modal, content, "", f"Search: {query}")
            except Exception:
                pass

        return result

    except requests.Timeout:
        return {
            'success': False,
            'error': 'Search request timed out',
            'results': []
        }
    except requests.RequestException as e:
        return {
            'success': False,
            'error': f'Search request failed: {str(e)}',
            'results': []
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Search error: {str(e)}',
            'results': []
        }


def _fetch_in_browser(url: str, timeout_ms: int = 20000) -> str:
    """The page's visible text rendered in the full Chromium build: for sites
    that block plain requests (403/429) or build the page with scripts."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True, channel='chromium')
        except Exception:
            browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_context(user_agent=_BROWSER_HEADERS['User-Agent'], locale='en-US').new_page()
            page.goto(url, timeout=timeout_ms, wait_until='domcontentloaded')
            page.wait_for_timeout(1500)
            return page.evaluate("() => { for (const n of document.querySelectorAll('script,style,noscript,nav,footer,header')) n.remove(); return document.body ? document.body.innerText : ''; }") or ''
        finally:
            browser.close()


def fetch_url(url: str, timeout: int = 15, show_window: bool = False) -> Dict[str, Any]:
    """
    Fetch content from a URL. Returns the raw `content` and the readable `text`
    (what the model reads); falls back to a headless browser when the plain
    request is blocked or the page is script-built. The modal window is opt-in.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Dict with 'success', 'content', 'content_type', and optional 'error'
    """
    if not url or not url.strip():
        return {
            'success': False,
            'error': 'Empty URL',
            'content': None
        }

    # Validate URL
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = 'https://' + url
        elif parsed.scheme not in ('http', 'https'):
            return {
                'success': False,
                'error': f'Unsupported URL scheme: {parsed.scheme}',
                'content': None
            }
    except Exception:
        return {
            'success': False,
            'error': 'Invalid URL format',
            'content': None
        }

    try:
        # Apply rate limiting
        _rate_limiter.wait()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = None
        blocked = False
        try:
            response = requests.get(url, headers={**_BROWSER_HEADERS, **headers}, timeout=timeout)
            if response.status_code in (401, 403, 406, 429, 503):
                blocked = True
            else:
                response.raise_for_status()
        except requests.HTTPError:
            blocked = True
        content_type = response.headers.get('Content-Type', 'text/html') if response is not None else 'text/html'
        raw = response.text if (response is not None and not blocked) else ''
        text = extract_text_from_html(raw) if raw and 'html' in content_type.lower() else raw
        via = 'requests'

        # blocked, or a script-built page with almost no readable text: render it
        if blocked or ('html' in content_type.lower() and len(re.sub(r'\s+', ' ', text)) < 400 and len(raw) > 20000):
            try:
                rendered = _fetch_in_browser(url)
                if len(re.sub(r'\s+', ' ', rendered)) > len(re.sub(r'\s+', ' ', text)):
                    text, via = rendered, 'browser'
                    if not raw:
                        raw = rendered
            except Exception as e:
                if blocked and not text:
                    code = response.status_code if response is not None else '?'
                    return {'success': False, 'error': f'blocked (HTTP {code}) and browser fetch failed: {str(e)[:120]}', 'content': None}
        text = re.sub(r'\n{3,}', '\n\n', text).strip()

        result = {
            'success': True,
            'url': url,
            'content': raw,
            'text': text,
            'content_type': content_type,
            'status_code': response.status_code if response is not None else None,
            'length': len(raw),
            'via': via,
        }

        # Show content in modal window only when asked
        if show_window:
            try:
                from ui.modals import show_web_modal, show_modal_threadsafe
                text_content = text if len(text) <= 5000 else text[:5000] + "\n\n[Content truncated...]"
                show_modal_threadsafe(show_web_modal, text_content, url, f"Fetched: {urlparse(url).netloc}")
            except Exception:
                pass

        return result

    except requests.Timeout:
        return {
            'success': False,
            'error': f'Request timed out after {timeout}s',
            'content': None
        }
    except requests.HTTPError as e:
        return {
            'success': False,
            'error': f'HTTP error: {e.response.status_code}',
            'content': None
        }
    except requests.RequestException as e:
        return {
            'success': False,
            'error': f'Request failed: {str(e)}',
            'content': None
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Fetch error: {str(e)}',
            'content': None
        }


def summarize_url(url: str, max_length: int = 500) -> Dict[str, Any]:
    """
    Fetch a URL and summarize its text content.

    Args:
        url: The URL to fetch and summarize
        max_length: Maximum length of summary in characters

    Returns:
        Dict with 'success', 'summary', 'title', and optional 'error'
    """
    # Fetch the URL
    fetch_result = fetch_url(url)

    if not fetch_result['success']:
        return {
            'success': False,
            'error': fetch_result['error'],
            'summary': None
        }

    html = fetch_result['content']

    # Extract title
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else 'No title'

    # Extract main text
    text = extract_text_from_html(html)

    if not text:
        return {
            'success': True,
            'url': url,
            'title': title,
            'summary': 'No readable text content found.',
            'length': 0
        }

    # Create summary (first max_length chars, break at sentence)
    if len(text) <= max_length:
        summary = text
    else:
        summary = text[:max_length]
        # Try to break at sentence
        last_period = summary.rfind('.')
        last_question = summary.rfind('?')
        last_exclaim = summary.rfind('!')
        break_point = max(last_period, last_question, last_exclaim)

        if break_point > max_length // 2:
            summary = summary[:break_point + 1]
        else:
            summary = summary + '...'

    return {
        'success': True,
        'url': url,
        'title': title,
        'summary': summary,
        'full_length': len(text),
        'summary_length': len(summary)
    }


def search_and_summarize(query: str, num_results: int = 3) -> Dict[str, Any]:
    """
    Search the web and summarize top results.

    Args:
        query: Search query string
        num_results: Number of results to summarize

    Returns:
        Dict with 'success', 'results' list with summaries
    """
    search_result = web_search(query, num_results)

    if not search_result['success']:
        return search_result

    results_with_summaries = []

    for result in search_result['results']:
        url = result.get('url', '')
        if url:
            summary_result = summarize_url(url, max_length=300)
            result['summary'] = summary_result.get('summary', result.get('snippet', ''))
            result['full_content_available'] = summary_result.get('success', False)

        results_with_summaries.append(result)

    return {
        'success': True,
        'query': query,
        'results': results_with_summaries,
        'count': len(results_with_summaries)
    }


# Convenience functions for CLI integration
def search(query: str) -> str:
    """CLI-friendly search function."""
    result = web_search(query)

    if not result['success']:
        return f"Search failed: {result['error']}"

    if not result['results']:
        return f"No results found for: {query}"

    output = [f"Search results for: {query}\n"]

    for i, r in enumerate(result['results'], 1):
        output.append(f"{i}. {r['title']}")
        output.append(f"   {r['url']}")
        if r.get('snippet'):
            output.append(f"   {r['snippet'][:150]}...")
        output.append("")

    return '\n'.join(output)


def fetch(url: str) -> str:
    """CLI-friendly fetch function."""
    result = fetch_url(url)

    if not result['success']:
        return f"Fetch failed: {result['error']}"

    text = extract_text_from_html(result['content'])

    if len(text) > 2000:
        text = text[:2000] + '...\n[Content truncated]'

    return f"Content from {url}:\n\n{text}"


def summarize(url: str) -> str:
    """CLI-friendly summarize function."""
    result = summarize_url(url)

    if not result['success']:
        return f"Summarize failed: {result['error']}"

    return f"Title: {result['title']}\nURL: {url}\n\nSummary:\n{result['summary']}"


# Module test
if __name__ == '__main__':
    print("Testing web.py module...")

    # Test search
    print("\n--- Web Search Test ---")
    result = web_search("Python programming", num_results=3)
    print(f"Success: {result['success']}")
    print(f"Results: {result.get('count', 0)}")

    # Test fetch
    print("\n--- URL Fetch Test ---")
    result = fetch_url("https://example.com")
    print(f"Success: {result['success']}")
    print(f"Length: {result.get('length', 0)}")

    # Test summarize
    print("\n--- URL Summarize Test ---")
    result = summarize_url("https://example.com")
    print(f"Success: {result['success']}")
    print(f"Title: {result.get('title', 'N/A')}")

    print("\nAll tests completed.")
