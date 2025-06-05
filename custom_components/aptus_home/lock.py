"""Aptus Home lock platform."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.lock import LockEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import AptusHomeConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AptusHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aptus Home lock entities."""
    client = entry.runtime_data

    # Get available locks from the client
    locks_data = await hass.async_add_executor_job(client.list_available_locks)  # type: ignore  # noqa: PGH003
    if isinstance(locks_data, list):
        entities = [AptusHomeLock(client, lock_info) for lock_info in locks_data]
        async_add_entities(entities)
    else:
        _LOGGER.warning("Could not retrieve locks: %s", locks_data)


class AptusHomeLock(LockEntity):
    """Representation of an Aptus Home lock."""

    def __init__(self, client, lock_info: dict[str, Any]) -> None:  # noqa: ANN001
        """Initialize the lock."""
        self._client = client
        self._lock_info = lock_info
        self._attr_name = lock_info["name"]
        self._attr_unique_id = f"aptus_lock_{lock_info['id']}"
        self._lock_id = lock_info["id"]
        self._attr_is_locked = None
        self._unlock_time: float | None = None
        self._unlock_duration = 5.0  # Door stays unlocked for 5 seconds

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        return self._attr_is_locked

    async def async_update(self) -> None:
        """Fetch new state data for this lock."""
        # Check if door should still be unlocked
        if self._unlock_time is not None:
            time_since_unlock = time.time() - self._unlock_time
            if time_since_unlock < self._unlock_duration:
                self._attr_is_locked = False
            else:
                self._attr_is_locked = True
                self._unlock_time = None  # Reset unlock time
        else:
            self._attr_is_locked = True

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        # Can't lock the entrance doors, it automatically locks when closed.

    async def async_unlock(self) -> None:
        """Unlock the device."""
        result = await self.hass.async_add_executor_job(
            self._client.unlock_entrance_door, self._lock_id
        )
        if result.get("error"):
            _LOGGER.error("Failed to unlock: %s", result.get("message"))
        else:
            # Set unlock time to simulate door being unlocked
            self._unlock_time = time.time()
            self._attr_is_locked = False
            _LOGGER.debug(
                "Door unlocked, will automatically lock in %s seconds",
                self._unlock_duration,
            )
