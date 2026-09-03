"""Constants for deadband_filter."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "deadband_filter"

CONF_SOURCE = "source"
CONF_DELTA = "delta"
CONF_PERCENTAGE = "percentage"
CONF_HEARTBEAT = "heartbeat"
CONF_PRECISION = "precision"

DEFAULT_NAME_SUFFIX = "Filtered"
