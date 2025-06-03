"""Integration for Aptus Home."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .AptusClient import AptusClient

_PLATFORMS: list[Platform] = [Platform.LOCK]

type AptusHomeConfigEntry = ConfigEntry[AptusClient]


async def async_setup_entry(hass: HomeAssistant, entry: AptusHomeConfigEntry) -> bool:
    """Set up Aptus Home from a config entry."""
    # Create API instance
    client = AptusClient(
        base_url=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    # Validate the API connection and authentication
    try:
        login_success = await hass.async_add_executor_job(client.login)
        if not login_success:
            raise ConfigEntryNotReady("Failed to authenticate with Aptus Home")  # noqa: TRY301
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to Aptus Home: {err}") from err

    # Store API object for platforms to access
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AptusHomeConfigEntry) -> bool:
    """Unload a config entry."""
    # Logout from the API
    if entry.runtime_data:
        await hass.async_add_executor_job(entry.runtime_data.logout)

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
