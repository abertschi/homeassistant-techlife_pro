import os
import random
import time
from typing import Callable
from unicodedata import name
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.light \
    import (ATTR_WHITE,
            COLOR_MODE_BRIGHTNESS,
            COLOR_MODE_COLOR_TEMP,
            COLOR_MODE_HS,
            COLOR_MODE_RGB,
            COLOR_MODE_RGBW,
            COLOR_MODE_RGBWW, COLOR_MODE_WHITE,
            COLOR_MODE_XY, SUPPORT_BRIGHTNESS,
            ATTR_BRIGHTNESS,
            ATTR_HS_COLOR,
            ATTR_RGB_COLOR,
            SUPPORT_COLOR,
            PLATFORM_SCHEMA,
            LightEntity)

import homeassistant.util.color as color_util

try:
    from .techlife_bulb import TechLifeBulp
except:
    from techlife_pro.techlife_bulb import TechLifeBulp

log = logging.getLogger("techlife_pro.light")

CONF_MAC_ADDRESS = 'mac_address'
CONF_FRIENDLY_NAME = 'name'
CONF_BROKER_URL = 'broker_url'
CONF_BROKER_USERNAME = 'broker_username'
CONF_BROKER_PASSWORD = 'broker_password'
CONF_UNIQUE_ID = 'unique_id'

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC_ADDRESS): cv.string,
    vol.Required(CONF_BROKER_URL): cv.string,
    vol.Optional(CONF_BROKER_USERNAME, default='user'): cv.string,
    vol.Optional(CONF_BROKER_PASSWORD, default='passwd'): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
})


def setup_platform(hass, config, add_entities: Callable, discovery_info=None):
    mac = config.get(CONF_MAC_ADDRESS)
    name = config.get(CONF_FRIENDLY_NAME)
    broker_url = config.get(CONF_BROKER_URL)
    broker_username = config.get(CONF_BROKER_USERNAME)
    broker_password = config.get(CONF_BROKER_PASSWORD)

    light = TechLifeLightEntity(config, broker_url, broker_username, broker_password, mac, name)
    add_entities([light])


class TechLifeLightEntity(LightEntity):
    def __init__(self,
                 ha_config,
                 broker_url,
                 broker_username,
                 broker_password,
                 bulb_mac,
                 bulb_name):
        self._unique_id = 'tl_{}_{}'.format(broker_url, bulb_mac)
        if ha_config and ha_config.get(CONF_UNIQUE_ID):
            self._unique_id = ha_config.get(CONF_UNIQUE_ID)

        if bulb_name:
            self._name = bulb_name
        else:
            self._name = f'light_{bulb_mac}'

        self._light = TechLifeBulp(broker_url,
                                   broker_username,
                                   broker_password,
                                   bulb_mac,
                                   self._name)

        try:
            log.info(f"connecting to light {bulb_mac}"
                     f" at broker {broker_url}")

            self._light.connect()
        except Exception as e:
            log.exception("failed to connect", e)

    @property
    def supported_color_modes(self):
        return [COLOR_MODE_HS, COLOR_MODE_WHITE]

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_on(self) -> bool:
        return self._light.state_power

    @property
    def available(self) -> bool:
        return self._light.state_is_available

    @property
    def color_mode(self) -> str:
        mode = ''
        if self._light.state_type == self._light.STATE_TYPE_RGB:
            mode = 'hs'
        elif self._light.state_type == self._light.STATE_TYPE_WHITE:
            mode = 'white'
        else:
            mode = 'onoff'
        log.debug(f"{self._name}: color_mode={mode}")
        return mode

    @property
    def brightness(self) -> int:
        if not self._light.state_is_available:
            log.warning("light not available, cant get brightness")
            return 0
        else:
            b = self._light.get_brightness()
            log.debug(f"{self._name}: brightness={b}")
            return b

    @property
    def assumed_state(self):
        return False

    @property
    def hs_color(self):
        if not self._light.state_is_available:
            log.warning("light not available, cant get color")
            return None
        else:
            rgb = self._light.state_rgb
            hs = color_util.color_RGB_to_hs(rgb[0], rgb[1], rgb[2])

            log.debug(f"{self._name}: hs_color={hs}, rgb={rgb}")
            return hs

    def turn_on(self, **kwargs):
        if not self.is_on:
            self.on()
        white_mode = not self._light.is_color_mode()

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            brightness = self.brightness

        if ATTR_HS_COLOR in kwargs:
            color = kwargs[ATTR_HS_COLOR]
            white_mode = False
        else:
            color = self.hs_color

        if ATTR_WHITE in kwargs:
            brightness = kwargs[ATTR_WHITE]
            white_mode = True

        rgb = color_util.color_hs_to_RGB(color[0], color[1])

        log.info(f'{self._name}: turn_on: white_mode={white_mode},'
                 f' brightn={brightness}, '
                 f'hs={color}, rgb={rgb} kwargs: {kwargs}')

        if white_mode:
            self._light.white(brightness)
        else:
            self._light.color(rgb[0], rgb[1], rgb[2], brightness)

    def update(self):
        pass

    def turn_off(self, **kwargs):
        log.info(f'{self._name}: turn_off')
        self.off()

    def on(self):
        self._light.on()
        self.update()

    def off(self):
        self._light.off()
        self.update()


def _test():
    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    broker_url = '192.168.1.129'
    mac = '7c:b9:4c:57:6e:1f'
    broker_password = 'passwd'
    broker_username = 'user'
    bulb_name = 'name'
    config = None

    light = TechLifeLightEntity(config, broker_url, broker_username, broker_password, mac, bulb_name)
    hs = color_util.color_RGB_to_hs(255, 255, 43)
    print(light.turn_on(hs_color=hs, brightness=10))
    # time.sleep(1)
    print(light.is_on)
    time.sleep(1)
    light.turn_off()
    time.sleep(1)
    print(light.is_on)

    while True:
        time.sleep(1)


if __name__ == '__main__':
    _test()
