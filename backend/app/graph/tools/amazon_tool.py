import os
import re
import requests
from dotenv import load_dotenv, find_dotenv
from langchain_core.tools import tool

load_dotenv(find_dotenv())

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")


def _extract_asin_and_domain(text: str) -> tuple[str, str | None]:
    """Extract ASIN and Amazon regional domain from URL or raw ASIN string."""
    text = text.strip()
    domain_match = re.search(r"amazon\.(com|co\.uk|in|de|ca|fr|co\.jp|es|it|com\.au)", text, re.IGNORECASE)
    domain = f"amazon.{domain_match.group(1)}" if domain_match else None

    asin_match = re.search(r"(?:/dp/|/gp/product/|/d/)([A-Z0-9]{10})", text, re.IGNORECASE)
    if asin_match:
        return asin_match.group(1).upper(), domain

    raw_asin = re.search(r"^[A-Z0-9]{10}$", text, re.IGNORECASE)
    if raw_asin:
        return raw_asin.group(0).upper(), domain

    return "", domain


def _format_search_results(query: str, data: dict, domain: str) -> str:
    """Format Amazon search results."""
    organic = data.get("organic_results", [])
    if not organic:
        return f"No Amazon products found for search query '{query}' on {domain}."

    lines = [f"## Amazon Search Results for '{query}' ({domain})\n"]

    for idx, item in enumerate(organic[:6], 1):
        title = item.get("title", "Untitled Product")
        link = item.get("link", "")
        asin = item.get("asin", "N/A")
        price = item.get("price", "Price not listed")
        rating = item.get("rating")
        reviews = item.get("reviews")
        is_prime = item.get("is_prime", False)

        meta_parts = [f"Price: **{price}**", f"ASIN: `{asin}`"]
        if rating:
            reviews_str = f" from {reviews:,} reviews" if reviews else ""
            meta_parts.append(f"Rating: {rating}/5{reviews_str}")
        if is_prime:
            meta_parts.append("Prime eligible")

        details_str = " | ".join(meta_parts)
        lines.append(f"{idx}. **[{title}]({link})**\n   - {details_str}")

        badge = item.get("badge")
        if badge:
            lines.append(f"   - Badge: *{badge}*")

    return "\n".join(lines)


def _format_product_details(data: dict, asin: str, domain: str) -> str:
    """Format detailed Amazon product information."""
    product = data.get("product_results", {})
    if not product:
        return f"Could not retrieve Amazon product details for ASIN '{asin}'."

    title = product.get("title", "Untitled Product")
    link = product.get("link") or f"https://www.{domain}/dp/{asin}"
    price = product.get("price", "Price not listed")
    rating = product.get("rating")
    reviews = product.get("reviews")
    brand = product.get("brand")

    lines = [
        f"## Amazon Product: [{title}]({link})",
        f"- **ASIN**: `{asin}`",
        f"- **Price**: {price}",
    ]

    if brand:
        lines.append(f"- **Brand**: {brand}")

    if rating:
        reviews_str = f" based on {reviews:,} reviews" if reviews else ""
        lines.append(f"- **Rating**: {rating}/5 stars{reviews_str}")

    options = data.get("purchase_options")
    if isinstance(options, dict):
        opt_lines = []
        for key, opt in list(options.items())[:3]:
            if isinstance(opt, dict):
                caption = opt.get("caption") or key.replace("_", " ").title()
                price_val = opt.get("price", "")
                stock = opt.get("stock", "")
                part = f"{caption}: {price_val}" if price_val else caption
                if stock:
                    part += f" ({stock})"
                opt_lines.append(part)
        if opt_lines:
            lines.append(f"- **Purchase Options**: {', '.join(opt_lines)}")
    elif isinstance(options, list) and options:
        opt_lines = []
        for opt in options[:3]:
            if isinstance(opt, dict):
                opt_title = opt.get("title") or opt.get("condition", "")
                opt_price = opt.get("price", "")
                if opt_price:
                    opt_lines.append(f"{opt_title}: {opt_price}")
        if opt_lines:
            lines.append(f"- **Purchase Options**: {', '.join(opt_lines)}")

    about = data.get("about_item", [])
    if about and isinstance(about, list):
        lines.append("\n### Key Features:")
        for bullet in about[:5]:
            lines.append(f"- {bullet}")

    specs = data.get("item_specifications", {})
    if specs and isinstance(specs, dict):
        lines.append("\n### Specifications:")
        for k, v in list(specs.items())[:6]:
            spec_name = k.replace("_", " ").title()
            lines.append(f"- **{spec_name}**: {v}")

    return "\n".join(lines)


@tool
def amazon_tool(query: str, action: str = "auto", amazon_domain: str = "amazon.com") -> str:
    """
    All-in-one Amazon tool using SerpAPI for Amazon Search and Amazon Product details.

    Parameters:
    - query (str): The product search query (e.g., 'wireless mechanical keyboard')
                   OR an Amazon product ASIN (e.g., 'B07CMS5Q6P')
                   OR an Amazon product URL (e.g., 'https://www.amazon.com/dp/B07CMS5Q6P').
    - action (str, optional): The action to execute:
      - 'auto' (default): Automatically detects whether to fetch product details (if query is an ASIN or product URL) or perform a product search.
      - 'search': Searches Amazon products by keywords and returns prices, ratings, and ASINs.
      - 'product': Fetches detailed product specifications, bullet points, price, and reviews by ASIN or product URL.
    - amazon_domain (str, optional): The Amazon regional domain (default: 'amazon.com'). Examples: 'amazon.com', 'amazon.in', 'amazon.co.uk', 'amazon.de', 'amazon.ca'.
    """
    api_key = os.getenv("SERPAPI_API_KEY") or SERPAPI_API_KEY
    if not api_key:
        return "SERPAPI_API_KEY is not configured in the environment."

    clean_query = query.strip()
    if not clean_query:
        return "Please provide a valid product search query, ASIN, or Amazon product URL."

    extracted_asin, detected_domain = _extract_asin_and_domain(clean_query)
    target_domain = detected_domain or amazon_domain.strip().lower()

    act = action.strip().lower()
    if act == "auto":
        act = "product" if extracted_asin else "search"

    url = "https://serpapi.com/search"

    try:
        if act == "product":
            asin = extracted_asin or clean_query
            params = {
                "engine": "amazon_product",
                "asin": asin,
                "amazon_domain": target_domain,
                "api_key": api_key,
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                return f"Amazon Product error for ASIN '{asin}': {data['error']}"
            return _format_product_details(data, asin, target_domain)

        else:  # 'search'
            params = {
                "engine": "amazon",
                "k": clean_query,
                "amazon_domain": target_domain,
                "api_key": api_key,
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                return f"Amazon Search error for '{clean_query}': {data['error']}"
            return _format_search_results(clean_query, data, target_domain)

    except requests.RequestException as e:
        return f"Failed to connect to Amazon API: {str(e)}"
    except Exception as e:
        return f"An unexpected error occurred while fetching Amazon data: {str(e)}"
