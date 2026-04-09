"""The tv4_play component."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_ENTITY_ID

from .const import DOMAIN, CONF_CONFIG_ENTRY, CONF_PROGRAM_ID
from .tv4play import (
    fetch_access_token,
    get_suggested_episode,
    get_video_url,
)

_LOGGER = logging.getLogger(__name__)

# Schema for the existing service
SERVICE_PLAY_SUGGESTED_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_PROGRAM_ID): cv.string,
        vol.Required(CONF_CONFIG_ENTRY): cv.string,
    }
)

# Schema for the new play_video service
SERVICE_PLAY_VIDEO_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("video_id"): cv.string,
        vol.Required(CONF_CONFIG_ENTRY): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TV4 Play from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Existing play_suggested service
    async def play_suggested(service: ServiceCall):
        """Play a tv4 play video using suggested episode."""
        entity_id = service.data.get(CONF_ENTITY_ID)
        program_id = service.data.get(CONF_PROGRAM_ID)
        config_entry_id = service.data.get(CONF_CONFIG_ENTRY)

        config_entry = hass.data[DOMAIN][config_entry_id]
        refresh_token: str = config_entry["refresh_token"]

        access_token = await fetch_access_token(refresh_token)
        episode = await get_suggested_episode(access_token, program_id)
        video_url = await get_video_url(access_token, episode.id)

        service_data = {
            "entity_id": entity_id,
            "media_content_id": video_url,
            "media_content_type": "video",
        }

        await hass.services.async_call("media_player", "play_media", service_data, blocking=True)

    # New play_video service for direct video_id (e.g. Beck movies)
    async def play_video(service: ServiceCall):
        """Play a specific TV4 Play video by video_id."""
        entity_id = service.data.get(CONF_ENTITY_ID)
        video_id = service.data.get("video_id")
        config_entry_id = service.data.get(CONF_CONFIG_ENTRY)

        config_entry = hass.data[DOMAIN][config_entry_id]
        refresh_token: str = config_entry["refresh_token"]

        access_token = await fetch_access_token(refresh_token)

        video_url = await get_video_url(access_token, video_id)

        service_data = {
            "entity_id": entity_id,
            "media_content_id": video_url,
            "media_content_type": "video",
        }

        await hass.services.async_call("media_player", "play_media", service_data, blocking=True)

    # Register both services
    hass.services.async_register(
        DOMAIN, "play_suggested", play_suggested, SERVICE_PLAY_SUGGESTED_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, "play_video", play_video, SERVICE_PLAY_VIDEO_SCHEMA
    )

    return True
