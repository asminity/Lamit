from langchain_core.tools import tool
from langchain_community.utilities import ArxivAPIWrapper


arxiv = ArxivAPIWrapper(
    top_k_results=3,
    doc_content_chars_max=5000,
    load_all_available_meta=True,
    continue_on_failure=True
)


@tool
def arxiv_search(query: str) -> str:
    """
    Search arXiv for scientific research papers.

    Use this tool when the user asks for:
    - research papers
    - machine learning papers
    - deep learning papers
    - NLP papers
    - LLM papers
    - AI research
    - computer science papers
    - a specific arXiv paper or arXiv ID
    """

    query = query.strip()

    if not query:
        return "Please provide a research topic, paper title, author, or arXiv ID."

    try:
        result = arxiv.run(query)

        if not result:
            return (
                f"No arXiv papers were found for '{query}'. "
                "Try using different or more specific keywords."
            )

        if "No good Arxiv Result was found" in result:
            return (
                f"No arXiv papers were found for '{query}'. "
                "Try using different or more specific keywords."
            )

        if result.startswith("Arxiv exception:"):
            return (
                "The arXiv search service returned an error. "
                "Please try again later."
            )

        return result

    except Exception:
        return (
            "arXiv search is temporarily unavailable. "
            "Please try again later."
        )