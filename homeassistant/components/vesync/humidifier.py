"""Support for VeSync humidifier."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.components.humidifier.const import (
    MODE_AUTO,
    MODE_SLEEP,
    MODE_BOOST,
    MODE_NORMAL,
    MODE_ECO,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncDevice
from .const import DOMAIN, SKU_TO_BASE_DEVICE, VS_DISCOVERY, VS_HUMIDIFIERS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "Classic300S": "humidifier",
}

MIST_MODE_AUTO = "auto"
MIST_MODE_SLEEP = "sleep"
MIST_MODE_MANUAL = "manual"
# MIST_MODE_TO_HA = {
#     "auto": MODE_AUTO,
#     "sleep": MODE_SLEEP,
#     MIST_MODE_MANUAL: MODE_NORMAL,
# }

# HA_TO_MIST_MODE = {v: k for k, v in MIST_MODE_TO_HA.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync fan platform."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_HUMIDIFIERS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(SKU_TO_BASE_DEVICE.get(dev.device_type)) == "humidifier":
            entities.append(VeSyncHumidifierHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncHumidifierHA(VeSyncDevice, HumidifierEntity):
    """Representation of a VeSync humidifier."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_available_modes = []
    _attr_mode = MODE_AUTO

    def __init__(self, smarthumidifier):
        """Initialize the VeSync humidifier device."""
        super().__init__(smarthumidifier)
        self._device_class = HumidifierDeviceClass.HUMIDIFIER
        self.smarthumidifier = smarthumidifier

        if MIST_MODE_AUTO in smarthumidifier.mist_modes:
            self._attr_available_modes.append(MODE_AUTO)
        if MIST_MODE_SLEEP in smarthumidifier.mist_modes:
            self._attr_available_modes.append(MODE_SLEEP)
        if MIST_MODE_MANUAL in smarthumidifier.mist_modes:
            self._attr_available_modes.append(MODE_NORMAL)
            if len(smarthumidifier.mist_levels) > 2:
                self._attr_available_modes.extend([MODE_ECO, MODE_BOOST])

        self._attr_min_humidity = 30
        self._attr_max_humidity = 80

    @property
    def device_class(self):
        """Return the device class of the humidifier."""
        return self._device_class

    @property
    def mode(self) -> str | None:
        """Get mode."""
        if not self.details["mode"]:
            return
        elif self.details["mode"] == MIST_MODE_AUTO:
            return MODE_AUTO
        elif self.details["mode"] == MIST_MODE_SLEEP:
            return MODE_SLEEP
        elif self.details["mode"] == MIST_MODE_MANUAL:
            if self.details["mist_virtual_level"] == 1:
                return MODE_ECO
            elif self.details["mist_virtual_level"] == max(
                self.smarthumidifier.mist_levels
            ):
                return MODE_BOOST
            return MODE_NORMAL
        else:
            raise ValueError(f"{self.smarthumidifier.mode} is not a supported mode")

    def set_mode(self, mode: str) -> None:
        """Set new mode."""
        if mode == MODE_AUTO:
            self.smarthumidifier.set_auto_mode()
        elif mode == MODE_SLEEP:
            self.smarthumidifier.set_humidity_mode(MIST_MODE_SLEEP)
        elif mode == MODE_ECO:
            self.smarthumidifier.set_mist_level(1)
        elif mode == MODE_NORMAL:
            self.smarthumidifier.set_mist_level(5)
        elif mode == MODE_BOOST:
            self.smarthumidifier.set_mist_level(9)
        self.schedule_update_ha_state()

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self.smarthumidifier.auto_humidity

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""

        if not self.smarthumidifier.is_on:
            self.smarthumidifier.turn_on()

        self.smarthumidifier.set_humidity(humidity)

        self.schedule_update_ha_state()

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        self.smarthumidifier.turn_on()
        self.set_humidity(percentage)
        self.set_mode(preset_mode)
