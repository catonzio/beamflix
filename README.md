# beamflix

Play a movie or series on a Chromecast with Google TV straight from the terminal.

beamflix searches the title on [JustWatch](https://www.justwatch.com), picks the
first streaming app you have that includes it, connects to the Chromecast over
wireless adb and opens the app's deep link, so playback starts on the TV.

## Quick run

```sh
uv run beamflix stranger things
```

```text
Found: Stranger Things (2016)
Opening on Netflix: intent://...
Connecting to the Chromecast...
Connected to 192.168.1.14:39667
Starting: Intent { ... }
```

The first time, pair with the TV by running `uv run beamflix connect` (see
[First pairing](#first-pairing)).

### Remote control

```sh
uv run beamflix toggle
```

| Command | Effect |
| --- | --- |
| `connect` | Connect to the Chromecast, pairing first if needed |
| `play` | Resume playback |
| `pause` | Pause playback |
| `toggle` | Play if paused, pause if playing |
| `startup` | Wake the Chromecast (and turn on the TV through HDMI-CEC) |
| `shutdown` | Put the Chromecast to sleep (and turn off the TV through HDMI-CEC) |
| `clean` | Close every installed app, clear all app caches and go back to the home screen |
| `restart` | `clean`, then reboot the Chromecast |

> [!WARNING]
> Android turns wireless debugging off at every reboot (including `restart`).
> Enable it again on the TV before using beamflix. Pairing is kept, so you
> don't need to pair again.

A single word matching a command is always treated as a command, so a title
like "Play" can't be searched on its own.

## Setup

### Requirements

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- `adb` from the Android platform-tools, in your `PATH`:

  ```sh
  brew install android-platform-tools   # macOS
  ```

- A Chromecast with Google TV on the same network as the computer

There are no Python dependencies besides the standard library: everything on
the TV is done through the `adb` command.

### Enable wireless debugging on the Chromecast

1. **Settings > System > About**: select **Android TV OS build** 7 times to
   unlock the developer options.
2. **Settings > System > Developer options**: turn on **Wireless debugging**.
3. Write down the IP address and port shown on the Wireless debugging screen.

Wireless debugging turns off every time the Chromecast reboots: turn it back on
from the same screen.

### Configure

Edit [src/beamflix/config.py](src/beamflix/config.py):

| Setting | Description |
| --- | --- |
| `CHROMECAST_IP` | IP address of the Chromecast (set a static DHCP lease on your router) |
| `CHROMECAST_PORT` | Wireless debugging port. Used only if mDNS discovery fails, because the port changes every time wireless debugging restarts |
| `JUSTWATCH_COUNTRY`, `JUSTWATCH_LANGUAGE` | JustWatch catalog to search (default: Italy) |
| `PROVIDERS` | JustWatch provider name → Android TV app package, in order of preference. Keep only the apps you have installed and subscribed to |
| `PROFILES` | JustWatch provider name → profile to choose when the app asks "Who's watching?". Supported for Disney+ only; PIN-protected profiles are not supported |

Supported by default: Netflix, Disney+, Amazon Prime Video, NOW.

### First pairing

1. On the TV, open **Wireless debugging > Pair device with pairing code**.
2. Run `uv run beamflix connect`. If it can't connect, it starts pairing.
3. beamflix detects the pairing port via mDNS. Press Enter to accept it, or
   type the port shown on the TV.
4. Enter the 6-digit code shown on the TV.

The other commands also start pairing when the connection is refused, but
they can't tell an unpaired computer from disabled wireless debugging while
the pairing dialog is open: use `connect` for the first pairing.

Pairing is stored by adb, so you only need to do this once.

### Install as a command (optional)

```sh
uv tool install .
beamflix the bear
```

## How it works

1. **Search** ([justwatch.py](src/beamflix/justwatch.py)): queries the
   JustWatch GraphQL API for the most popular match and its Android TV deep
   links. Only subscription, free and ad-supported offers are kept.
2. **Choose** ([providers.py](src/beamflix/providers.py)): takes the first
   provider in `PROVIDERS` that has an offer. NOW links are changed from "open
   the title page" to "play".
3. **Connect** ([chromecast.py](src/beamflix/chromecast.py),
   [adb.py](src/beamflix/adb.py), [pairing.py](src/beamflix/pairing.py)):
   starts the adb server, finds the port via mDNS, connects, and pairs if needed.
   The server runs with macOS's mDNS (Bonjour) instead of adb's built-in one
   (Openscreen), which doesn't see the Chromecast; a server already running
   with Openscreen is restarted.
4. **Launch**: wakes the Chromecast (which also turns on the TV through
   HDMI-CEC), force-stops the app so it doesn't just resume its last screen,
   then runs `am start` with the deep link.
5. **Profile** ([profiles.py](src/beamflix/profiles.py)): if the app shows its
   profile picker, reads the screen with `uiautomator dump`, moves the focus to
   the profile set in `PROFILES` and selects it. Netflix doesn't need this,
   because its deep link already skips the picker.

## Limitations

- The JustWatch API is public but unofficial, so it may change without notice.
- Only the first search result is used. If you get the wrong title, add the
  year or a more specific title.
