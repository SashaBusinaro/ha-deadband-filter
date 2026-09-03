"""Unit tests for the DeadbandFilterSensor platform and deadband logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, EventStateChangedData, State

from custom_components.deadband_filter.config_flow import _validate_criteria
from custom_components.deadband_filter.const import (
    CONF_DELTA,
    CONF_PERCENTAGE,
    CONF_SOURCE,
)
from custom_components.deadband_filter.sensor import (
    ATTR_STATE_CLASS,
    DeadbandFilterOptions,
    DeadbandFilterSensor,
    _parse_heartbeat,
)


def _create_test_sensor(
    options: DeadbandFilterOptions, source_id: str = "sensor.test"
) -> DeadbandFilterSensor:
    """Create a configured test sensor with mocked async_write_ha_state."""
    hass = MagicMock()
    hass.states.get.return_value = None
    hass.is_running = True

    sensor = DeadbandFilterSensor(
        hass=hass,
        source_entity_id=source_id,
        custom_name=None,
        unique_id=None,
        options=options,
    )
    sensor.entity_id = f"{source_id}_filtered"
    sensor.async_write_ha_state = MagicMock()  # type: ignore[method-assign]
    return sensor


def test_parse_heartbeat() -> None:
    """Test parsing various heartbeat representation formats."""
    assert _parse_heartbeat(None) is None
    assert _parse_heartbeat(timedelta(seconds=60)) == timedelta(seconds=60)
    assert _parse_heartbeat(300) == timedelta(seconds=300)
    assert _parse_heartbeat(45.5) == timedelta(seconds=45.5)
    assert _parse_heartbeat({"minutes": 5}) == timedelta(minutes=5)
    assert _parse_heartbeat("00:05:00") == timedelta(minutes=5)


def test_validate_criteria() -> None:
    """Test config flow validation criteria."""
    # Empty inputs - error
    errors, _ = _validate_criteria({CONF_SOURCE: "sensor.test"})
    assert errors == {"base": "no_filter_criteria"}

    # Invalid delta <= 0
    errors, _ = _validate_criteria({CONF_SOURCE: "sensor.test", CONF_DELTA: -5})
    assert errors == {CONF_DELTA: "invalid_delta"}

    # Invalid percentage <= 0
    errors, _ = _validate_criteria({CONF_SOURCE: "sensor.test", CONF_PERCENTAGE: 0})
    assert errors == {CONF_PERCENTAGE: "invalid_percentage"}

    # Valid inputs
    errors, cleaned = _validate_criteria(
        {
            CONF_SOURCE: "sensor.test",
            CONF_DELTA: 10.0,
            CONF_PERCENTAGE: 5.0,
        }
    )
    assert not errors
    assert cleaned[CONF_DELTA] == 10.0


def test_sensor_init() -> None:
    """Test sensor initialization and default naming."""
    options = DeadbandFilterOptions(delta=10.0)
    sensor = _create_test_sensor(options, source_id="sensor.power_raw")

    assert sensor.name == "Power Raw Filtered"
    assert sensor.unique_id == "sensor.power_raw_deadband_filtered"
    assert sensor.available is True


def test_sensor_init_from_entity_registry_name() -> None:
    """Test sensor initialization using entity registry configured name."""
    hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.name = "Power Home Appliances"
    mock_entry.original_name = "Shelly Power"

    mock_ent_reg = MagicMock()
    mock_ent_reg.async_get.return_value = mock_entry
    hass.data = {"entity_registry": mock_ent_reg}
    hass.states.get.return_value = None

    options = DeadbandFilterOptions(delta=15.0)
    sensor = DeadbandFilterSensor(
        hass=hass,
        source_entity_id="sensor.shellyem_channel_1_power",
        custom_name=None,
        unique_id=None,
        options=options,
    )

    assert sensor.name == "Power Home Appliances Filtered"
    assert sensor.unique_id == "sensor.shellyem_channel_1_power_deadband_filtered"


def test_sensor_init_from_entity_registry_original_name() -> None:
    """Test sensor initialization using original_name when name is unset."""
    hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.name = None
    mock_entry.original_name = "Power Home Appliances"

    mock_ent_reg = MagicMock()
    mock_ent_reg.async_get.return_value = mock_entry
    hass.data = {"entity_registry": mock_ent_reg}
    hass.states.get.return_value = None

    options = DeadbandFilterOptions(delta=15.0)
    sensor = DeadbandFilterSensor(
        hass=hass,
        source_entity_id="sensor.shellyem_channel_1_power",
        custom_name=None,
        unique_id=None,
        options=options,
    )

    assert sensor.name == "Power Home Appliances Filtered"


def test_sensor_init_from_source_state_when_registry_empty() -> None:
    """Test sensor initialization using source state name when registry empty."""
    hass = MagicMock()
    mock_ent_reg = MagicMock()
    mock_ent_reg.async_get.return_value = None
    hass.data = {"entity_registry": mock_ent_reg}
    hass.states.get.return_value = State(
        "sensor.power_raw", "100", {"friendly_name": "Living Room Power"}
    )

    options = DeadbandFilterOptions(delta=15.0)
    sensor = DeadbandFilterSensor(
        hass=hass,
        source_entity_id="sensor.power_raw",
        custom_name=None,
        unique_id=None,
        options=options,
    )

    assert sensor.name == "Living Room Power Filtered"


def test_sensor_init_custom_name_override() -> None:
    """Test custom name overrides registry and state."""
    hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.name = "Power Home Appliances"

    mock_ent_reg = MagicMock()
    mock_ent_reg.async_get.return_value = mock_entry
    hass.data = {"entity_registry": mock_ent_reg}

    options = DeadbandFilterOptions(delta=15.0)
    sensor = DeadbandFilterSensor(
        hass=hass,
        source_entity_id="sensor.shellyem_channel_1_power",
        custom_name="Custom Filtered Name",
        unique_id=None,
        options=options,
    )

    assert sensor.name == "Custom Filtered Name"


def test_delta_filtering() -> None:
    """Test absolute delta threshold filtering."""
    options = DeadbandFilterOptions(delta=40.0)
    sensor = _create_test_sensor(options, source_id="sensor.power_raw")

    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
    with patch(
        "custom_components.deadband_filter.sensor.dt_util.utcnow", return_value=now
    ):
        # 1. First event: value 100 W -> must publish
        event1 = Event(
            "state_changed",
            EventStateChangedData(
                entity_id="sensor.power_raw",
                old_state=None,
                new_state=State("sensor.power_raw", "100.0"),
            ),
        )
        sensor._async_source_state_changed(event1)
        assert sensor.native_value == 100.0
        assert sensor.extra_state_attributes["suppressed_updates"] == 0
        assert sensor.async_write_ha_state.call_count == 1

        # 2. Small jitter: 120 W (change +20 W < delta 40 W) -> suppressed (0 DB writes)
        event2 = Event(
            "state_changed",
            EventStateChangedData(
                entity_id="sensor.power_raw",
                old_state=event1.data["new_state"],
                new_state=State("sensor.power_raw", "120.0"),
            ),
        )
        sensor._async_source_state_changed(event2)
        assert sensor.native_value == 100.0
        assert sensor.extra_state_attributes["suppressed_updates"] == 1
        assert sensor.async_write_ha_state.call_count == 1  # No write!

        # 3. Small jitter: 135 W (+35 W from last 100 W < 40 W) -> suppressed
        event3 = Event(
            "state_changed",
            EventStateChangedData(
                entity_id="sensor.power_raw",
                old_state=event2.data["new_state"],
                new_state=State("sensor.power_raw", "135.0"),
            ),
        )
        sensor._async_source_state_changed(event3)
        assert sensor.native_value == 100.0
        assert sensor.extra_state_attributes["suppressed_updates"] == 2
        assert sensor.async_write_ha_state.call_count == 1  # Still no write!

        # 4. Spike: 145 W (change +45 W from last published 100 W >= 40 W) -> published!
        event4 = Event(
            "state_changed",
            EventStateChangedData(
                entity_id="sensor.power_raw",
                old_state=event3.data["new_state"],
                new_state=State("sensor.power_raw", "145.0"),
            ),
        )
        sensor._async_source_state_changed(event4)
        assert sensor.native_value == 145.0
        assert sensor.extra_state_attributes["suppressed_updates"] == 0
        assert sensor.async_write_ha_state.call_count == 2  # Exactly 1 new write!


def test_percentage_filtering() -> None:
    """Test percentage variation filtering."""
    options = DeadbandFilterOptions(percentage=5.0)
    sensor = _create_test_sensor(options, source_id="sensor.power_raw")

    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
    with patch(
        "custom_components.deadband_filter.sensor.dt_util.utcnow", return_value=now
    ):
        # 1. Initial publish: 200.0 W
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.power_raw",
                    old_state=None,
                    new_state=State("sensor.power_raw", "200.0"),
                ),
            )
        )
        assert sensor.native_value == 200.0
        assert sensor.async_write_ha_state.call_count == 1

        # 2. Change by 3% (206.0 W) -> suppressed
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.power_raw",
                    old_state=None,
                    new_state=State("sensor.power_raw", "206.0"),
                ),
            )
        )
        assert sensor.native_value == 200.0
        assert sensor.extra_state_attributes["suppressed_updates"] == 1
        assert sensor.async_write_ha_state.call_count == 1

        # 3. Change by 6% (212.0 W, diff 12 / 200 = 6% >= 5%) -> published
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.power_raw",
                    old_state=None,
                    new_state=State("sensor.power_raw", "212.0"),
                ),
            )
        )
        assert sensor.native_value == 212.0
        assert sensor.extra_state_attributes["suppressed_updates"] == 0
        assert sensor.async_write_ha_state.call_count == 2


def test_percentage_zero_handling() -> None:
    """Test departure from zero with percentage and delta rules."""
    # Case A: percentage=5%, delta=None -> any departure from 0 triggers update
    options_a = DeadbandFilterOptions(percentage=5.0)
    sensor_a = _create_test_sensor(options_a, source_id="sensor.load")
    sensor_a._last_published_value = 0.0

    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
    with patch(
        "custom_components.deadband_filter.sensor.dt_util.utcnow", return_value=now
    ):
        sensor_a._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.load",
                    old_state=None,
                    new_state=State("sensor.load", "0.5"),
                ),
            )
        )
        assert sensor_a.native_value == 0.5
        assert sensor_a.async_write_ha_state.call_count == 1

    # Case B: percentage=5%, delta=10.0 -> departure from 0 requires delta (10.0)
    options_b = DeadbandFilterOptions(percentage=5.0, delta=10.0)
    sensor_b = _create_test_sensor(options_b, source_id="sensor.load")
    sensor_b._last_published_value = 0.0

    with patch(
        "custom_components.deadband_filter.sensor.dt_util.utcnow", return_value=now
    ):
        # Change to 5.0 (< delta 10.0) -> suppressed
        sensor_b._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.load",
                    old_state=None,
                    new_state=State("sensor.load", "5.0"),
                ),
            )
        )
        assert sensor_b.native_value is None
        assert sensor_b.extra_state_attributes["suppressed_updates"] == 1
        assert sensor_b.async_write_ha_state.call_count == 0

        # Change to 12.0 (>= delta 10.0) -> published
        sensor_b._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.load",
                    old_state=None,
                    new_state=State("sensor.load", "12.0"),
                ),
            )
        )
        assert sensor_b.native_value == 12.0
        assert sensor_b.async_write_ha_state.call_count == 1


def test_heartbeat_timeout() -> None:
    """Test heartbeat interval forces publication after elapsed time."""
    options = DeadbandFilterOptions(delta=50.0, heartbeat=timedelta(minutes=5))
    sensor = _create_test_sensor(options, source_id="sensor.power_raw")

    t0 = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
    with patch(
        "custom_components.deadband_filter.sensor.dt_util.utcnow", return_value=t0
    ):
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.power_raw",
                    old_state=None,
                    new_state=State("sensor.power_raw", "100.0"),
                ),
            )
        )
        assert sensor.native_value == 100.0
        assert sensor.async_write_ha_state.call_count == 1

    # 3 minutes later: small change 105 W (< 50 W, elapsed 3m < 5m) -> suppressed
    t1 = t0 + timedelta(minutes=3)
    with patch(
        "custom_components.deadband_filter.sensor.dt_util.utcnow", return_value=t1
    ):
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.power_raw",
                    old_state=None,
                    new_state=State("sensor.power_raw", "105.0"),
                ),
            )
        )
        assert sensor.native_value == 100.0
        assert sensor.async_write_ha_state.call_count == 1

    # 6 min later: change 106 W (< 50 W, elapsed 6m >= 5m heartbeat) -> published!
    t2 = t0 + timedelta(minutes=6)
    with patch(
        "custom_components.deadband_filter.sensor.dt_util.utcnow", return_value=t2
    ):
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.power_raw",
                    old_state=None,
                    new_state=State("sensor.power_raw", "106.0"),
                ),
            )
        )
        assert sensor.native_value == 106.0
        assert sensor.async_write_ha_state.call_count == 2


def test_availability_transitions() -> None:
    """Test availability changes between available and unavailable/unknown."""
    options = DeadbandFilterOptions(delta=10.0)
    sensor = _create_test_sensor(options, source_id="sensor.voltage")

    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
    with patch(
        "custom_components.deadband_filter.sensor.dt_util.utcnow", return_value=now
    ):
        # 1. Available state: 230.0 V
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.voltage",
                    old_state=None,
                    new_state=State("sensor.voltage", "230.0"),
                ),
            )
        )
        assert sensor.available is True
        assert sensor.native_value == 230.0
        assert sensor.async_write_ha_state.call_count == 1

        # 2. Transition to unavailable
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.voltage",
                    old_state=None,
                    new_state=State("sensor.voltage", STATE_UNAVAILABLE),
                ),
            )
        )
        assert sensor.available is False
        assert sensor.native_value is None
        assert sensor.async_write_ha_state.call_count == 2

        # 3. Back to available with new state: 231.0 V -> published immediately
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.voltage",
                    old_state=None,
                    new_state=State("sensor.voltage", "231.0"),
                ),
            )
        )
        assert sensor.available is True
        assert sensor.native_value == 231.0
        assert sensor.async_write_ha_state.call_count == 3


def test_metadata_inheritance() -> None:
    """Test automatic inheritance of unit, device_class, state_class, and icon."""
    options = DeadbandFilterOptions(delta=10.0, precision=1)
    sensor = _create_test_sensor(options, source_id="sensor.temp_sensor")

    source_state = State(
        "sensor.temp_sensor",
        "22.345",
        attributes={
            ATTR_UNIT_OF_MEASUREMENT: "°C",
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_STATE_CLASS: "measurement",
            ATTR_ICON: "mdi:thermometer",
        },
    )

    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
    with patch(
        "custom_components.deadband_filter.sensor.dt_util.utcnow", return_value=now
    ):
        sensor._async_source_state_changed(
            Event(
                "state_changed",
                EventStateChangedData(
                    entity_id="sensor.temp_sensor",
                    old_state=None,
                    new_state=source_state,
                ),
            )
        )

        assert sensor.native_unit_of_measurement == "°C"
        assert sensor.device_class == "temperature"
        assert sensor.state_class == "measurement"
        assert sensor.icon == "mdi:thermometer"
        assert sensor.native_value == 22.3  # Rounded with precision=1
        assert sensor.async_write_ha_state.call_count == 1


@pytest.mark.asyncio
async def test_restore_state_with_metadata() -> None:
    """Test state and metadata restoration across Home Assistant restarts."""
    options = DeadbandFilterOptions(delta=10.0, precision=1)
    sensor = _create_test_sensor(options, source_id="sensor.power")

    last_state = State(
        "sensor.power_filtered",
        "123.45",
        attributes={
            ATTR_UNIT_OF_MEASUREMENT: "W",
            ATTR_DEVICE_CLASS: "power",
            ATTR_STATE_CLASS: "measurement",
            ATTR_ICON: "mdi:flash",
        },
    )
    sensor.async_get_last_state = AsyncMock(return_value=last_state)

    await sensor._restore_state()

    assert sensor.native_value == 123.5
    assert sensor.native_unit_of_measurement == "W"
    assert sensor.device_class == "power"
    assert sensor.state_class == "measurement"
    assert sensor.icon == "mdi:flash"
