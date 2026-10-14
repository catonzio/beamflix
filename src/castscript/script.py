import shutil
import subprocess
import sys
import time

from ppadb.client import Client as AdbClient

from castscript.justwatch import search

# Chromecast con Google TV (Impostazioni > Sistema > Opzioni sviluppatore > Debug wireless)
CHROMECAST_IP = "192.168.1.14"
# Porta della schermata principale di Debug wireless: usata solo se la scoperta
# automatica via mDNS non la trova (cambia a ogni riavvio del debug wireless)
CHROMECAST_PORT = 39667

ADB_HOST = "127.0.0.1"
ADB_PORT = 5037

# Piattaforme JustWatch (clearName) -> app Android TV, in ordine di preferenza
PROVIDERS = {
    "Netflix": "com.netflix.ninja",
    "Disney Plus": "com.disney.disneyplus",
    "Amazon Prime Video": "com.amazon.amazonvideo.livingroom",
    "Now TV": "com.nowtv.it",
}

ADB = shutil.which("adb") or ""


def adb(*args: str, timeout: float = 15) -> str:
    # ppadb non supporta pair e mdns: per connessione e accoppiamento usiamo la CLI
    try:
        r = subprocess.run(
            [ADB, *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return ""
    return (r.stdout + r.stderr).strip()


def start_adb_server() -> None:
    if not ADB:
        sys.exit("adb non trovato nel PATH: installa le Android platform-tools")
    # Niente capture_output: il server adb resta in background e, ereditando le
    # pipe, terrebbe bloccato subprocess.run in attesa della loro chiusura
    subprocess.run(
        [ADB, "start-server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def mdns_port(service: str) -> int | None:
    # Righe del tipo: adb-XXXX  _adb-tls-connect._tcp  192.168.1.14:39667
    for line in adb("mdns", "services").splitlines():
        parts = line.split()
        if (
            len(parts) == 3
            and parts[1].startswith(service)
            and parts[2].startswith(f"{CHROMECAST_IP}:")
        ):
            return int(parts[2].rsplit(":", 1)[1])
    return None


def try_connect(port: int) -> str | None:
    serial = f"{CHROMECAST_IP}:{port}"
    adb("connect", serial, timeout=10)
    if adb("-s", serial, "get-state", timeout=5) == "device":
        return serial
    # Un connect fallito lascia un trasporto "offline" che farebbe rispondere
    # "already connected" al tentativo successivo: lo rimuoviamo
    adb("disconnect", serial, timeout=5)
    return None


def pair() -> None:
    print(
        "Il computer non è accoppiato con la TV.\n"
        "Sulla TV vai in Impostazioni > Sistema > Opzioni sviluppatore > "
        "Debug wireless > Accoppia dispositivo con codice di accoppiamento."
    )
    print("In attesa della finestra di accoppiamento...", end="", flush=True)
    port = None
    for _ in range(30):
        port = mdns_port("_adb-tls-pairing")
        if port:
            break
        print(".", end="", flush=True)
        time.sleep(2)
    print()

    hint = f" [{port}]" if port else ""
    answer = input(f"Porta di accoppiamento mostrata sulla TV{hint}: ").strip()
    if answer:
        port = int(answer)
    if not port:
        sys.exit("Porta di accoppiamento mancante")

    code = input("Codice di accoppiamento a 6 cifre: ").strip()
    out = adb("pair", f"{CHROMECAST_IP}:{port}", code, timeout=30)
    print(out)
    if "Successfully paired" not in out:
        sys.exit("Accoppiamento non riuscito: riapri la finestra sulla TV e riprova")


def connect():
    start_adb_server()

    port = mdns_port("_adb-tls-connect") or CHROMECAST_PORT
    print(f"Connessione a {CHROMECAST_IP}:{port}...")
    serial = try_connect(port)

    # Se il connect fallisce con il debug wireless attivo, il computer non è accoppiato
    if serial is None:
        pair()
        port = mdns_port("_adb-tls-connect") or CHROMECAST_PORT
        serial = try_connect(port)
        if serial is None:
            sys.exit(
                f"Impossibile connettersi a {CHROMECAST_IP}:{port}: controlla la "
                "porta nella schermata principale di Debug wireless"
            )

    print(f"Connesso a {serial}")
    device = AdbClient(host=ADB_HOST, port=ADB_PORT).device(serial)
    if device is None:
        sys.exit("Dispositivo non trovato dopo la connessione")
    return device


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Uso: castscript <titolo di una serie o di un film>")
    query = " ".join(sys.argv[1:])

    title = search(query)
    if title is None:
        sys.exit(f"Nessun risultato per '{query}'")
    print(f"Trovato: {title.name} ({title.year})")

    links = {o.provider: o.deeplink for o in title.offers}
    provider = next((p for p in PROVIDERS if p in links), None)
    if provider is None:
        sys.exit(f"Non disponibile sulle tue app (offerte: {', '.join(links) or 'nessuna'})")
    package, deeplink = PROVIDERS[provider], links[provider]
    # Il link NOW apre la scheda (action PDP): con PLAY parte l'episodio del link
    deeplink = deeplink.replace("%22action%22%3A%22PDP%22", "%22action%22%3A%22PLAY%22")
    print(f"Apro su {provider}: {deeplink}")

    device = connect()

    # 1. Sveglia il Chromecast (e accende la TV tramite HDMI-CEC)
    device.shell("input keyevent KEYCODE_WAKEUP")

    # 2. Chiude l'app: se è già aperta riporta in primo piano la schermata
    # attuale e ignora il link
    device.shell(f"am force-stop {package}")

    # 3. Avvia il deep link di JustWatch (URI intent:// con pacchetto ed extra già
    # inclusi; per Netflix S.source=30 salta la scelta del profilo)
    print(device.shell(f"am start '{deeplink}'").strip())


if __name__ == "__main__":
    main()
