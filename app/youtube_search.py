"""
youtube_search.py
-----------------
Thin wrapper around YouTube Data API v3 for live video resource discovery.
Used by curriculum_builder.py to attach real, topic-matched video links to lessons.
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

_YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_YT_VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"

# Channels known for high-quality technical education (filter by channel if desired)
_PREFERRED_CHANNEL_IDS = [
    "UC8butISFwT-Wl7EV0hUK0BQ",  # freeCodeCamp
    "UCVhQ2NnY5Rskt6UjCUkJ_DA",  # TechWorld with Nana
    "UCWX3yGbODI3RYBmBALKFnWw",  # Simplilearn
    "UCCTVrRjOOdUcLnrISoWdNBQ",  # Amigoscode
]


async def search_youtube_video(query: str, max_results: int = 1) -> dict | None:
    """
    Search YouTube for a topic and return the top video result.

    Returns a dict with keys: name, url, channel, duration_approx
    Returns None if the API key is missing or the request fails.
    """
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        logger.warning("YOUTUBE_API_KEY not set — skipping live video search.")
        return None

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoEmbeddable": "true",
        "videoDuration": "medium",       # 4–20 min clips
        "relevanceLanguage": "en",
        "maxResults": max_results,
        "key": api_key,
        "safeSearch": "strict",
        "order": "relevance",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(_YT_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        if not items:
            logger.info("YouTube search returned no results for: %s", query)
            return None

        item = items[0]
        video_id = item["id"].get("videoId", "")
        snippet = item.get("snippet", {})

        return {
            "name": snippet.get("title", query),
            "url": _YT_VIDEO_URL.format(video_id=video_id),
            "channel": snippet.get("channelTitle", ""),
            "description": snippet.get("description", "")[:120],
            "duration_approx": "varies",
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.warning("YouTube API quota exceeded or key invalid (403).")
        else:
            logger.error("YouTube API HTTP error: %s", e)
        return None
    except Exception as e:
        logger.error("YouTube search failed: %s", e)
        return None
