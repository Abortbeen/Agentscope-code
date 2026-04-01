# -*- coding: utf-8 -*-
"""Web tools - WebSearch and WebFetch.

Implements R9 from the plan.
"""
import asyncio

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


async def web_fetch(
    url: str,
    prompt: str | None = None,
    timeout: int = 30,
) -> ToolResponse:
    """Fetch a web page and return its content as markdown.

    Args:
        url: The URL to fetch.
        prompt: Optional prompt to extract specific info from the page.
        timeout: Request timeout in seconds.

    Returns:
        ToolResponse with the page content.
    """
    try:
        import httpx
    except ImportError:
        return ToolResponse(
            content=[TextBlock(text="Error: httpx not installed. Run: pip install httpx")],
        )

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            resp = await client.get(url, headers={
                "User-Agent": "CodeAgent/0.1 (https://github.com/codeagent)",
            })
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            if "text/html" in content_type:
                # Try html2text conversion
                try:
                    import html2text
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    h.ignore_images = True
                    h.body_width = 0
                    text = h.handle(resp.text)
                except ImportError:
                    # Fallback: strip tags roughly
                    import re
                    text = re.sub(r"<[^>]+>", "", resp.text)
                    text = re.sub(r"\s+", " ", text).strip()
            else:
                text = resp.text

            # Truncate
            max_len = 50000
            if len(text) > max_len:
                text = text[:max_len] + "\n\n... (truncated)"

            if prompt:
                text = f"User's question: {prompt}\n\n---\n\n{text}"

            return ToolResponse(
                content=[TextBlock(text=text)],
                metadata={"url": url, "status": resp.status_code},
            )

    except Exception as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error fetching URL {url}: {e}")],
        )


async def web_search(
    query: str,
    max_results: int = 5,
) -> ToolResponse:
    """Search the web and return results.

    Uses DuckDuckGo as default (no API key needed).

    Args:
        query: Search query string.
        max_results: Maximum number of results. Default 5.

    Returns:
        ToolResponse with search results.
    """
    # Try duckduckgo-search
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    f"**{r.get('title', 'No title')}**\n"
                    f"{r.get('href', '')}\n"
                    f"{r.get('body', '')}\n"
                )

        if results:
            return ToolResponse(
                content=[TextBlock(text="\n---\n".join(results))],
                metadata={"count": len(results)},
            )
        return ToolResponse(
            content=[TextBlock(text=f"No results found for: {query}")],
        )

    except ImportError:
        return ToolResponse(
            content=[TextBlock(
                text="Web search unavailable. Install: pip install duckduckgo-search\n"
                "Or use WebFetch with a direct URL instead.",
            )],
        )
    except Exception as e:
        return ToolResponse(
            content=[TextBlock(text=f"Search error: {e}")],
        )
