"""Client usbmux minimal : ouvre un tunnel TCP vers un port de l'iPad, par le cable USB.

Sous Windows, le service Apple (fourni par iTunes) ecoute sur 127.0.0.1:27015.
"""
import plistlib
import socket
import struct

USBMUXD_ADDR = ("127.0.0.1", 27015)
_tag = 0


def _send(sock, payload: dict):
    global _tag
    _tag += 1
    data = plistlib.dumps(payload)
    # longueur totale, version 1, type 8 (plist), tag
    sock.sendall(struct.pack("<IIII", 16 + len(data), 1, 8, _tag) + data)


def _recv(sock) -> dict:
    header = _recv_exact(sock, 16)
    length, _version, _type, _tag_r = struct.unpack("<IIII", header)
    return plistlib.loads(_recv_exact(sock, length - 16))


def _recv_exact(sock, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("usbmux : connexion fermee")
        buf += chunk
    return bytes(buf)


def _connect_daemon():
    sock = socket.create_connection(USBMUXD_ADDR, timeout=5)
    return sock


def _base(msg_type: str) -> dict:
    return {"MessageType": msg_type, "ClientVersionString": "ipad-tablette",
            "ProgName": "ipad-tablette"}


def list_devices() -> list:
    """Renvoie la liste des appareils Apple branches en USB."""
    sock = _connect_daemon()
    try:
        _send(sock, _base("ListDevices"))
        rep = _recv(sock)
    finally:
        sock.close()
    return [d for d in rep.get("DeviceList", [])
            if d.get("Properties", {}).get("ConnectionType") == "USB"]


def connect(device_id: int, port: int) -> socket.socket:
    """Ouvre un tunnel vers le port TCP `port` de l'iPad. Renvoie un socket brut."""
    sock = _connect_daemon()
    msg = _base("Connect")
    msg["DeviceID"] = device_id
    msg["PortNumber"] = ((port & 0xFF) << 8) | (port >> 8)  # ordre reseau
    _send(sock, msg)
    rep = _recv(sock)
    if rep.get("Number", -1) != 0:
        sock.close()
        raise ConnectionRefusedError(f"usbmux : connexion refusee (code {rep.get('Number')})")
    sock.settimeout(None)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


if __name__ == "__main__":
    for d in list_devices():
        p = d["Properties"]
        print(d["DeviceID"], p.get("ProductID"), p.get("SerialNumber"), p.get("ConnectionType"))
