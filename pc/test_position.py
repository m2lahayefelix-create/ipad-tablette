"""Test : injecte des appuis stylet a des positions connues dans une fenetre plein ecran et compare."""
import ctypes
import threading
import time
import tkinter as tk
from ctypes import wintypes

import stylet

stylet.rendre_dpi_aware()
u = ctypes.windll.user32
clics = []

racine = tk.Tk()
racine.geometry("2560x1440+0+0")
racine.overrideredirect(True)
racine.attributes("-topmost", True)
toile = tk.Canvas(racine, bg="white")
toile.pack(fill="both", expand=True)
toile.bind("<Button-1>", lambda e: clics.append((e.x_root, e.y_root)))

CIBLES = [(200, 200), (1280, 200), (2300, 200), (200, 720), (1280, 720), (2300, 720),
          (200, 1250), (1280, 1250), (2300, 1250)]


def curseur():
    p = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def injecter():
    time.sleep(1.0)
    s = stylet.Stylet()
    for x, y in CIBLES:
        s.poser(x, y, 0.5)
        time.sleep(0.1)
        a = curseur()
        s.bouger(x, y, 0.5)
        time.sleep(0.1)
        b = curseur()
        s.lever(x, y)
        time.sleep(0.4)
        print("envoye", (x, y), "curseur apres pose", a, "apres bouge", b, "clics", len(clics))
    racine.after(0, racine.destroy)


threading.Thread(target=injecter, daemon=True).start()
racine.mainloop()
print("clics", clics)
