"""Simule un vrai stylet Windows (avec pression et inclinaison) via InjectSyntheticPointerInput.

Les logiciels de dessin (Krita, Photoshop...) le voient comme une tablette graphique (Windows Ink).
"""
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

PT_PEN = 3
POINTER_FEEDBACK_DEFAULT = 1

POINTER_FLAG_INRANGE = 0x00000002
POINTER_FLAG_INCONTACT = 0x00000004
POINTER_FLAG_FIRSTBUTTON = 0x00000010
POINTER_FLAG_PRIMARY = 0x00002000
POINTER_FLAG_DOWN = 0x00010000
POINTER_FLAG_UPDATE = 0x00020000
POINTER_FLAG_UP = 0x00040000

PEN_MASK_PRESSURE = 0x1
PEN_MASK_TILT_X = 0x4
PEN_MASK_TILT_Y = 0x8

POINTER_CHANGE_NONE = 0
POINTER_CHANGE_FIRSTBUTTON_DOWN = 1
POINTER_CHANGE_FIRSTBUTTON_UP = 2


class POINTER_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerType", wintypes.DWORD),
        ("pointerId", ctypes.c_uint32),
        ("frameId", ctypes.c_uint32),
        ("pointerFlags", ctypes.c_uint32),
        ("sourceDevice", wintypes.HANDLE),
        ("hwndTarget", wintypes.HWND),
        ("ptPixelLocation", wintypes.POINT),
        ("ptHimetricLocation", wintypes.POINT),
        ("ptPixelLocationRaw", wintypes.POINT),
        ("ptHimetricLocationRaw", wintypes.POINT),
        ("dwTime", wintypes.DWORD),
        ("historyCount", ctypes.c_uint32),
        ("InputData", ctypes.c_int32),
        ("dwKeyStates", wintypes.DWORD),
        ("PerformanceCount", ctypes.c_uint64),
        ("ButtonChangeType", ctypes.c_int),
    ]


class POINTER_PEN_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerInfo", POINTER_INFO),
        ("penFlags", ctypes.c_uint32),
        ("penMask", ctypes.c_uint32),
        ("pressure", ctypes.c_uint32),
        ("rotation", ctypes.c_uint32),
        ("tiltX", ctypes.c_int32),
        ("tiltY", ctypes.c_int32),
    ]


class POINTER_TOUCH_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerInfo", POINTER_INFO),
        ("touchFlags", ctypes.c_uint32),
        ("touchMask", ctypes.c_uint32),
        ("rcContact", wintypes.RECT),
        ("rcContactRaw", wintypes.RECT),
        ("orientation", ctypes.c_uint32),
        ("pressure", ctypes.c_uint32),
    ]


class _INFO_UNION(ctypes.Union):
    _fields_ = [("touchInfo", POINTER_TOUCH_INFO), ("penInfo", POINTER_PEN_INFO)]


class POINTER_TYPE_INFO(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INFO_UNION)]


user32.CreateSyntheticPointerDevice.restype = wintypes.HANDLE
user32.CreateSyntheticPointerDevice.argtypes = [wintypes.DWORD, ctypes.c_uint32, wintypes.DWORD]
user32.InjectSyntheticPointerInput.restype = wintypes.BOOL
user32.InjectSyntheticPointerInput.argtypes = [wintypes.HANDLE, ctypes.POINTER(POINTER_TYPE_INFO), ctypes.c_uint32]


def rendre_dpi_aware():
    """Coordonnees en vrais pixels, meme avec la mise a l'echelle Windows (125 %, 150 %...)."""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except Exception:
        pass


class Stylet:
    def __init__(self):
        self.device = user32.CreateSyntheticPointerDevice(PT_PEN, 1, POINTER_FEEDBACK_DEFAULT)
        if not self.device:
            raise OSError(f"CreateSyntheticPointerDevice a echoue ({ctypes.get_last_error()})")
        self.en_contact = False
        # Windows lit les coordonnees du stylet injecte depuis le coin haut-gauche du bureau virtuel
        # (tous les ecrans), pas depuis l'ecran principal : on compense.
        self.decalage_x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        self.decalage_y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN

    def _injecter(self, x, y, flags, pression=0.0, tilt_x=0, tilt_y=0, bouton=POINTER_CHANGE_NONE):
        x -= self.decalage_x
        y -= self.decalage_y
        info = POINTER_TYPE_INFO()
        info.type = PT_PEN
        pen = info.penInfo
        pen.pointerInfo.pointerType = PT_PEN
        pen.pointerInfo.pointerId = 0
        pen.pointerInfo.pointerFlags = flags | POINTER_FLAG_PRIMARY
        pen.pointerInfo.ptPixelLocation.x = int(x)
        pen.pointerInfo.ptPixelLocation.y = int(y)
        pen.pointerInfo.ButtonChangeType = bouton
        pen.penMask = PEN_MASK_PRESSURE | PEN_MASK_TILT_X | PEN_MASK_TILT_Y
        pen.pressure = max(0, min(1024, int(pression * 1024)))
        pen.tiltX = max(-90, min(90, int(tilt_x)))
        pen.tiltY = max(-90, min(90, int(tilt_y)))
        if not user32.InjectSyntheticPointerInput(self.device, ctypes.byref(info), 1):
            return ctypes.get_last_error()
        return 0

    def survol(self, x, y):
        self._injecter(x, y, POINTER_FLAG_INRANGE | POINTER_FLAG_UPDATE)

    def poser(self, x, y, pression, tx=0, ty=0):
        if self.en_contact:
            self.lever(x, y)
        self.survol(x, y)  # le stylet doit etre "a portee" avant de toucher
        self._injecter(x, y, POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT | POINTER_FLAG_FIRSTBUTTON
                       | POINTER_FLAG_DOWN, pression, tx, ty, POINTER_CHANGE_FIRSTBUTTON_DOWN)
        self.en_contact = True

    def bouger(self, x, y, pression, tx=0, ty=0):
        if not self.en_contact:
            return self.poser(x, y, pression, tx, ty)
        self._injecter(x, y, POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT | POINTER_FLAG_FIRSTBUTTON
                       | POINTER_FLAG_UPDATE, pression, tx, ty)

    def lever(self, x, y):
        if not self.en_contact:
            return
        self._injecter(x, y, POINTER_FLAG_INRANGE | POINTER_FLAG_UP, 0, 0, 0, POINTER_CHANGE_FIRSTBUTTON_UP)
        self._injecter(x, y, POINTER_FLAG_UPDATE)  # hors de portee
        self.en_contact = False
