"""
list_chromecasts.py

Discovers Chromecast devices on your LAN using zeroconf and lists their friendly names, UUIDs, and IP addresses.
"""

import pychromecast
from zeroconf import Zeroconf

def list_chromecasts():
    # Create a Zeroconf instance
    zeroconf = Zeroconf()
    try:
        # Discover all Chromecasts on the network (this can take a few seconds)
        chromecasts, browser = pychromecast.get_chromecasts(zzc=zeroconf)

        if not chromecasts:
            print("No Chromecast devices found.")
            return

        print(f"Found {len(chromecasts)} device(s):\n")
        for cc in chromecasts:
            # Make sure we've resolved the details
            cc.wait()
            print(f"Name:    {cc.device.friendly_name}")
            print(f"UUID:    {cc.device.uuid}")
            print(f"Model:   {cc.device.model_name}")
            print(f"Host:    {cc.host}")
            print(f"Port:    {cc.port}")
            print("-" * 40)

    finally:
        # Tear down discovery and zeroconf
        browser.stop_discovery()
        zeroconf.close()

if __name__ == "__main__":
    list_chromecasts()

