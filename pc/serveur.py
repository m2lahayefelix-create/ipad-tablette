"""iPad -> tablette graphique, par cable USB.

Envoie l'ecran du PC a l'app iPad "Tablette" et rejoue les traits du stylet comme un vrai stylet Windows.

Protocole (dans les deux sens) : [type 1 octet][longueur 4 octets big-endian][donnees]
  PC -> iPad   0x01  image JPEG
  iPad -> PC   0x10  trait : phase u8, type u8, x f32, y f32, pression f32, altitude f32, azimut f32
"""
import argparse
import math
import socket
import struct
import threading
import time

import cv2
import dxcam

import usbmux
from stylet import Stylet, rendre_dpi_aware

PORT_IPAD = 2345
TYPE_IMAGE = 0x01
TYPE_TRAIT = 0x10
TRAIT = struct.Struct(">BBfffff")
PHASES = {0: "survol", 1: "pose", 2: "bouge", 3: "leve", 4: "annule"}


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("iPad deconnecte")
        buf += chunk
    return bytes(buf)


class Session:
    def __init__(self, sock, camera, zone, args):
        self.sock = sock
        self.camera = camera
        self.gauche, self.haut, self.largeur, self.hauteur = zone
        self.args = args
        self.stylet = Stylet()
        self.actif = True
        self.signale = set()
        self.pression_max = -1.0
        self.pression_trait = -1.0
        self.traits_affiches = 0

    # ---------- iPad -> PC : traits du stylet ----------
    def boucle_traits(self):
        try:
            while self.actif:
                type_, longueur = struct.unpack(">BI", recv_exact(self.sock, 5))
                donnees = recv_exact(self.sock, longueur)
                if type_ == TYPE_TRAIT and longueur == TRAIT.size:
                    self.traiter(*TRAIT.unpack(donnees))
        except (ConnectionError, OSError):
            pass
        finally:
            self.actif = False

    def traiter(self, phase, genre, x, y, pression, altitude, azimut):
        px = self.gauche + min(max(x, 0.0), 1.0) * (self.largeur - 1)
        py = self.haut + min(max(y, 0.0), 1.0) * (self.hauteur - 1)
        self.signaler(genre, pression)
        self.pression_max = max(self.pression_max, pression)
        self.pression_trait = max(self.pression_trait, pression)
        # Pas de pression (doigt), ou stylet "compatible Pencil" qui envoie toujours 0 : pression fixe.
        if pression < 0 or self.pression_max < 0.05:
            pression = self.args.pression
        # inclinaison : altitude = pi/2 quand le stylet est vertical
        incl = math.degrees(math.pi / 2 - altitude)
        tx, ty = incl * math.cos(azimut), incl * math.sin(azimut)
        if phase == 1:
            self.stylet.poser(px, py, pression, tx, ty)
        elif phase == 2:
            self.stylet.bouger(px, py, pression, tx, ty)
        elif phase in (3, 4):
            self.stylet.lever(px, py)
            if self.traits_affiches < 3:
                self.traits_affiches += 1
                info = "aucune" if self.pression_trait < 0 else f"{self.pression_trait:.2f}"
                print(f"  Trait termine - pression max recue : {info}")
            self.pression_trait = -1.0
        elif phase == 0 and not self.stylet.en_contact:
            self.stylet.survol(px, py)

    def signaler(self, genre, pression):
        cle = (genre, pression >= 0)
        if cle in self.signale:
            return
        self.signale.add(cle)
        nom = "Apple Pencil / stylet compatible" if genre == 1 else "doigt / stylet simple"
        print(f"  Stylet detecte : {nom} - pression {'transmise' if pression >= 0 else 'non disponible'}")

    # ---------- PC -> iPad : image de l'ecran ----------
    def boucle_images(self):
        qualite = [cv2.IMWRITE_JPEG_QUALITY, self.args.qualite]
        n, t0 = 0, time.time()
        while self.actif:
            image = self.camera.get_latest_frame()
            if image is None:
                continue
            if self.args.largeur and image.shape[1] > self.args.largeur:
                h = int(image.shape[0] * self.args.largeur / image.shape[1])
                image = cv2.resize(image, (self.args.largeur, h), interpolation=cv2.INTER_AREA)
            ok, jpeg = cv2.imencode(".jpg", image, qualite)
            if not ok:
                continue
            try:
                self.sock.sendall(struct.pack(">BI", TYPE_IMAGE, len(jpeg)) + jpeg.tobytes())
            except OSError:
                break
            n += 1
            if self.args.stats and time.time() - t0 >= 2:
                print(f"  {n / (time.time() - t0):.0f} images/s, {len(jpeg) // 1024} Ko/image")
                n, t0 = 0, time.time()
        self.actif = False

    def lancer(self):
        t = threading.Thread(target=self.boucle_traits, daemon=True)
        t.start()
        self.boucle_images()
        self.stylet.lever(0, 0)
        try:
            self.sock.close()
        except OSError:
            pass


def main():
    p = argparse.ArgumentParser(description="Transforme l'iPad en tablette graphique (USB).")
    p.add_argument("--ecran", type=int, default=0, help="numero de l'ecran a afficher (voir --lister)")
    p.add_argument("--lister", action="store_true", help="liste les ecrans et quitte")
    p.add_argument("--fps", type=int, default=60, help="images par seconde max (defaut 60)")
    p.add_argument("--qualite", type=int, default=75, help="qualite JPEG 1-100 (defaut 75)")
    p.add_argument("--largeur", type=int, default=1920, help="largeur max envoyee, 0 = native (defaut 1920)")
    p.add_argument("--pression", type=float, default=0.6, help="pression fixe 0-1 si le stylet n'en donne pas")
    p.add_argument("--stats", action="store_true", help="affiche images/s")
    args = p.parse_args()

    if args.lister:
        print(dxcam.output_info())
        return

    rendre_dpi_aware()
    camera = dxcam.create(output_idx=args.ecran, output_color="BGR")
    c = camera._output.desc.DesktopCoordinates
    zone = (c.left, c.top, c.right - c.left, c.bottom - c.top)
    print(f"Ecran {args.ecran} : {zone[2]}x{zone[3]} a la position ({zone[0]}, {zone[1]})")
    camera.start(target_fps=args.fps, video_mode=False)

    print("En attente de l'iPad (branche-le et ouvre l'app Tablette)...  Ctrl+C pour quitter.")
    attente_affichee = False
    try:
        while True:
            appareils = usbmux.list_devices()
            sock = None
            for a in appareils:
                try:
                    sock = usbmux.connect(a["DeviceID"], PORT_IPAD)
                    break
                except (ConnectionRefusedError, OSError):
                    continue
            if sock is None:
                if appareils and not attente_affichee:
                    print("  iPad branche, mais l'app Tablette n'est pas ouverte.")
                    attente_affichee = True
                time.sleep(1)
                continue
            attente_affichee = False
            print("iPad connecte ! Tu peux dessiner.")
            Session(sock, camera, zone, args).lancer()
            print("iPad deconnecte. En attente...")
    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()


if __name__ == "__main__":
    main()
