"""Device configuration model and GPIO function catalog."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# GPIO function type catalog
# ---------------------------------------------------------------------------

@dataclass
class GpioType:
    type_id: str
    label: str
    description: str
    category: str
    base_codes: list[int]       # Tasmota numeric codes for instance 1, 2, 3...
    mqtt_example: Optional[str] = None
    direction: str = "–"        # "BEMENET" | "KIMENET" | "–"


# ---------------------------------------------------------------------------
# Tasmota 15 GPIO function codes (new unified numbering, valid for ESP32 and ESP8266)
# Source: https://tasmota.github.io/docs/Components/
# ---------------------------------------------------------------------------

GPIO_FUNCTION_TYPES: list[GpioType] = [
    GpioType(
        "none", "— Nincs kiosztás —", "", "Általános",
        base_codes=[0], mqtt_example=None, direction="–",
    ),
    # --- Bemenet --------------------------------------------------------
    GpioType(
        "switch", "Bemeneti érzékelő",
        "PIR mozgásérzékelő, ajtó/ablak reed relé, vízszint érzékelő",
        "Bemenet",
        # Switch1-8 = 160-167 (pull-up);  Switch_n1-8 = 192-199 (no pull-up)
        base_codes=[160, 161, 162, 163, 164, 165, 166, 167,
                    192, 193, 194, 195, 196, 197, 198, 199],
        mqtt_example='{"Switch{n}": "ON"}',
        direction="BEMENET",
    ),
    GpioType(
        "button", "Nyomógomb (fizikai)",
        "Fizikai gomb, érintő – rövid/hosszú nyomásra különböző esemény",
        "Bemenet",
        # Button1-8 = 32-39; Button_n1-8 = 64-71; Button_i1-8 = 96-103; Button_in1-8 = 128-135
        # Extend to Button26 (=57) to cover all standard ESP32-DevKit board assignments
        base_codes=list(range(32, 58)) + list(range(64, 72)) + list(range(96, 104)) + list(range(128, 136)),
        mqtt_example='{"Button{n}": {"Action": "SINGLE"}}',
        direction="BEMENET",
    ),
    GpioType(
        "counter", "Impulzusszámláló",
        "Villanyóra, gázóra, vízóra impulzusbemenet",
        "Bemenet",
        # Counter1-4 = 352-355;  Counter_n1-4 = 384-387
        base_codes=[352, 353, 354, 355, 384, 385, 386, 387],
        mqtt_example='{"Counter{n}": 42}',
        direction="BEMENET",
    ),
    # --- Kimenet --------------------------------------------------------
    GpioType(
        "relay", "Relé / Kapcsoló kimenet",
        "Lámpa, motor, szivattyú ki-/bekapcsolása",
        "Kimenet",
        # Relay1-8 = 224-231;  Relay_i1-8 = 256-263 (inverted)
        base_codes=[224, 225, 226, 227, 228, 229, 230, 231,
                    256, 257, 258, 259, 260, 261, 262, 263],
        mqtt_example="cmnd/{topic}/POWER{n} ON|OFF",
        direction="KIMENET",
    ),
    GpioType(
        "pwm", "PWM fényerő szabályozás",
        "LED dimmer, ventilátorsebesség szabályozás (0–1023)",
        "Kimenet",
        # PWM1-5 = 416-420;  PWM_i1-5 = 448-452 (inverted)
        base_codes=[416, 417, 418, 419, 420, 448, 449, 450, 451, 452],
        mqtt_example="cmnd/{topic}/Dimmer{n} 75",
        direction="KIMENET",
    ),
    GpioType(
        "led", "Beépített státusz LED",
        "Eszköz aktivitás és státusz jelző LED",
        "Kimenet",
        # Led1-4 = 288-291;  Led_i1-4 = 320-323 (inverted);  LedLink = 544
        base_codes=[288, 289, 290, 291, 320, 321, 322, 323, 544, 576],
        mqtt_example=None,
        direction="KIMENET",
    ),
    # --- Szenzor --------------------------------------------------------
    GpioType(
        "dht22", "DHT22 / AM2301 – hőmérséklet + páratartalom",
        "Leggyakoribb kombinált szenzor, digitális protokoll",
        "Szenzor",
        # AM2301 = 1216
        base_codes=[1216],
        mqtt_example='{"AM2301": {"Temperature": 23.4, "Humidity": 61}}',
        direction="BEMENET",
    ),
    GpioType(
        "dht11", "DHT11 – hőmérséklet + páratartalom",
        "Olcsóbb, kevésbé pontos változat",
        "Szenzor",
        # DHT11 = 1184
        base_codes=[1184],
        mqtt_example='{"DHT11": {"Temperature": 22.0, "Humidity": 55}}',
        direction="BEMENET",
    ),
    GpioType(
        "ds18b20", "DS18B20 – hőmérséklet szenzor (1-Wire)",
        "Digitális hőmérő, vízálló változat is elérhető",
        "Szenzor",
        # DS18x20 = 1312
        base_codes=[1312],
        mqtt_example='{"DS18B20": {"Temperature": 23.4}}',
        direction="BEMENET",
    ),
    GpioType(
        "bme280", "BME280 – hőmérséklet + pára + nyomás (I2C)",
        "Precíziós légköri szenzor, I2C buszon (SCL+SDA szükséges)",
        "Szenzor",
        base_codes=[],   # configured via I2C, no direct GPIO code
        mqtt_example='{"BME280": {"Temperature": 23.4, "Humidity": 61, "Pressure": 1013.7}}',
        direction="BEMENET",
    ),
    # --- I2C busz -------------------------------------------------------
    GpioType(
        "i2c_scl", "I2C busz – SCL (órajel)",
        "BME280, SHT30, OLED kijelző és más I2C eszközökhöz (párban SDA-val)",
        "I2C",
        # I2C SCL1 = 608
        base_codes=[608],
        mqtt_example=None,
        direction="–",
    ),
    GpioType(
        "i2c_sda", "I2C busz – SDA (adat)",
        "BME280, SHT30, OLED kijelző és más I2C eszközökhöz (párban SCL-lel)",
        "I2C",
        # I2C SDA1 = 640
        base_codes=[640],
        mqtt_example=None,
        direction="–",
    ),
]

# Lookup by type_id
GPIO_TYPE_BY_ID: dict[str, GpioType] = {gt.type_id: gt for gt in GPIO_FUNCTION_TYPES}

# Select widget options: (label, value) grouped by category separator
def gpio_select_options() -> list[tuple[str, str]]:
    """Return (display_label, type_id) list suitable for a Textual Select widget."""
    result: list[tuple[str, str]] = []
    current_cat = ""
    for gt in GPIO_FUNCTION_TYPES:
        if gt.category != current_cat:
            current_cat = gt.category
            if gt.type_id != "none":
                result.append((f"── {current_cat} ──", f"__sep_{current_cat}"))
        result.append((gt.label, gt.type_id))
    return result


def assign_tasmota_codes(gpio_assignments: dict[int, str]) -> dict[int, int]:
    """
    Convert user-facing type assignments to Tasmota numeric GPIO codes.

    gpio_assignments: {gpio_number: type_id}  e.g. {4: "switch", 5: "switch", 14: "relay"}
    Returns:          {gpio_number: tasmota_code}  e.g. {4: 160, 5: 161, 14: 224}

    Same type_id gets auto-incremented codes in ascending GPIO order.
    """
    # Count per type, ordered by GPIO number
    type_counters: dict[str, int] = {}
    result: dict[int, int] = {}
    for gpio_num in sorted(gpio_assignments.keys()):
        type_id = gpio_assignments[gpio_num]
        gt = GPIO_TYPE_BY_ID.get(type_id)
        if gt is None or not gt.base_codes:
            result[gpio_num] = 0
            continue
        idx = type_counters.get(type_id, 0)
        code = gt.base_codes[idx] if idx < len(gt.base_codes) else gt.base_codes[-1]
        result[gpio_num] = code
        type_counters[type_id] = idx + 1
    return result


def instance_label(type_id: str, instance: int) -> str:
    """Return Tasmota instance name for display, e.g. 'Switch2', 'Relay1'."""
    names = {
        "switch": "Switch",
        "button": "Button",
        "counter": "Counter",
        "relay": "Relay",
        "pwm": "PWM",
        "led": "Led",
        "i2c_scl": "I2C SCL",
        "i2c_sda": "I2C SDA",
        "dht22": "AM2301",
        "dht11": "DHT11",
        "ds18b20": "DS18x20",
        "bme280": "BME280",
    }
    base = names.get(type_id, type_id)
    if type_id in ("dht22", "dht11", "ds18b20", "bme280", "i2c_scl", "i2c_sda", "none"):
        return base
    return f"{base}{instance}"


def compute_gpio_instances(gpio_assignments: dict[int, str]) -> dict[int, str]:
    """Return {gpio_num: instance_label} e.g. {4: 'Switch1', 5: 'Switch2', 14: 'Relay1'}."""
    type_counters: dict[str, int] = {}
    result: dict[int, str] = {}
    for gpio_num in sorted(gpio_assignments.keys()):
        type_id = gpio_assignments[gpio_num]
        idx = type_counters.get(type_id, 0) + 1
        type_counters[type_id] = idx
        result[gpio_num] = instance_label(type_id, idx)
    return result


# ---------------------------------------------------------------------------
# Pydantic config models
# ---------------------------------------------------------------------------

class WifiConfig(BaseModel):
    ssid1: str = ""
    password1: str = ""
    ssid2: str = ""
    password2: str = ""


class MqttConfig(BaseModel):
    host: str = "broker.emqx.io"
    port: int = 1883
    user: str = ""
    password: str = ""
    topic: str = ""
    full_topic: str = "%prefix%/%topic%/"


class DeviceConfig(BaseModel):
    device_name: str = ""
    topic: str = ""
    # Group hierarchy for MQTT topic: {region_id}/{user_id}/%prefix%/%topic%/
    region_id: str = ""
    user_id: str = ""
    wifi: WifiConfig = Field(default_factory=WifiConfig)
    mqtt: MqttConfig = Field(default_factory=MqttConfig)
    tele_period: int = 300
    # Board/module name (e.g. "Wemos D1 Mini"). Legacy profiles may contain an
    # int Tasmota module ID – the validator converts that to a board name.
    module_type: str = "Wemos D1 Mini"
    # gpio: {gpio_number_str: type_id}  e.g. {"4": "switch", "14": "relay"}
    gpio: dict[str, str] = Field(default_factory=dict)

    @field_validator("module_type", mode="before")
    @classmethod
    def _coerce_module_type(cls, v: Union[int, str]) -> str:
        """Convert legacy int module IDs to board name strings."""
        if isinstance(v, int):
            from tasmota_manager.board_layouts import TASMOTA_MODULE_TO_BOARD
            return TASMOTA_MODULE_TO_BOARD.get(v, "Wemos D1 Mini")
        return str(v) if v else "Wemos D1 Mini"

    def gpio_int_keys(self) -> dict[int, str]:
        return {int(k): v for k, v in self.gpio.items()}

    def to_tasmota_commands(self) -> list[tuple[str, str]]:
        """Return list of (command, value) tuples for serial / MQTT sending."""
        cmds: list[tuple[str, str]] = []

        # WiFi
        if self.wifi.ssid1:
            cmds.append(("Ssid1", self.wifi.ssid1))
        if self.wifi.password1:
            cmds.append(("Password1", self.wifi.password1))
        if self.wifi.ssid2:
            cmds.append(("Ssid2", self.wifi.ssid2))
        if self.wifi.password2:
            cmds.append(("Password2", self.wifi.password2))

        # MQTT
        if self.mqtt.host:
            cmds.append(("MqttHost", self.mqtt.host))
        cmds.append(("MqttPort", str(self.mqtt.port)))
        if self.mqtt.user:
            cmds.append(("MqttUser", self.mqtt.user))
            cmds.append(("MqttPassword", self.mqtt.password))
        else:
            cmds.append(("MqttUser", "0"))
            cmds.append(("MqttPassword", "0"))
        if self.mqtt.topic:
            cmds.append(("Topic", self.mqtt.topic))
        cmds.append(("FullTopic", self.mqtt.full_topic))

        # General
        from tasmota_manager.board_layouts import BOARD_TO_TASMOTA_MODULE
        tasmota_module = BOARD_TO_TASMOTA_MODULE.get(self.module_type, 18)
        cmds.append(("Module", str(tasmota_module)))
        cmds.append(("TelePeriod", str(self.tele_period)))

        # GPIO
        gpio_codes = assign_tasmota_codes(self.gpio_int_keys())
        for gpio_num in sorted(gpio_codes.keys()):
            code = gpio_codes[gpio_num]
            cmds.append((f"GPIO{gpio_num}", str(code)))

        cmds.append(("Restart", "1"))
        return cmds

    def to_tasmota_command_strings(self) -> list[str]:
        return [f"{cmd} {val}" for cmd, val in self.to_tasmota_commands()]

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "DeviceConfig":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


PROFILES_DIR = Path(__file__).parent.parent / "profiles"


def list_profiles() -> list[Path]:
    PROFILES_DIR.mkdir(exist_ok=True)
    return sorted(PROFILES_DIR.glob("*.json"))


def load_profile(name: str) -> DeviceConfig:
    return DeviceConfig.load(PROFILES_DIR / f"{name}.json")


def save_profile(config: DeviceConfig, name: str) -> None:
    PROFILES_DIR.mkdir(exist_ok=True)
    config.save(PROFILES_DIR / f"{name}.json")
