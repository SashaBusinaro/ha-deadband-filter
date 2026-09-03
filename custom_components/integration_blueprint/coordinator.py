"""DataUpdateCoordinator for integration_blueprint."""

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    IntegrationBlueprintApiClientAuthenticationError,
    IntegrationBlueprintApiClientError,
    IntegrationBlueprintApiClientRateLimitError,
)

if TYPE_CHECKING:
    from .data import IntegrationBlueprintConfigEntry


# NOTE: this coordinator only implements `_async_update_data` (periodic polling).
# Override `_async_setup` for one-time init that needs to run before the first
# refresh — e.g. fetching static device metadata (firmware version, model) so
# entity.py can pass it to DeviceInfo.
# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
# NOTE: `Any` is the coordinator data type. Once your API client returns a
# typed object (dataclass/TypedDict), substitute it here and in
# `_async_update_data` so entities get typed `coordinator.data`.
class BlueprintDataUpdateCoordinator(DataUpdateCoordinator[Any]):
    """Class to manage fetching data from the API."""

    config_entry: IntegrationBlueprintConfigEntry

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        try:
            return await self.config_entry.runtime_data.client.async_get_data()
        except IntegrationBlueprintApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except IntegrationBlueprintApiClientRateLimitError as exception:
            raise UpdateFailed(
                exception,
                retry_after=exception.retry_after,
            ) from exception
        except IntegrationBlueprintApiClientError as exception:
            raise UpdateFailed(exception) from exception
