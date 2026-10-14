import shutil
import subprocess
import sys
import time

from ppadb.client import Client as AdbClient

# Chromecast con Google TV (Impostazioni > Sistema > Opzioni sviluppatore > Debug wireless)
CHROMECAST_IP = "192.168.1.14"
# Porta della schermata principale di Debug wireless: usata solo se la scoperta
# automatica via mDNS non la trova (cambia a ogni riavvio del debug wireless)
CHROMECAST_PORT = 39667

ADB_HOST = "127.0.0.1"
ADB_PORT = 5037

# ID della serie (netflix.com/title/<ID>) o della puntata (netflix.com/watch/<ID>)
NETFLIX_URL = "https://www.netflix.com/title/81231974"
NETFLIX_PACKAGE = "com.netflix.ninja"  # app Netflix per Android TV

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
    device = connect()

    # 1. Sveglia il Chromecast (e accende la TV tramite HDMI-CEC)
    device.shell("input keyevent KEYCODE_WAKEUP")
    time.sleep(2)

    # 2. Apre Netflix direttamente sulla serie tramite deep link
    out = device.shell(
        f"am start -a android.intent.action.VIEW -d '{NETFLIX_URL}' -p {NETFLIX_PACKAGE}"
    )
    print(out.strip())

    # 3. Se serve, aspetta il caricamento e preme OK/Play
    # time.sleep(8)
    # device.shell("input keyevent KEYCODE_DPAD_CENTER")


if __name__ == "__main__":
    main()
