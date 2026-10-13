from .get_lat_long import get_lat_long
from .get_weather import get_weather
from .duckduckgo_search import duckduckgo_search
from .wikipedia_search import wikipedia_search
from .arxiv_search import arxiv_search
from .google_scholar import google_scholar_search
from .google_search import google_search
from .youtube_tool import youtube_tool
from .stock_price import get_stock_price
from .amazon_tool import amazon_tool
from .gmail_tool import read_gmail_messages, send_gmail_message


tools = [
    get_lat_long,
    get_weather,
    duckduckgo_search,  
    wikipedia_search,
    arxiv_search,
    google_scholar_search,
    google_search,
    get_stock_price,
    youtube_tool,
    amazon_tool,
    read_gmail_messages,
    send_gmail_message,
]