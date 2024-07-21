import os
import random
import time
from typing import Callable
from unicodedata import name

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant.components.light import (ATTR_WHITE, COLOR_MODE_BRIGHTNESS, COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS,
                                            COLOR_MODE_RGB,
                                            COLOR_MODE_RGBW,
                                            COLOR_MODE_WHITE, SUPPORT_BRIGHTNESS,
                                            ATTR_BRIGHTNESS,
                                            ATTR_HS_COLOR,
                                            ATTR_RGB_COLOR,
                                            SUPPORT_COLOR,
                                            PLATFORM_SCHEMA,
                                            LightEntity)

from homeassistant.const import (CONF_NAME)
import homeassistant.util.color as color_util

try:
    from .techlife_bulb import TechLifeBulp
except:
    from techlife_pro.techlife_bulb import TechLifeBulp

_LOGGER = logging.getLogger("techlife_pro")

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
            self._name = 'light_{}'.format(bulb_mac)

        self._light = TechLifeBulp(broker_url, broker_username, broker_password, bulb_mac, self._name)

        try:
            res = self._light.connect()
        except Exception as e:
            _LOGGER.info(e)

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
        if self._light.state_type == self._light.STATE_TYPE_RGB:
            return 'hs'
        elif self._light.state_type == self._light.STATE_TYPE_WHITE:
            return 'brightness'
        else:
            return 'onoff'

    # @property
    # def supported_color_modes(self):
    #     if self._light.state_type == 'rgb':
    #         return ["hs", "brightness"]
    #     elif self._light.state_type == 'w':
    #         return ["brightness"]
    #     else:
    #         return ['onoff']
    @property
    def brightness(self) -> int:
        if not self._light.state_is_available:
            _LOGGER.warning("light not available, cant get brightness")
            return 0
        else:
            return self._light.get_brightness()

    @property
    def assumed_state(self):
        return False

    @property
    def hs_color(self):
        _LOGGER.info('hs_color')
        if not self._light.state_is_available:
            _LOGGER.warning("light not available, cant get color")
            return None
        else:
            rgb = self._light.state_rgb
            return color_util.color_RGB_to_hs(rgb[0], rgb[1], rgb[2])

    def turn_on(self, **kwargs):
        _LOGGER.info('kwargs: {}'.format(kwargs))
        if not self.is_on:
            self.on()

        white_mode = not self._light.is_color_mode()

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            brightness = self.brightness

        _LOGGER.info(f'brightness {brightness}')

        if ATTR_HS_COLOR in kwargs:
            color = kwargs[ATTR_HS_COLOR]
            white_mode = False
        else:
            color = self.hs_color

        if ATTR_WHITE in kwargs:
            _LOGGER.info('use white mode')
            brightness = kwargs[ATTR_WHITE]
            white_mode = True

        _LOGGER.info('hs_color: {}'.format(self.hs_color))
        _LOGGER.info('rgb_color: {}'.format(self.rgb_color))
        _LOGGER.info('color: {}'.format(color))
        _LOGGER.info('brightness: {}'.format(brightness))

        rgb = color_util.color_hs_to_RGB(color[0], color[1])

        if white_mode:
            self._light.white(brightness)
        else:
            self._light.color(rgb[0], rgb[1], rgb[2], brightness)

    def update(self):
        pass

    def turn_off(self, **kwargs):
        self.off()

    def on(self):
        self._light.on()
        self.update()

    def off(self):
        self._light.off()
        self.update()


if __name__ == '__main__':
    broker_url = '192.168.1.129'
    mac = '7c:b9:4c:57:6e:1f'
    broker_password = 'passwd'
    broker_username = 'user'
    config = None

    light = TechLifeLightEntity(config, broker_url, broker_username, broker_password, mac, name)
    hs = color_util.color_RGB_to_hs(255, 255, 43)
    _LOGGER.info(light.turn_on(hs_color=hs, brightness=10))
    # time.sleep(1)
    _LOGGER.info(light.is_on)
    time.sleep(1)
    light.turn_off()
    time.sleep(1)
    _LOGGER.info(light.is_on)

    while True:
        time.sleep(1)
