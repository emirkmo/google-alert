import pychromecast
import logging
import orjson
from uuid import UUID
from pathlib import Path
import urllib.parse

from pychromecast import Chromecast
from pychromecast.error import RequestTimeout, RequestFailed

CACHE_PATH = Path(__file__).parent / ".local_chromecasts.json"


def discover_friendly_names() -> dict[str, UUID]:
    """Discover the friendly name and UUID of all chromecast on the network"""

    chromecasts, browser = pychromecast.get_chromecasts(tries=2)

    devices: dict[str, UUID] = {}
    for cc in chromecasts:
        if not cc.cast_info.friendly_name:
            logging.debug("Found chromecast with no friendly name, skipping.\n%s", cc)
            continue
        devices[cc.cast_info.friendly_name] = cc.cast_info.uuid

    if not devices:
        raise ValueError("Did not find any chrome cast devices with a friendly name!")

    browser.stop_discovery()

    return devices


def cache_friendly_names(devices: dict[str, UUID]) -> Path:
    """Cache friendly names and store in a local cache json file"""
    save_path = CACHE_PATH

    devices_array_json = [{"name": n, "uuid": u} for n, u in devices.items()]

    save_path.write_bytes(orjson.dumps(devices_array_json))

    return save_path.resolve()


def read_cached_friendly_names_or_none(
    path: Path = CACHE_PATH,
) -> dict[str, UUID] | None:
    """Cache friendly names and store in a local cache json file"""

    if not path.is_file():
        return None

    devices_bytes = path.read_bytes()
    if not devices_bytes:
        return None

    string_devices_list = orjson.loads(devices_bytes)
    devices = {}
    for pair in string_devices_list:
        devices[pair["name"]] = UUID(pair["uuid"])

    if not devices:
        return None
    return devices


def cast_message(message: str, cast: Chromecast, timeout: int = 30) -> None:
    """Broadcast a voice message to the given chromecast using google translate for the mp3 generation
    Failed or timed out requests can raise RequestFailed or RequestTimeout"""

    cast.wait(timeout)
    logging.debug(cast.cast_info)
    mc = cast.media_controller
    encoded = urllib.parse.quote(message)
    mc.play_media(
        f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={encoded}",
        "audio/mp3",
    )
    mc.block_until_active(timeout)


def safely_cast_message_on_all_chromecasts(msg: str, chromecasts: list[Chromecast]):
    """By safely we mean we try all available chromecasts and only raise any errors
    after we've tried them all."""
    errors = []
    for cast in chromecasts:
        try:
            cast_message(message=msg, cast=cast)
        except (RequestFailed, RequestTimeout) as err:
            logging.error(
                "Skipped casting to device due to timeout or failure, trying other devices"
            )
            logging.error(err)
            errors.append(err)
    if errors:
        # Exception groups require python >= 3.11
        raise ExceptionGroup("Errors casting to one or more devices", errors)


def get_device_uuids() -> dict[str, UUID]:
    """Use cache if possible"""
    devices = read_cached_friendly_names_or_none()
    if devices is None:
        devices = discover_friendly_names()
        cache_friendly_names(devices)
    return devices


def discover_devices_cast_message(msg: str, discovery_timeout: int = 30):
    """Discover chromecasts with a friendly name and cast the message on all of them using a voice service"""

    devices = get_device_uuids()
    uuids = list(devices.values())

    logging.info(
        "discovering following friendly names based on their uuids: %s",
        list(devices.keys()),
    )
    chromecasts, browser = pychromecast.get_listed_chromecasts(
        uuids=uuids, discovery_timeout=discovery_timeout
    )

    logging.info("casting msg to all devices")
    try:
        safely_cast_message_on_all_chromecasts(msg, chromecasts)
    finally:
        browser.stop_discovery()

if __name__ == "__main__":
    discover_devices_cast_message("HELLO FAMILY, WHERE ARE YOU?")
