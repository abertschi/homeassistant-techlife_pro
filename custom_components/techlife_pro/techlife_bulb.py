import logging
import paho.mqtt.client as mqtt
import time
import binascii
import traceback

log = logging.getLogger("techlife_pro.bulb")
log_mqtt = logging.getLogger("techlife_pro.mqtt")

MIN_COLOR_VAL = 16


class TechLifeBulp():
    STATE_TYPE_RGB = "rgb"
    STATE_TYPE_WHITE = 'w'

    def __init__(self,
                 broker_url,
                 broker_username,
                 broker_password,
                 bulb_mac,
                 bulb_name):
        self.broker_url = broker_url
        self.broker_username = broker_username
        self.broker_password = broker_password
        self.bulb_name = bulb_name
        self.bulb_mac = bulb_mac

        self.mqtt_client = None

        self.state_is_available: bool = True
        self.state_power: bool = False
        self.state_rgb = (255, 255, 255)
        self.state_color_brightness = 255
        self.state_white_brightness = 255
        self.state_type: str = self.STATE_TYPE_RGB

        log.info(f"creating bulb with url={broker_url},"
                 f" user={broker_username},"
                 f" mac={bulb_mac},"
                 f" name={bulb_name}")

    def is_color_mode(self):
        return self.state_type == self.STATE_TYPE_RGB

    def get_brightness(self):
        if self.state_type == self.STATE_TYPE_RGB:
            return self.state_color_brightness
        else:
            return self.state_white_brightness

    def set_brightness(self, val):
        if self.state_type == self.STATE_TYPE_RGB:
            r = self.state_rgb[0]
            g = self.state_rgb[1]
            b = self.state_rgb[2]
            return self.color(r, g, b, val)
        else:
            return self.white(val)

    def connect(self):
        id = f"clientid{self.bulb_mac}"
        self.mqtt_client = mqtt.Client(id)
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_log = self._on_log

        log.info(f"Connecting to broker {self.broker_url}"
                 f" with client id {id}")

        self.mqtt_client.username_pw_set(self.broker_username,
                                         password=self.broker_password)

        self.mqtt_client.connect(self.broker_url)
        self.mqtt_client.loop_start()
        return True

    def _on_connect(self, client, obj, flags, rc):
        if rc == 0:
            log_mqtt.debug("[mqtt:on_connect] connected ok")
            log.debug(f"mqtt connected {self.bulb_name}/{self.bulb_mac}")

            self.state_is_available = True
            dev_pub = f"dev_pub_{self.bulb_mac}"
            dev_sub = f"dev_sub_{self.bulb_mac}"

            log_mqtt.debug(f"mqtt subscribing to {dev_pub}")
            log_mqtt.debug(f"mqtt subscribing to {dev_sub}")

            client.subscribe(dev_pub)
            client.subscribe(dev_sub)
        else:
            log_mqtt.error(f"[on_connect] Bad connection. code={rc}")

    def _on_disconnect(self, client, userdata, rc):
        log_mqtt.info(f"[mqtt:on_disconnect] disconnecting reason {rc},"
                      f" client: {self.bulb_name}")

        self.state_is_available = False
        client.connected_flag = False
        client.disconnect_flag = True

    def _on_log(self, client, userdata, level, buff):
        log_mqtt.debug(f"[mqtt:on_log]: {buff}")

    def _on_message(self, client, userdata, message):
        try:
            msg = binascii.hexlify(message.payload)
            topic = message.topic
            log_mqtt.debug(f"[mqtt:on_message] Command received in topic {topic}: {msg}")

            # TODO: Do we need this?
            if ((topic == "dev_sub_%s" % self.bulb_mac) \
                    and message.payload[0] == 0xfc \
                    and message.payload[1] == 0xf0):
                response = bytearray.fromhex("110000000000003f0d000000014100ffffff1524f14d22")
                client.publish("dev_pub_%s" % self.bulb_mac, response)

        except Exception as e:
            log_mqtt.exception("error while receiving message", e)
            traceback.print_exc()

    def _send(self, cmd):
        command = self._calc_checksum(cmd)
        sub_topic = f"dev_sub_{self.bulb_mac}"
        self.mqtt_client.publish(sub_topic, command)

    def color(self, red, green, blue, alpha):
        """
        rgb alpha in [0, 255]
        """

        #
        # some playing around
        #
        _alpha = alpha
        if alpha == 0:
            pass
        elif alpha < 128:
            alpha = alpha + 12
        elif alpha < 164:
            alpha = int(alpha * 12)
        elif alpha < 192:
            alpha = int(alpha * 30)
        else:
            alpha = int(alpha / 255 * 10_000)

        r = int(red / 255 * alpha)
        g = int(green / 255 * alpha)
        b = int(blue / 255 * alpha)

        log.debug(f"{self.bulb_name} changing color:"
                  f" in:{red},{green},{blue},{_alpha}"
                  f" adj:{r},{g},{b},{alpha}")

        self.state_rgb = (red, green, blue)
        self.state_color_brightness = _alpha
        self.state_type = self.STATE_TYPE_RGB

        self._send(self._cmd_color(r, g, b, alpha))

    def _cmd_color(self, r, g, b, alpha):
        """
        rgb and alpha in range [0, 10_000]
        """
        payload = bytearray.fromhex("28 00 00 00 00 00 00 00 00 00 00 00 00 0f 00 29")

        #
        # bulb visual hacks
        #
        if r > 0:
            r = max(MIN_COLOR_VAL, r)
        if g > 0:
            g = max(MIN_COLOR_VAL, g)
        if b > 0:
            b = max(MIN_COLOR_VAL, b)

        alp = max(12, alpha)

        log.debug(f"{self.bulb_name} color: "
                  f" in:{r},{g},{b},{alpha}")

        payload[1] = r & 0xFF
        payload[2] = r >> 8
        payload[3] = g & 0xFF
        payload[4] = g >> 8
        payload[5] = b & 0xFF
        payload[6] = b >> 8
        payload[11] = alp & 0xFF
        return payload

    def white(self, brightness_256):
        assert 0 <= brightness_256 <= 255

        if brightness_256 < 128:
            value = max(12, brightness_256 * 4)
        else:
            value = int(brightness_256 / 256 * 10_000)

        log.debug(f"{self.bulb_name} white: "
                  f" in:{brightness_256}, adj:{value}")

        self.state_white_brightness = brightness_256
        self.state_type = self.STATE_TYPE_WHITE

        self._send(self._cmd_brightness(value))

    def on(self):
        self.state_power = True
        self._send(bytearray.fromhex(
            "fa 23 00 00 00 00 00 00 00 00 00 00 00 00 23 fb"))

    def off(self):
        self.state_power = False
        self._send(bytearray.fromhex(
            "fa 24 00 00 00 00 00 00 00 00 00 00 00 00 24 fb"))

    def _calc_checksum(self, stream):
        checksum = 0
        for i in range(1, 14):
            checksum = checksum ^ stream[i]
        stream[14] = checksum & 0xFF
        return bytearray(stream)

    def _cmd_brightness(self, value):
        assert 0 <= value <= 10000
        payload = bytearray.fromhex(
            "28 00 00 00 00 00 00 00 00 00 00 00 00 f0 00 29")
        payload[7] = value & 0xFF
        payload[8] = value >> 8
        return payload


def _test():
    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    broker_url = '192.168.1.129'
    mac = '7c:b9:4c:57:6e:1f'
    name = 'test'
    broker_password = 'passwd'
    broker_username = 'user'

    light = TechLifeBulp(broker_url, broker_username, broker_password, mac, name)
    try:
        res = light.connect()
    except Exception as e:
        print(e)

    light.on()
    i = 0

    red = 255
    green = 0
    blue = 255
    alpha = 1 / 10_000

    light.on()

    # light.white(12)
    i = 0
    while True:
        time.sleep(.1)
        i += 1
        print(i)

        light.color(red, green, blue, i)
        # r = (red + i) % 256
        # light.color(r, green, blue, alpha)
    # while True:
    #     time.sleep(0.01)
    #     i += 1
    #     light.color(red, green, blue, alpha + i/ 10_000)


if __name__ == '__main__':
    _test()
