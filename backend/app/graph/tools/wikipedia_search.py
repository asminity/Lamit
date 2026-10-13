from langchain_core.tools import tool
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

api_wrapper = WikipediaAPIWrapper(
    top_k_results=2,
    doc_content_chars_max=1500
)

wiki_search = WikipediaQueryRun(api_wrapper=api_wrapper)


@tool
def wikipedia_search(query: str) -> str:
    """
    Search Wikipedia for encyclopedic facts, historical events, biographies,
    scientific concepts, definitions, and high-level summaries.
    """
    try:
        return wiki_search.invoke(query)
    except Exception as e:
        return f"Wikipedia search failed for '{query}': {str(e)}"
