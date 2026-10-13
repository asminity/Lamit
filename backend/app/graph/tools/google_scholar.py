import os

from dotenv import load_dotenv, find_dotenv
from langchain_core.tools import tool
from langchain_community.utilities import GoogleScholarAPIWrapper


load_dotenv(find_dotenv())


scholar = GoogleScholarAPIWrapper(
    serp_api_key=os.getenv("SERPAPI_API_KEY")
)


@tool
def google_scholar_search(query: str) -> str:
    """
    Search Google Scholar for academic papers, research articles,
    authors, citations, and scholarly literature.
    """

    query = query.strip()

    if not query:
        return "Please provide a research topic or paper query."

    try:
        result = scholar.run(query)

        if not result:
            return (
                f"No Google Scholar results were found for '{query}'."
            )

        return result

    except Exception:
        return (
            "Google Scholar search is temporarily unavailable. "
            "Please try again later or use arXiv."
        )