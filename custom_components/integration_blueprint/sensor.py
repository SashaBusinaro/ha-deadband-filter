"""Sensor platform for integration_blueprint."""

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .entity import IntegrationBlueprintEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import IntegrationBlueprintConfigEntry

PARALLEL_UPDATES = 1

# NOTE: each EntityDescription `key` becomes part of the entity's unique_id
# (`{entry_id}_{key}`), so it MUST be unique within a config entry. If you add
# a second sensor here, give it a different key.
# NOTE: `translation_key` points at `entity.sensor.<key>` in
# translations/en.json — entity names live there, not in Python.
# https://developers.home-assistant.io/docs/core/entity#generic-properties
# NOTE: the example sensor returns a string (`body` from JSONPlaceholder).
# For numeric sensors set `device_class`, `state_class` and
# `native_unit_of_measurement` on the EntityDescription — this enables unit
# conversion, statistics graphs and long-term statistics in HA.
# https://developers.home-assistant.io/docs/core/entity/sensor
ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="example_sensor",
        translation_key="example_sensor",
        icon="mdi:format-quote-close",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationBlueprintConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        IntegrationBlueprintSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationBlueprintSensor(IntegrationBlueprintEntity, SensorEntity):
    """integration_blueprint Sensor class."""

    @property
    def native_value(self) -> str | None:
        """Return the native value of the sensor."""
        return self.coordinator.data.get("body")
