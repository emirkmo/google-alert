#!/usr/bin/env python3
"""
chromecast_discovery_and_tts.py

Discover specified Chromecast/Google Home devices, print their info nicely,
and play a TTS message on them. Includes a --debug flag to introspect available attributes.
"""

import sys
import argparse
import urllib.parse
import pychromecast
from pychromecast.discovery import stop_discovery


def discover_casts(friendly_names, timeout=5):
    """
    Discover Chromecast devices matching any of the provided friendly names.

    Returns a tuple of (cast_list, browser_instance).
    """
    casts, browser = pychromecast.get_listed_chromecasts(
        friendly_names=friendly_names,
        discovery_timeout=timeout
    )
    return casts, browser


def print_cast_info(cast, debug=False):
    """
    Nicely print information about a single Chromecast device.
    If debug is True, also print all attributes of the CastInfo object.
    """
    info = cast.cast_info
    print(f"Name        : {info.friendly_name}")
    print(f"UUID        : {info.uuid}")
    print(f"Manufacturer: {info.manufacturer}")
    print(f"Model       : {info.model_name}")
    print(f"Type        : {info.cast_type}")
    print(f"Host:Port   : {info.host}:{info.port}")
    print("-" * 40)

    if debug:
        print("Available CastInfo attributes:")
        for attr in dir(info):
            if not attr.startswith('_'):
                print(f"  {attr}")
        print("-" * 40)


def play_tts_on_cast(cast, message):
    """
    Play a text-to-speech message on the specified Chromecast device.
    """
    cast.wait()
    encoded = urllib.parse.quote(message)
    tts_url = (
        "https://translate.google.com/translate_tts?"
        f"ie=UTF-8&tl=en&client=tw-ob&q={encoded}"
    )
    mc = cast.media_controller
    mc.play_media(tts_url, "audio/mp3")
    mc.block_until_active()


def main(args):
    # Discover devices
    print(f"Discovering devices {args.devices} (timeout={args.timeout}s)...")
    casts, browser = discover_casts(args.devices, args.timeout)

    try:
        if not casts:
            print("No matching devices found.")
            return 1

        print(f"Found {len(casts)} device(s):\n")
        for cast in casts:
            print_cast_info(cast, debug=args.debug)

        # Optionally test TTS playback
        if args.play and not args.debug:
            for cast in casts:
                name = cast.cast_info.friendly_name
                print(f"Playing TTS on {name}...")
                play_tts_on_cast(cast, args.message)
    finally:
        stop_discovery(browser)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discover and interact with Chromecast devices.")
    parser.add_argument(
        '-d', '--devices', nargs='+', default=["Kitchen Display 2", "Living Room speaker"],
        help="List of friendly names to discover"
    )
    parser.add_argument(
        '-t', '--timeout', type=int, default=30,
        help="Discovery timeout in seconds"
    )
    parser.add_argument(
        '-m', '--message', default="Temperature below 8 degrees",
        help="TTS message to play"
    )
    parser.add_argument(
        '-p', '--play', action='store_true',
        help="Actually play the TTS message"
    )
    parser.add_argument(
        '--debug', action='store_true',
        help="Print detailed attribute info for debugging"
    )
    args = parser.parse_args()

    sys.exit(main(args))

