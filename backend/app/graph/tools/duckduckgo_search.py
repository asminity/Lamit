import sys
try:
    import duckduckgo_search as _ddgs
    if "ddgs" not in sys.modules:
        sys.modules["ddgs"] = _ddgs
except Exception:
    pass

from langchain_core.tools import tool
try:
    from langchain_community.tools import DuckDuckGoSearchRun
    search = DuckDuckGoSearchRun()
except Exception:
    search = None


@tool
def duckduckgo_search(query: str) -> str:
    """
    Search the web using DuckDuckGo.

    Use this tool when the user asks for:
    - current information
    - recent news
    - facts that may have changed
    - information that requires web search
    """
    try:
        return search.invoke(query)
    except Exception as e:
        return f"DuckDuckGo search failed for query '{query}': {str(e)}"
