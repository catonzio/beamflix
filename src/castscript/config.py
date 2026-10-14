"""User settings: Chromecast address, JustWatch catalog and installed apps."""

# Chromecast with Google TV (Settings > System > Developer options > Wireless debugging)
CHROMECAST_IP = "192.168.1.14"
# Port shown on the main Wireless debugging screen: used only when mDNS discovery
# cannot find it (it changes every time wireless debugging is restarted)
CHROMECAST_PORT = 39667

# Local adb server
ADB_HOST = "127.0.0.1"
ADB_PORT = 5037

# JustWatch catalog to search
JUSTWATCH_COUNTRY = "IT"
JUSTWATCH_LANGUAGE = "it"

# JustWatch providers (clearName) -> Android TV app package, in order of preference
PROVIDERS = {
    "Netflix": "com.netflix.ninja",
    "Disney Plus": "com.disney.disneyplus",
    "Amazon Prime Video": "com.amazon.amazonvideo.livingroom",
    "Now TV": "com.nowtv.it",
}
