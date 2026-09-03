"""Adds config flow for Deadband Filter."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .const import (
    CONF_DELTA,
    CONF_HEARTBEAT,
    CONF_PERCENTAGE,
    CONF_PRECISION,
    CONF_SOURCE,
    DEFAULT_NAME_SUFFIX,
    DOMAIN,
)


def _validate_criteria(
    user_input: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    """Validate user configuration inputs."""
    errors: dict[str, str] = {}
    cleaned_data: dict[str, Any] = dict(user_input)

    delta = user_input.get(CONF_DELTA)
    percentage = user_input.get(CONF_PERCENTAGE)
    heartbeat = user_input.get(CONF_HEARTBEAT)

    if delta is not None and delta <= 0:
        errors[CONF_DELTA] = "invalid_delta"
    if percentage is not None and percentage <= 0:
        errors[CONF_PERCENTAGE] = "invalid_percentage"
    if heartbeat is not None:
        # Check if duration dict has positive total
        if isinstance(heartbeat, dict):
            try:
                td = cv.time_period_dict(heartbeat)
                if td.total_seconds() <= 0:
                    heartbeat = None
                    cleaned_data.pop(CONF_HEARTBEAT, None)
            except vol.Invalid, TypeError:
                errors[CONF_HEARTBEAT] = "invalid_heartbeat"
        elif isinstance(heartbeat, int | float) and heartbeat <= 0:
            errors[CONF_HEARTBEAT] = "invalid_heartbeat"

    if (
        not errors
        and delta is None
        and percentage is None
        and cleaned_data.get(CONF_HEARTBEAT) is None
    ):
        errors["base"] = "no_filter_criteria"

    return errors, cleaned_data


class DeadbandFilterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Deadband Filter."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, cleaned_data = _validate_criteria(user_input)
            if not errors:
                source = cleaned_data[CONF_SOURCE]
                await self.async_set_unique_id(f"{source}_deadband_filtered")
                self._abort_if_unique_id_configured()

                title = cleaned_data.get(CONF_NAME)
                if not title:
                    source_state = self.hass.states.get(source)
                    if source_state and source_state.name:
                        title = f"{source_state.name} {DEFAULT_NAME_SUFFIX}"
                    else:
                        title = f"{source} {DEFAULT_NAME_SUFFIX}"

                return self.async_create_entry(
                    title=title,
                    data=cleaned_data,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor"),
                ),
                vol.Optional(CONF_NAME): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
                ),
                vol.Optional(CONF_DELTA): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        step="any",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(CONF_PERCENTAGE): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=1000,
                        step="any",
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(CONF_HEARTBEAT): selector.DurationSelector(
                    selector.DurationSelectorConfig(enable_day=False),
                ),
                vol.Optional(CONF_PRECISION): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return DeadbandFilterOptionsFlow()


class DeadbandFilterOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Deadband Filter."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current_options = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            # Preserve the source entity from initial config
            combined = {**user_input, CONF_SOURCE: current_options[CONF_SOURCE]}
            errors, cleaned_data = _validate_criteria(combined)
            if not errors:
                return self.async_create_entry(title="", data=cleaned_data)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DELTA,
                    description={"suggested_value": current_options.get(CONF_DELTA)},
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        step="any",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    CONF_PERCENTAGE,
                    description={
                        "suggested_value": current_options.get(CONF_PERCENTAGE)
                    },
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=1000,
                        step="any",
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    CONF_HEARTBEAT,
                    description={
                        "suggested_value": current_options.get(CONF_HEARTBEAT)
                    },
                ): selector.DurationSelector(
                    selector.DurationSelectorConfig(enable_day=False),
                ),
                vol.Optional(
                    CONF_PRECISION,
                    description={
                        "suggested_value": current_options.get(CONF_PRECISION)
                    },
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
