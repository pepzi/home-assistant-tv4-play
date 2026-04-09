from dataclasses import dataclass
import json
import aiohttp
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
)
import logging

_LOGGER = logging.getLogger(__name__)

REFRESH_TOKEN_URL = "https://auth.tv4.a2d.tv/v2/auth/token"
PLAYBACK_URL = "https://playback2.a2d.tv/play"
GRAPHQL_URL = "https://nordic-gateway.tv4.a2d.tv/graphql"


@dataclass
class Episode:
    id: str
    title: str
    image_url: str


async def fetch_access_token(refresh_token: str) -> str:
    """Fetch a new access token using a refresh token."""
    query_data = {
        "grant_type": "refresh_token",
        "is_child": False,
        "profile_id": "default",
        "refresh_token": refresh_token,
    }
    headers = {
        "client-name": "tv4-web",
        "content-type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            REFRESH_TOKEN_URL, json=query_data, headers=headers
        ) as response:
            if response.status == 401:
                raise ConfigEntryAuthFailed(await response_error(response))
            elif response.status != 200:
                raise Exception(
                    f"Could not fetch access token from refresh token, status code: {response.status}, message: {await response_error(response)}"
                )

            data = await response.json()
            return data["access_token"]


async def response_error(response) -> str:
    try:
        data = await response.json()
        return data["error"]["message"]
    except Exception:
        return "Unknown error"


async def get_video_url(access_token: str, video_id: str):
    """Get the video stream URL for a specific video_id."""
    url = "https://playback2.a2d.tv/video"

    params = {
        "service": "tv4",
        "device": "browser",
        "protocol": "hls",
        "videoId": video_id,
        "drm": "widevine",
        "client": "tv4play-web",
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            data = await response.json()

            if response.status != 200 or data.get("errorCode"):
                error_code = data.get("errorCode", "unknown")
                _LOGGER.error("Failed to fetch video URL for %s: %s", video_id, error_code)
                raise Exception(f"Could not fetch the CDN data: {error_code}")

            # Hitta HLS stream
            if "playback" in data and "items" in data["playback"]:
                for item in data["playback"]["items"]:
                    if item.get("protocol") == "hls" and "url" in item:
                        return item["url"]

            # Fallback om ingen items-lista
            if "playback" in data and "url" in data["playback"]:
                return data["playback"]["url"]

            raise Exception("No valid video URL found in response")
            
async def get_suggested_episode(access_token: str, program_id: str) -> Episode:
    "Get information about the suggested episode based on the program name"

    variables = {
        "id": program_id,
    }

    query = """
        query($id: ID!) {
            series(id: $id) {
                suggestedEpisode {
                    episode {
                        id
                        title
                        images {
                            main16x9 {
                                sourceEncoded
                            }
                        }
                        series {
                            title
                        }
                    }
                }
            }
        }
    """

    async with aiohttp.ClientSession() as session:
        async with session.get(
            GRAPHQL_URL,
            params={
                "variables": json.dumps(variables),
                "query": query,
            },
            headers={
                "authorization": f"Bearer {access_token}",
                "client-name": "tv4-web",
                "client-version": "5.3.0",
                "content-type": "application/json",
            },
        ) as response:
            if response.status != 200:
                raise Exception(
                    f"Could not fetch suggested episode, status code: {response.status}"
                )

            data = await response.json()
            series = data["data"]["series"]
            if series is None:
                raise Exception(f"Could not find the series with id {program_id}")
            suggested_episode = series["suggestedEpisode"]
            if suggested_episode is None:
                raise Exception(f"No suggested episode found for {program_id}")
            episode = suggested_episode["episode"]
            if episode is None:
                raise Exception(f"No episode found for {program_id}")

            return Episode(
                id=episode["id"],
                title=f"{episode['series']['title']} - {episode['title']}",
                image_url=episode["images"]["main16x9"]["sourceEncoded"],
            )
