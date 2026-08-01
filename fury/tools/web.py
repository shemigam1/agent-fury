"""Web tools for `assistant` mode. Stdlib-only (no API keys required).

`web_search` uses DuckDuckGo's HTML endpoint; `web_fetch` retrieves a URL and
strips it to readable text. These reach the network only when the assistant mode
tool set is active and the model chooses to call them.
"""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request

from fury.tools.base import Tool, ToolContext, ToolResult

_UA = "Mozilla/5.0 (compatible; agent-fury/0.2; +https://github.com/)"
_FETCH_LIMIT = 15_000


def _get(url: str, data: bytes | None = None) -> str:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (user-invoked)
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _web_search(ctx: ToolContext, args: dict) -> ToolResult:
    query = args["query"]
    max_results = int(args.get("max_results", 5))
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    body = _get(url)
    results = []
    for m in re.finditer(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S
    ):
        href, title = m.group(1), _strip_html(m.group(2))
        # DDG wraps hrefs in a redirect; pull out the real target when present.
        parsed = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(parsed.query)
        real = qs.get("uddg", [href])[0]
        results.append(f"{len(results)+1}. {title}\n   {real}")
        if len(results) >= max_results:
            break
    if not results:
        return ToolResult(f'No results for "{query}".')
    return ToolResult("\n".join(results))


def _web_fetch(ctx: ToolContext, args: dict) -> ToolResult:
    url = args["url"]
    if not url.startswith(("http://", "https://")):
        return ToolResult("Error: url must start with http:// or https://", is_error=True)
    text = _strip_html(_get(url))
    if len(text) > _FETCH_LIMIT:
        text = text[:_FETCH_LIMIT] + "\n[...truncated]"
    return ToolResult(text)


web_search_tool = Tool(
    name="web_search",
    description="Search the web and return the top result titles and URLs.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "max_results": {"type": "integer", "description": "Max results (default 5)."},
        },
        "required": ["query"],
    },
    handler=_web_search,
)

web_fetch_tool = Tool(
    name="web_fetch",
    description="Fetch a web page and return its readable text content.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Absolute http(s) URL to fetch."},
        },
        "required": ["url"],
    },
    handler=_web_fetch,
)
