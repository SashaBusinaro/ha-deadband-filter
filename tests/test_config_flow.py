"""Unit tests for the DeadbandFilter config flow and options flow."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import State
from homeassistant.data_entry_flow import FlowResultType

from custom_components.deadband_filter.config_flow import (
    DeadbandFilterConfigFlow,
    DeadbandFilterOptionsFlow,
)
from custom_components.deadband_filter.const import (
    CONF_DELTA,
    CONF_HEARTBEAT,
    CONF_PERCENTAGE,
    CONF_PRECISION,
    CONF_SOURCE,
)


@pytest.mark.asyncio
async def test_config_flow_user_step_success() -> None:
    """Test successful user step in config flow."""
    hass = MagicMock()
    source_state = State("sensor.power_raw", "100.0", {ATTR_FRIENDLY_NAME: "Raw Power"})
    hass.states.get.return_value = source_state

    flow = DeadbandFilterConfigFlow()
    flow.hass = hass

    with patch.object(flow, "async_set_unique_id", return_value=None) as mock_set_id:
        result = await flow.async_step_user(
            user_input={
                CONF_SOURCE: "sensor.power_raw",
                CONF_DELTA: 25.0,
                CONF_PERCENTAGE: 5.0,
                CONF_HEARTBEAT: {"minutes": 5},
                CONF_PRECISION: 1,
            }
        )

    mock_set_id.assert_called_once_with("sensor.power_raw_deadband_filtered")
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Raw Power Filtered"
    assert result["data"][CONF_DELTA] == 25.0
    assert result["data"][CONF_PERCENTAGE] == 5.0


@pytest.mark.asyncio
async def test_config_flow_user_step_no_criteria() -> None:
    """Test config flow validation error when no criteria provided."""
    hass = MagicMock()
    flow = DeadbandFilterConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(
        user_input={
            CONF_SOURCE: "sensor.power_raw",
        }
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_filter_criteria"


@pytest.mark.asyncio
async def test_options_flow_success() -> None:
    """Test options flow reconfiguring filter parameters."""
    hass = MagicMock()
    mock_entry = MagicMock(spec=config_entries.ConfigEntry)
    mock_entry.entry_id = "test_entry_id"
    mock_entry.data = {CONF_SOURCE: "sensor.power_raw", CONF_DELTA: 20.0}
    mock_entry.options = {}
    hass.config_entries.async_get_known_entry.return_value = mock_entry

    options_flow = DeadbandFilterOptionsFlow()
    options_flow.hass = hass
    options_flow.handler = "test_entry_id"

    result = await options_flow.async_step_init(
        user_input={
            CONF_DELTA: 30.0,
            CONF_PERCENTAGE: 10.0,
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DELTA] == 30.0
    assert result["data"][CONF_PERCENTAGE] == 10.0
    assert result["data"][CONF_SOURCE] == "sensor.power_raw"
