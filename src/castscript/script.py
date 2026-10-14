from ppadb.client import Client as AdbClient

# Connessione al Chromecast tramite IP locale (porta ADB standard: 5555)
client = AdbClient(host="127.0.0.1", port=5037)
device = client.device("192.168.1.14:39667") # IP del Chromecast

# 1. Sveglia il Chromecast (e accende la TV tramite HDMI-CEC)
device.shell("input keyevent KEYCODE_WAKEUP")

# 2. Avvia direttamente Netflix sulla puntata/serie desiderata (usando i Deep Link ufficiali)
# Sostituisci l'ID con quello della serie che trovi nell'URL di Netflix
netflix_url = "https://netflix.com" 
device.shell(f"am start -a android.intent.action.VIEW -d {netflix_url}")

# 3. Aspetta il caricamento e simula la pressione del tasto Invio/Play se necessario
# device.shell("input keyevent KEYCODE_DPAD_CENTER")

