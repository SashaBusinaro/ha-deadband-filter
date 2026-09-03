"""Sensor platform for deadband_filter."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
)
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DELTA,
    CONF_HEARTBEAT,
    CONF_PERCENTAGE,
    CONF_PRECISION,
    CONF_SOURCE,
    DEFAULT_NAME_SUFFIX,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
        AddEntitiesCallback,
    )
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

ATTR_STATE_CLASS = "state_class"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SOURCE): cv.entity_id,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DELTA): vol.Coerce(float),
        vol.Optional(CONF_PERCENTAGE): vol.Coerce(float),
        vol.Optional(CONF_HEARTBEAT): cv.time_period,
        vol.Optional(CONF_PRECISION): vol.Coerce(int),
    }
)


@dataclass(frozen=True)
class DeadbandFilterOptions:
    """Options for deadband filter."""

    delta: float | None = None
    percentage: float | None = None
    heartbeat: timedelta | None = None
    precision: int | None = None


def _parse_heartbeat(heartbeat_val: Any) -> timedelta | None:
    """Parse heartbeat value into timedelta."""
    if heartbeat_val is None:
        return None
    if isinstance(heartbeat_val, timedelta):
        return heartbeat_val
    if isinstance(heartbeat_val, int | float):
        return timedelta(seconds=heartbeat_val)
    if isinstance(heartbeat_val, dict):
        return cv.time_period_dict(heartbeat_val)
    if isinstance(heartbeat_val, str):
        return cv.time_period(heartbeat_val)
    return None


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the deadband_filter sensor from YAML."""
    await async_setup_reload_service(hass, DOMAIN, [Platform.SENSOR])

    source = config[CONF_SOURCE]
    name = config.get(CONF_NAME)
    unique_id = config.get(CONF_UNIQUE_ID)
    options = DeadbandFilterOptions(
        delta=config.get(CONF_DELTA),
        percentage=config.get(CONF_PERCENTAGE),
        heartbeat=_parse_heartbeat(config.get(CONF_HEARTBEAT)),
        precision=config.get(CONF_PRECISION),
    )

    async_add_entities(
        [
            DeadbandFilterSensor(
                hass=hass,
                source_entity_id=source,
                custom_name=name,
                unique_id=unique_id,
                options=options,
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up deadband_filter sensor from config entry."""
    options_dict = {**entry.data, **entry.options}
    source = options_dict[CONF_SOURCE]
    name = entry.title or options_dict.get(CONF_NAME)
    unique_id = entry.entry_id
    options = DeadbandFilterOptions(
        delta=options_dict.get(CONF_DELTA),
        percentage=options_dict.get(CONF_PERCENTAGE),
        heartbeat=_parse_heartbeat(options_dict.get(CONF_HEARTBEAT)),
        precision=options_dict.get(CONF_PRECISION),
    )

    async_add_entities(
        [
            DeadbandFilterSensor(
                hass=hass,
                source_entity_id=source,
                custom_name=name,
                unique_id=unique_id,
                options=options,
            )
        ]
    )


class DeadbandFilterSensor(RestoreSensor, SensorEntity):
    """Deadband filter sensor entity."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        source_entity_id: str,
        custom_name: str | None,
        unique_id: str | None,
        options: DeadbandFilterOptions,
    ) -> None:
        """Initialize the deadband filter sensor."""
        self.hass = hass
        self._source_entity_id = source_entity_id
        self._custom_name = custom_name
        self._options = options

        self._last_published_value: float | None = None
        self._last_published_time: datetime | None = None
        self._heartbeat_unsub: CALLBACK_TYPE | None = None
        self._suppressed_count = 0
        self._attr_available = True
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_icon = None

        if unique_id:
            self._attr_unique_id = unique_id
        else:
            self._attr_unique_id = f"{source_entity_id}_deadband_filtered"

        if custom_name:
            self._attr_name = custom_name
        else:
            source_state = hass.states.get(source_entity_id)
            if source_state and source_state.name:
                self._attr_name = f"{source_state.name} {DEFAULT_NAME_SUFFIX}"
            else:
                object_id = split_entity_id(source_entity_id)[1]
                self._attr_name = (
                    f"{object_id.replace('_', ' ').title()} {DEFAULT_NAME_SUFFIX}"
                )

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()

        await self._restore_state()
        self._initialize_from_source()
        self._start_heartbeat()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity_id],
                self._async_source_state_changed,
            )
        )

    async def _restore_state(self) -> None:
        """Restore previously saved state and metadata."""
        last_state = await self.async_get_last_state()
        if not last_state:
            return

        if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                restored_val = float(last_state.state)
            except ValueError, TypeError:
                restored_val = None

            if restored_val is not None:
                if self._options.precision is not None:
                    restored_val = round(restored_val, self._options.precision)
                self._last_published_value = restored_val
                self._attr_native_value = restored_val
                self._last_published_time = last_state.last_updated

        attrs = last_state.attributes
        if not self.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = attrs.get(ATTR_UNIT_OF_MEASUREMENT)
        if not self.device_class:
            self._attr_device_class = attrs.get(ATTR_DEVICE_CLASS)
        if not self.state_class:
            self._attr_state_class = attrs.get(ATTR_STATE_CLASS)
        if not self.icon:
            self._attr_icon = attrs.get(ATTR_ICON)

    def _initialize_from_source(self) -> None:
        """Sync metadata and initial value from source state if available."""
        source_state = self.hass.states.get(self._source_entity_id)
        if not source_state:
            return

        self._sync_metadata(source_state)
        if self._last_published_value is None and source_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            try:
                val = float(source_state.state)
            except ValueError, TypeError:
                return
            else:
                if self._options.precision is not None:
                    val = round(val, self._options.precision)
                self._publish_value(val, dt_util.utcnow())

    def _start_heartbeat(self) -> None:
        """Start heartbeat timer on startup if applicable."""
        if self._options.heartbeat is None or self._last_published_value is None:
            return

        if self._last_published_time:
            elapsed = dt_util.utcnow() - self._last_published_time
            remaining = self._options.heartbeat - elapsed
            delay = max(0.0, remaining.total_seconds())
            self._schedule_heartbeat(delay)
        else:
            self._schedule_heartbeat(self._options.heartbeat.total_seconds())

    async def async_will_remove_from_hass(self) -> None:
        """Cancel heartbeat timer when removing."""
        self._cancel_heartbeat()
        await super().async_will_remove_from_hass()

    def _sync_metadata(self, state: State) -> None:
        """Sync metadata attributes from source state."""
        attrs = state.attributes
        if (unit := attrs.get(ATTR_UNIT_OF_MEASUREMENT)) is not None:
            self._attr_native_unit_of_measurement = unit
        if (dev_class := attrs.get(ATTR_DEVICE_CLASS)) is not None:
            self._attr_device_class = dev_class
        if (state_class := attrs.get(ATTR_STATE_CLASS)) is not None:
            self._attr_state_class = state_class
        if (icon := attrs.get(ATTR_ICON)) is not None:
            self._attr_icon = icon

    @callback
    def _async_source_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle state changes of the source entity."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        self._sync_metadata(new_state)
        now = dt_util.utcnow()

        # Handle availability changes
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if self._attr_available:
                self._attr_available = False
                self._attr_native_value = None
                self._cancel_heartbeat()
                self.async_write_ha_state()
            return

        was_unavailable = not self._attr_available
        self._attr_available = True

        try:
            current_val = float(new_state.state)
        except ValueError, TypeError:
            if self._attr_available:
                self._attr_available = False
                self._attr_native_value = None
                self._cancel_heartbeat()
                self.async_write_ha_state()
            return

        if self._options.precision is not None:
            current_val = round(current_val, self._options.precision)

        if was_unavailable or self._last_published_value is None:
            self._publish_value(current_val, now)
            return

        if self._should_publish(current_val, now):
            self._publish_value(current_val, now)
        else:
            self._suppressed_count += 1

    def _should_publish(self, current_val: float, now: datetime) -> bool:
        """Check if update criteria (delta, percentage, heartbeat) are met."""
        last_val = self._last_published_value
        if last_val is None:
            return True

        # 1. Absolute delta
        if (
            self._options.delta is not None
            and abs(current_val - last_val) >= self._options.delta
        ):
            return True

        # 2. Percentage variation
        if self._options.percentage is not None:
            if abs(last_val) > 0:
                diff_pct = (abs(current_val - last_val) / abs(last_val)) * 100.0
                if diff_pct >= self._options.percentage:
                    return True
            elif abs(current_val) > 0:
                if self._options.delta is not None:
                    if abs(current_val) >= self._options.delta:
                        return True
                else:
                    return True

        # 3. Heartbeat
        return bool(
            self._options.heartbeat is not None
            and self._last_published_time
            and (now - self._last_published_time) >= self._options.heartbeat
        )

    def _publish_value(self, val: float, now: datetime) -> None:
        """Publish new value and reset heartbeat and suppression counter."""
        self._attr_native_value = val
        self._last_published_value = val
        self._last_published_time = now
        self._suppressed_count = 0
        if self._options.heartbeat is not None:
            self._schedule_heartbeat(self._options.heartbeat.total_seconds())
        self.async_write_ha_state()

    def _schedule_heartbeat(self, delay: float) -> None:
        """Schedule the next heartbeat timer."""
        self._cancel_heartbeat()

        @callback
        def _async_heartbeat_fired(_now: datetime) -> None:
            """Publish the current value on heartbeat timeout."""
            self._heartbeat_unsub = None
            if not self.hass.is_running:
                return

            source_state = self.hass.states.get(self._source_entity_id)
            now = dt_util.utcnow()
            if source_state and source_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                try:
                    val = float(source_state.state)
                except ValueError, TypeError:
                    pass
                else:
                    if self._options.precision is not None:
                        val = round(val, self._options.precision)
                    self._publish_value(val, now)
                    return

            if self._last_published_value is not None and self._attr_available:
                self._publish_value(self._last_published_value, now)

        self._heartbeat_unsub = async_call_later(
            self.hass, max(0.1, delay), _async_heartbeat_fired
        )

    def _cancel_heartbeat(self) -> None:
        """Cancel any scheduled heartbeat timer."""
        if self._heartbeat_unsub:
            self._heartbeat_unsub()
            self._heartbeat_unsub = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic extra state attributes."""
        return {
            CONF_SOURCE: self._source_entity_id,
            "last_published_value": self._last_published_value,
            "last_published_time": (
                self._last_published_time.isoformat()
                if self._last_published_time
                else None
            ),
            "suppressed_updates": self._suppressed_count,
        }
