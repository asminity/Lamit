import os
from dotenv import load_dotenv, find_dotenv
from langchain_core.tools import tool
from langchain_community.utilities import SerpAPIWrapper

load_dotenv(find_dotenv())

search = SerpAPIWrapper(
    serpapi_api_key=os.getenv("SERPAPI_API_KEY")
)


@tool
def google_search(query: str) -> str:
    """
    Search Google using SerpAPI for real-time web results, current information,
    recent news, facts, and live web data.
    """
    query = query.strip()
    if not query:
        return "Please provide a valid search query."

    try:
        result = search.run(query)
        if not result:
            return f"No Google search results were found for '{query}'."
        return result
    except Exception as e:
        return f"Google search is temporarily unavailable: {str(e)}"
