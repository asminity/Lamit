import os
import re
import requests
from dotenv import load_dotenv, find_dotenv
from langchain_core.tools import tool

load_dotenv(find_dotenv())

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")


def _extract_video_id(text: str) -> str:
    """Extract YouTube video ID from URL or return raw ID if matched."""
    text = text.strip()
    patterns = [
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _extract_channel_id(text: str) -> str:
    """Extract channel handle, channel ID, or name from URL or text."""
    text = text.strip()
    match = re.search(r"youtube\.com\/(@[a-zA-Z0-9_.-]+)", text)
    if match:
        return match.group(1)
    match = re.search(r"youtube\.com\/channel\/([a-zA-Z0-9_-]+)", text)
    if match:
        return match.group(1)
    match = re.search(r"youtube\.com\/(?:c|user)\/([a-zA-Z0-9_.-]+)", text)
    if match:
        return match.group(1)
    return text


def _format_search_results(query: str, data: dict) -> str:
    """Format YouTube search results."""
    lines = [f"## YouTube Search Results for '{query}'\n"]

    # Channel result if any
    channel = data.get("channel_results")
    if isinstance(channel, list) and channel:
        ch = channel[0]
        title = ch.get("title", "")
        link = ch.get("link", "")
        subs = ch.get("subscribers", "")
        lines.append(f"### Channel: [{title}]({link}) ({subs})\n")
    elif isinstance(channel, dict):
        title = channel.get("title", "")
        link = channel.get("link", "")
        subs = channel.get("subscribers_text", "")
        lines.append(f"### Channel: [{title}]({link}) ({subs})\n")

    # Video results
    videos = data.get("video_results", [])
    if not videos:
        return f"No YouTube videos found for '{query}'."

    lines.append("### Videos:")
    for idx, video in enumerate(videos[:6], 1):
        title = video.get("title", "Untitled")
        link = video.get("link", "")
        ch_name = video.get("channel", {}).get("name", "Unknown Channel")
        ch_link = video.get("channel", {}).get("link", "")
        views = video.get("views", "N/A views")
        length = video.get("length", "N/A")
        published = video.get("published_date", "")

        pub_str = f" • {published}" if published else ""
        ch_str = f"[{ch_name}]({ch_link})" if ch_link else ch_name

        lines.append(
            f"{idx}. **[{title}]({link})**\n"
            f"   - Channel: {ch_str}\n"
            f"   - Duration: {length} • Views: {views}{pub_str}"
        )

        description = video.get("description", "")
        if description:
            snippet = description[:140] + ("..." if len(description) > 140 else "")
            lines.append(f"   - Description: {snippet}")

    return "\n".join(lines)


def _format_video_details(data: dict, video_id: str) -> str:
    """Format detailed YouTube video metadata."""
    title = data.get("title", "Untitled Video")
    link = f"https://www.youtube.com/watch?v={video_id}"

    channel = data.get("channel", {})
    ch_name = channel.get("name", "Unknown")
    ch_link = channel.get("link", "")
    ch_subs = channel.get("subscribers", "")
    ch_str = f"[{ch_name}]({ch_link})" if ch_link else ch_name
    if ch_subs:
        ch_str += f" ({ch_subs})"

    views = data.get("views", "N/A")
    likes = data.get("likes", "N/A")
    published = data.get("published_date", "N/A")

    lines = [
        f"## YouTube Video: [{title}]({link})",
        f"- **Channel**: {ch_str}",
        f"- **Views**: {views}",
        f"- **Likes**: {likes}",
        f"- **Published Date**: {published}",
    ]

    desc_raw = data.get("description")
    if isinstance(desc_raw, dict):
        desc_text = desc_raw.get("content", "")
    elif isinstance(desc_raw, str):
        desc_text = desc_raw
    else:
        desc_text = ""

    if desc_text:
        trimmed = desc_text[:600] + ("..." if len(desc_text) > 600 else "")
        lines.append(f"\n### Description:\n{trimmed}")

    chapters = data.get("chapters", [])
    if chapters:
        lines.append("\n### Chapters:")
        for chap in chapters[:8]:
            ch_title = chap.get("title", "")
            ch_time = chap.get("time", "")
            lines.append(f"- `{ch_time}`: {ch_title}")

    return "\n".join(lines)


def _format_channel_details(data: dict) -> str:
    """Format YouTube channel details."""
    channel = data.get("channel_results", {})
    if not channel:
        return "Could not retrieve channel details."

    title = channel.get("title", "Unknown Channel")
    handle = channel.get("handle", "")
    link = channel.get("link", "")
    subs = channel.get("subscribers_text") or channel.get("subscribers", "N/A")
    videos_count = channel.get("videos_text") or channel.get("video_count", "N/A")
    description = channel.get("description", "")

    header_title = f"[{title}]({link})" if link else title
    if handle:
        header_title += f" ({handle})"

    lines = [
        f"## YouTube Channel: {header_title}",
        f"- **Subscribers**: {subs}",
        f"- **Total Videos**: {videos_count}",
    ]

    if description:
        trimmed_desc = description[:400] + ("..." if len(description) > 400 else "")
        lines.append(f"- **About**: {trimmed_desc}")

    recent_videos = data.get("videos_results", [])
    if recent_videos:
        lines.append("\n### Recent Videos:")
        for idx, vid in enumerate(recent_videos[:5], 1):
            v_title = vid.get("title", "Untitled")
            v_link = vid.get("link", "")
            v_views = vid.get("views", "N/A")
            v_length = vid.get("length", "")
            v_pub = vid.get("published_date", "")

            meta_parts = []
            if v_length:
                meta_parts.append(v_length)
            if v_views:
                meta_parts.append(v_views)
            if v_pub:
                meta_parts.append(v_pub)
            meta_str = " • ".join(meta_parts)

            lines.append(f"{idx}. [{v_title}]({v_link}) ({meta_str})")

    return "\n".join(lines)


@tool
def youtube_tool(query: str, action: str = "auto") -> str:
    """
    All-in-one YouTube tool using SerpAPI for YouTube Search, Channel details, and Video analytics.

    Parameters:
    - query (str): The search keywords, topic, video URL/ID, or channel handle/URL/ID.
    - action (str, optional): The action to execute.
      - 'auto' (default): Automatically detects action based on query:
          * Video URL or video ID -> fetches detailed video metadata
          * Channel handle (@handle) or channel URL -> fetches channel details
          * General text -> performs YouTube search
      - 'search': Searches YouTube for matching videos, playlists, or channels.
      - 'video': Fetches in-depth information about a specific video (views, likes, channel, chapters, description) using video URL or ID.
      - 'channel': Fetches channel information, subscriber stats, and recent uploads using channel handle, name, or channel ID.
    """
    api_key = os.getenv("SERPAPI_API_KEY") or SERPAPI_API_KEY
    if not api_key:
        return "SERPAPI_API_KEY is not configured in the environment."

    clean_query = query.strip()
    if not clean_query:
        return "Please provide a valid query, video ID/URL, or channel name."

    act = action.strip().lower()

    # Automatic routing if action is 'auto'
    if act == "auto":
        extracted_vid = _extract_video_id(clean_query)
        if extracted_vid:
            act = "video"
            clean_query = extracted_vid
        elif clean_query.startswith("@") or "youtube.com/@" in clean_query or "youtube.com/channel/" in clean_query:
            act = "channel"
        else:
            act = "search"

    url = "https://serpapi.com/search"

    try:
        if act == "video":
            vid_id = _extract_video_id(clean_query) or clean_query
            params = {
                "engine": "youtube_video",
                "v": vid_id,
                "api_key": api_key,
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                return f"YouTube Video error for ID '{vid_id}': {data['error']}"
            return _format_video_details(data, vid_id)

        elif act == "channel":
            channel_id = _extract_channel_id(clean_query)
            params = {
                "engine": "youtube_channel",
                "channel_id": channel_id,
                "api_key": api_key,
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                return f"YouTube Channel error for '{channel_id}': {data['error']}"
            return _format_channel_details(data)

        else:  # 'search'
            params = {
                "engine": "youtube",
                "search_query": clean_query,
                "api_key": api_key,
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                return f"YouTube Search error for '{clean_query}': {data['error']}"
            return _format_search_results(clean_query, data)

    except requests.RequestException as e:
        return f"Failed to connect to YouTube API: {str(e)}"
    except Exception as e:
        return f"An error occurred while processing YouTube request: {str(e)}"
