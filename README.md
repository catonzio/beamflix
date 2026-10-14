# castscript

Play a movie or series on a Chromecast with Google TV straight from the terminal.

castscript searches the title on [JustWatch](https://www.justwatch.com), picks the
first streaming app you have that includes it, connects to the Chromecast over
wireless adb and opens the app's deep link, so playback starts on the TV.

## Quick run

```sh
uv run castscript stranger things
```

```text
Found: Stranger Things (2016)
Opening on Netflix: intent://...
Connecting to the Chromecast...
Connected to 192.168.1.14:39667
Starting: Intent { ... }
```

The first time you run it, castscript asks you to pair with the TV (see
[First pairing](#first-pairing)).

## Setup

### Requirements

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- `adb` from the Android platform-tools, in your `PATH`:

  ```sh
  brew install android-platform-tools   # macOS
  ```

- A Chromecast with Google TV on the same network as the computer

The Python dependencies (only
[pure-python-adb](https://github.com/Swind/pure-python-adb)) are installed by
uv on the first run. To install them yourself, run `uv sync`.

### Enable wireless debugging on the Chromecast

1. **Settings > System > About**: select **Android TV OS build** 7 times to
   unlock the developer options.
2. **Settings > System > Developer options**: turn on **Wireless debugging**.
3. Write down the IP address and port shown on the Wireless debugging screen.

### Configure

Edit [src/castscript/config.py](src/castscript/config.py):

| Setting | Description |
| --- | --- |
| `CHROMECAST_IP` | IP address of the Chromecast (set a static DHCP lease on your router) |
| `CHROMECAST_PORT` | Wireless debugging port. Used only if mDNS discovery fails, because the port changes every time wireless debugging restarts |
| `JUSTWATCH_COUNTRY`, `JUSTWATCH_LANGUAGE` | JustWatch catalog to search (default: Italy) |
| `PROVIDERS` | JustWatch provider name → Android TV app package, in order of preference. Keep only the apps you have installed and subscribed to |

Supported by default: Netflix, Disney+, Amazon Prime Video, NOW.

### First pairing

If the connection is refused, castscript assumes the computer is not paired yet
and walks you through it:

1. On the TV, open **Wireless debugging > Pair device with pairing code**.
2. castscript detects the pairing port via mDNS. Press Enter to accept it, or
   type the port shown on the TV.
3. Enter the 6-digit code shown on the TV.

Pairing is stored by adb, so you only need to do this once.

### Install as a command (optional)

```sh
uv tool install .
castscript the bear
```

## How it works

1. **Search** ([justwatch.py](src/castscript/justwatch.py)): queries the
   JustWatch GraphQL API for the most popular match and its Android TV deep
   links. Only subscription, free and ad-supported offers are kept.
2. **Choose** ([providers.py](src/castscript/providers.py)): takes the first
   provider in `PROVIDERS` that has an offer. NOW links are changed from "open
   the title page" to "play".
3. **Connect** ([chromecast.py](src/castscript/chromecast.py),
   [adb.py](src/castscript/adb.py), [pairing.py](src/castscript/pairing.py)):
   starts the adb server, finds the port via mDNS, connects, and pairs if needed.
4. **Launch**: wakes the Chromecast (which also turns on the TV through
   HDMI-CEC), force-stops the app so it doesn't just resume its last screen,
   then runs `am start` with the deep link.

## Limitations

- The JustWatch API is public but unofficial, so it may change without notice.
- Only the first search result is used. If you get the wrong title, add the
  year or a more specific title.
