"""
تبدیل متن تایپ‌شده با کیبورد اشتباه  (LayoutSwitcher) - نسخه‌ی ۳ با ظاهر جدید
نصب:  pip install customtkinter pyperclip pillow
اجرا:  python language_switcher.py
ساخت آیکون:  python language_switcher.py --make-icon
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk

import customtkinter as ctk
import pyperclip
from PIL import Image, ImageChops, ImageDraw, ImageFont

# ───────────────────────── چیدمان‌ها ─────────────────────────
KEYS = "qwertyuiop[]asdfghjkl;'zxcvbnm,./1234567890"
LAYOUTS = {
    "en": {"name": "English", "lang": 0x09, "chars": KEYS},
    "fa": {
        "name": "فارسی",
        "lang": 0x29,
        "chars": "ضصثقفغعهخحجچشسیبلاتنمکگظطزرذدپو./۱۲۳۴۵۶۷۸۹۰",
        "aliases": {"ك": ";", "ي": "d", "ئ": "m", "ؤ": "a", "،": ",", "؟": "?"},
    },
}
for _c, _l in LAYOUTS.items():
    assert len(_l["chars"]) == len(KEYS), f"طول چیدمان {_c} با KEYS برابر نیست"

# ───────────────────────── تنظیمات ─────────────────────────
_CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "LayoutSwitcher")
os.makedirs(_CFG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(_CFG_DIR, "config.json")

MOD_ALT, MOD_CTRL, MOD_SHIFT, MOD_NOREPEAT = 1, 2, 4, 0x4000
DEFAULT_CONFIG = {
    "mods": MOD_CTRL | MOD_ALT,
    "vk": 0x20,
    "label": "Ctrl+Alt+Space",
    "type": "combo",        # combo | double (دوبار فشردن Ctrl/Shift/Alt) | mouse (دکمه‌ی کناری ماوس)
    "switch_layout": True,
    "theme": "system",      # system | light | dark
    "auto_select": True,    # اگر چیزی انتخاب نشده بود، خودکار انتخاب کن
    "auto_mode": "all",     # all (کل متن) | line (خط جاری) | word (آخرین کلمه)
}
AUTO_MODES = {"کل متن": "all", "خط جاری": "line", "آخرین کلمه": "word"}

MOD_NAMES = {17: ("Ctrl", 0x11), 16: ("Shift", 0x10), 18: ("Alt", 0x12)}  # کد کلید در Tk ← (نام، VK)


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ───────────────────────── ویندوز ─────────────────────────
def _setup_winapi():
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    u.GetForegroundWindow.restype = ctypes.c_void_p
    u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    u.GetWindowThreadProcessId.restype = wt.DWORD
    u.GetKeyboardLayout.argtypes = [wt.DWORD]
    u.GetKeyboardLayout.restype = ctypes.c_void_p
    u.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.c_void_p]
    u.GetKeyboardLayoutList.restype = ctypes.c_int
    u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
    u.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
    u.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
    u.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), ctypes.c_void_p,
                               ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
    return u, k


user32, kernel32 = _setup_winapi() if os.name == "nt" else (None, None)
WM_HOTKEY, WM_INPUTLANGCHANGEREQUEST = 0x0312, 0x0050


def fg_window_layout():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return 0
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    return user32.GetKeyboardLayout(tid) or 0


def installed_hkls():
    n = user32.GetKeyboardLayoutList(0, None)
    arr = (ctypes.c_void_p * n)()
    user32.GetKeyboardLayoutList(n, arr)
    return [a for a in arr]


def code_of(hkl):
    if not hkl:
        return None
    prim = (hkl & 0xFFFF) & 0x3FF
    for code, lay in LAYOUTS.items():
        if lay["lang"] == prim:
            return code
    return None


def pick_target(cur_hkl):
    """برمی‌گرداند: (کد زبان فعلی، کد زبان مقصد، HKL مقصد یا None)"""
    cur_code = code_of(cur_hkl)
    cands = [(code_of(h), h) for h in installed_hkls() if code_of(h)]
    if cands:
        start = next((i for i, (_, h) in enumerate(cands) if h == cur_hkl), -1)
        for step in range(1, len(cands) + 1):
            c, h = cands[(start + step) % len(cands)]
            if c != cur_code:
                return cur_code, c, h
    codes = list(LAYOUTS)
    if cur_code in codes:
        return cur_code, codes[(codes.index(cur_code) + 1) % len(codes)], None
    return cur_code, codes[0], None


def _build_reverse():
    rev = {}
    for lay in LAYOUTS.values():
        for k, ch in zip(KEYS, lay["chars"]):
            rev.setdefault(ch, k)
        for ch, k in lay.get("aliases", {}).items():
            rev.setdefault(ch, k)
    return rev


REVERSE = _build_reverse()


def convert(text, target):
    out = dict(zip(KEYS, LAYOUTS[target]["chars"]))
    out.setdefault("?", "؟" if target == "fa" else "?")
    res = []
    for ch in text:
        k = REVERSE.get(ch) or REVERSE.get(ch.lower())
        res.append(out.get(k, ch) if k else ch)
    return "".join(res)


def _key(vk, up=False, ext=False):
    user32.keybd_event(vk, 0, (2 if up else 0) | (1 if ext else 0), 0)


def _combo(*vks, ext=False):
    for v in vks:
        _key(v, ext=ext and v == vks[-1])
    for v in reversed(vks):
        _key(v, True, ext=ext and v == vks[-1])


def _wait_release(extra_vk):
    t0 = time.time()
    vks = (0x10, 0x11, 0x12, 0x5B, 0x5C, extra_vk)
    while time.time() - t0 < 1.5:
        if not any(user32.GetAsyncKeyState(v) & 0x8000 for v in vks):
            break
        time.sleep(0.02)


def _copy_selection():
    pyperclip.copy("")
    _combo(0x11, 0x2D, ext=True)  # Ctrl+Insert
    for _ in range(20):
        time.sleep(0.03)
        t = pyperclip.paste()
        if t:
            return t
    return ""


class HotkeyThread(threading.Thread):
    def __init__(self, mods, vk, callback, report):
        super().__init__(daemon=True)
        self.mods, self.vk, self.callback, self.report = mods, vk, callback, report
        self._stop_evt = threading.Event()

    def stop(self):
        self._stop_evt.set()

    def run(self):
        if not user32.RegisterHotKey(None, 1, self.mods | MOD_NOREPEAT, self.vk):
            self.report("این کلید میانبر توسط برنامه‌ی دیگری استفاده می‌شود")
            return
        self.report("فعال و آماده")
        msg = wt.MSG()
        while not self._stop_evt.is_set():
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == WM_HOTKEY:
                    self.callback()
            else:
                time.sleep(0.02)
        user32.UnregisterHotKey(None, 1)


_VK_FAMILY = {0x10: {0x10, 0xA0, 0xA1}, 0x11: {0x11, 0xA2, 0xA3}, 0x12: {0x12, 0xA4, 0xA5}}


def _is_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


class PollThread(threading.Thread):
    """میانبرهایی که RegisterHotKey پشتیبانی نمی‌کند:
    دوبار فشردن Ctrl/Shift/Alt  و  دکمه‌های کناری ماوس."""
    TAP_MAX, GAP_MAX = 0.35, 0.45   # حداکثر طول هر ضربه / فاصله‌ی دو ضربه (ثانیه)

    def __init__(self, kind, vk, callback, report):
        super().__init__(daemon=True)
        self.kind, self.vk, self.callback, self.report = kind, vk, callback, report
        self._stop_evt = threading.Event()
        own = _VK_FAMILY.get(vk, {vk})
        self._others = [v for v in range(0x01, 0xFF) if v not in own]

    def stop(self):
        self._stop_evt.set()

    def _others_down(self):
        return any(_is_down(v) for v in self._others)

    def run(self):
        self.report("فعال و آماده")
        prev, t_down, last_tap, clean = False, 0.0, 0.0, True
        while not self._stop_evt.is_set():
            time.sleep(0.01)
            down = _is_down(self.vk)
            if self.kind == "mouse":
                if down and not prev:
                    self.callback()
                    time.sleep(0.3)
                    down = _is_down(self.vk)
                prev = down
                continue
            now = time.time()
            if down and not prev:                      # شروع فشردن
                t_down, clean = now, not self._others_down()
            elif down and clean and self._others_down():
                clean = False                          # کلید دیگری هم زده شد (مثل Ctrl+C)
            elif prev and not down:                    # رها کردن
                if clean and now - t_down < self.TAP_MAX:
                    if now - last_tap < self.GAP_MAX:  # ضربه‌ی دوم
                        last_tap = 0.0
                        self.callback()
                        prev = _is_down(self.vk)
                        continue
                    last_tap = now
                else:
                    last_tap = 0.0
            prev = down


# ───────────────────────── ظاهر ─────────────────────────
# هر رنگ = (حالت روشن، حالت تیره)
BG = ("#F3F5FD", "#0E1124")
CARD = ("#FFFFFF", "#171B38")
CARD_HI = ("#ECEFFF", "#21264D")
CARD_NEXT = ("#E2E7FF", "#25306F")
LINE = ("#DADFF3", "#2A3060")
TEXT = ("#14162E", "#F2F3FF")
MUTED = ("#5E658C", "#98A0CC")
ACCENT = ("#4F46E5", "#6C7BFF")
ACCENT2 = ("#0E7490", "#22D3EE")
OK = ("#059669", "#34D399")
ERR = ("#DC2626", "#F87171")
WARN = ("#B45309", "#FBBF24")
SEL = ("#C9D0FF", "#3A44A8")
FONT = "Segoe UI"


def _font(size):
    for name in ("segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_logo(size=256):
    """لوگو: دو کلید کیبورد («ف» و «A») با فلش‌های جابه‌جایی، روی گرادیان."""
    S, u = size * 4, size * 4 / 128
    v = Image.linear_gradient("L").resize((S, S))
    h = v.rotate(90)
    mask = ImageChops.add(v, h, scale=2)
    bg = Image.composite(Image.new("RGB", (S, S), "#06B6D4"), Image.new("RGB", (S, S), "#4F46E5"), mask)
    bg = bg.convert("RGBA")
    ov = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle([20 * u, 20 * u, 76 * u, 76 * u], 14 * u, fill=(255, 255, 255, 82))
    d.rounded_rectangle([52 * u, 52 * u, 108 * u, 108 * u], 14 * u, fill=(255, 255, 255, 255))
    d.text((39 * u, 39 * u), "ف", font=_font(int(26 * u)), fill="white", anchor="mm")
    d.text((80 * u, 80 * u), "A", font=_font(int(34 * u)), fill="#4F46E5", anchor="mm")
    w = int(4 * u)
    for pts in (
        [(86, 28), (102, 28)], [(96, 22), (102, 28), (96, 34)],
        [(42, 100), (26, 100)], [(32, 94), (26, 100), (32, 106)],
    ):
        d.line([(x * u, y * u) for x, y in pts], fill="white", width=w, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x * u - w / 2, y * u - w / 2, x * u + w / 2, y * u + w / 2], fill="white")
    bg.alpha_composite(ov)
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, S - 1, S - 1], 30 * u, fill=255)
    bg.putalpha(m)
    return bg.resize((size, size), Image.LANCZOS)


class App:
    def __init__(self):
        self.cfg = load_config()
        ctk.set_appearance_mode(self.cfg.get("theme", "system"))
        ctk.set_default_color_theme("blue")
        self.root = ctk.CTk(fg_color=BG)
        self.root.title("تبدیل زبان کیبورد")
        self.root.geometry("420x690")
        self.root.resizable(False, False)
        self._down, self._last_mod, self._last_mod_t = set(), None, 0.0
        self.q = queue.Queue()
        self.busy = False
        self.capturing = False
        self.hk_thread = None
        self.my_tid = kernel32.GetCurrentThreadId()
        self.last_hkl = 0

        self._logo = make_logo(256)
        self._logo_ctk = ctk.CTkImage(self._logo, self._logo, size=(60, 60))
        self._icon = tk.PhotoImage(master=self.root, data=self._png_b64(make_logo(64)))
        self.root.after(300, lambda: self.root.iconphoto(False, self._icon))

        self._build()
        self.root.bind("<KeyPress>", self.on_key)
        self.root.bind("<KeyRelease>", lambda e: self._down.discard(e.keycode))
        self.start_hotkey()
        self.tick()

    @staticmethod
    def _png_b64(img):
        import base64, io
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return base64.b64encode(buf.getvalue())

    # ───── ساخت رابط ─────
    def _card(self, **kw):
        f = ctk.CTkFrame(self.root, fg_color=CARD, corner_radius=22, border_width=1, border_color=LINE)
        f.pack(fill="x", padx=22, pady=kw.get("pady", 7))
        return f

    def _build(self):
        head = ctk.CTkFrame(self.root, fg_color="transparent")
        head.pack(fill="x", padx=26, pady=(26, 14))
        ctk.CTkLabel(head, image=self._logo_ctk, text="").pack(side="right")
        box = ctk.CTkFrame(head, fg_color="transparent")
        box.pack(side="right", padx=14)
        ctk.CTkLabel(box, text="تبدیل زبان کیبورد", text_color=TEXT, anchor="e",
                     font=ctk.CTkFont(family=FONT, size=22, weight="bold")).pack(anchor="e")
        ctk.CTkLabel(box, text="متنِ اشتباه تایپ‌شده را با یک کلید درست کنید", text_color=MUTED,
                     anchor="e", font=ctk.CTkFont(family=FONT, size=12)).pack(anchor="e")

        # کارت ۱: زبان فعلی ← زبان مقصد
        c1 = self._card()
        row = ctk.CTkFrame(c1, fg_color="transparent")
        row.pack(padx=16, pady=18, fill="x")
        row.grid_columnconfigure((0, 2), weight=1, uniform="a")
        row.grid_columnconfigure(1, weight=0)
        self.cur_lbl = self._chip(row, 2, "زبان فعلی", CARD_HI, TEXT)
        ctk.CTkLabel(row, text="←", width=40, height=40, corner_radius=20, fg_color=ACCENT,
                     text_color="white", font=ctk.CTkFont(family=FONT, size=20, weight="bold")
                     ).grid(row=0, column=1, padx=10)
        self.next_lbl = self._chip(row, 0, "تبدیل می‌شود به", CARD_NEXT, ACCENT2)

        # کارت ۲: کلید میانبر
        c2 = self._card()
        ctk.CTkLabel(c2, text="کلید میانبر", text_color=MUTED, anchor="e",
                     font=ctk.CTkFont(family=FONT, size=12)).pack(fill="x", padx=20, pady=(14, 0))
        self.keys_box = ctk.CTkFrame(c2, fg_color="transparent", height=48)
        self.keys_box.pack(pady=(8, 10))
        self.hk_btn = ctk.CTkButton(
            c2, text="تغییر کلید میانبر", height=40, corner_radius=14, command=self.start_capture,
            fg_color="transparent", border_width=1, border_color=ACCENT, text_color=ACCENT,
            hover_color=CARD_HI, font=ctk.CTkFont(family=FONT, size=13, weight="bold"))
        self.hk_btn.pack(fill="x", padx=20, pady=(0, 18))
        self.show_hotkey()

        # کارت ۳: گزینه‌ها
        c3 = self._card()
        self.sw_var = tk.BooleanVar(value=self.cfg["switch_layout"])
        ctk.CTkSwitch(c3, text="بعد از تبدیل، زبان سیستم هم عوض شود", variable=self.sw_var,
                      command=self.on_switch, progress_color=ACCENT, button_color="white",
                      button_hover_color="#DDE", fg_color=LINE, text_color=TEXT,
                      font=ctk.CTkFont(family=FONT, size=13)).pack(padx=20, pady=(18, 10), anchor="e")
        self.auto_var = tk.BooleanVar(value=self.cfg["auto_select"])
        ctk.CTkSwitch(c3, text="اگر متنی انتخاب نشده بود، خودکار انتخاب شود", variable=self.auto_var,
                      command=self.on_auto, progress_color=ACCENT, button_color="white",
                      button_hover_color="#DDE", fg_color=LINE, text_color=TEXT,
                      font=ctk.CTkFont(family=FONT, size=13)).pack(padx=20, pady=(0, 10), anchor="e")
        self.auto_btn = ctk.CTkSegmentedButton(
            c3, values=list(AUTO_MODES), command=self.on_auto_mode, height=32, corner_radius=12,
            fg_color=CARD_HI, selected_color=SEL, selected_hover_color=SEL,
            unselected_color=CARD_HI, unselected_hover_color=LINE, text_color=TEXT,
            font=ctk.CTkFont(family=FONT, size=12))
        self.auto_btn.set({v: k for k, v in AUTO_MODES.items()}[self.cfg["auto_mode"]])
        self.auto_btn.pack(fill="x", padx=20, pady=(0, 12))
        self._sync_auto_state()
        trow = ctk.CTkFrame(c3, fg_color="transparent")
        trow.pack(fill="x", padx=20, pady=(0, 18))
        ctk.CTkLabel(trow, text="پوسته", text_color=TEXT, font=ctk.CTkFont(family=FONT, size=13)
                     ).pack(side="right", padx=(12, 0))
        self._themes = {"سیستم": "system", "روشن": "light", "تیره": "dark"}
        self.theme_btn = ctk.CTkSegmentedButton(
            trow, values=list(self._themes), command=self.on_theme, height=32, corner_radius=12,
            fg_color=CARD_HI, selected_color=SEL, selected_hover_color=SEL,
            unselected_color=CARD_HI, unselected_hover_color=LINE, text_color=TEXT,
            font=ctk.CTkFont(family=FONT, size=12))
        self.theme_btn.set({v: k for k, v in self._themes.items()}[self.cfg.get("theme", "system")])
        self.theme_btn.pack(side="left", fill="x", expand=True)

        # نوار وضعیت
        bar = ctk.CTkFrame(self.root, fg_color=CARD, corner_radius=16)
        bar.pack(fill="x", padx=22, pady=(10, 22), side="bottom")
        self.dot = ctk.CTkLabel(bar, text="●", text_color=MUTED, font=ctk.CTkFont(size=14))
        self.dot.pack(side="right", padx=(0, 16), pady=12)
        self.status = ctk.CTkLabel(bar, text="در حال راه‌اندازی…", text_color=MUTED, anchor="e",
                                   wraplength=320, justify="right",
                                   font=ctk.CTkFont(family=FONT, size=12))
        self.status.pack(side="right", padx=8)

    def _chip(self, parent, col, caption, fg, color):
        f = ctk.CTkFrame(parent, fg_color=fg, corner_radius=16)
        f.grid(row=0, column=col, sticky="nsew")
        ctk.CTkLabel(f, text=caption, text_color=MUTED,
                     font=ctk.CTkFont(family=FONT, size=11)).pack(pady=(12, 0))
        lbl = ctk.CTkLabel(f, text="—", text_color=color,
                           font=ctk.CTkFont(family=FONT, size=22, weight="bold"))
        lbl.pack(pady=(0, 14))
        return lbl

    def show_hotkey(self, prompt=None):
        for w in self.keys_box.winfo_children():
            w.destroy()
        if prompt:
            ctk.CTkLabel(self.keys_box, text=prompt, text_color=WARN, wraplength=330,
                         font=ctk.CTkFont(family=FONT, size=13)).pack(pady=10)
            return
        parts = [p for p in self.cfg["label"].split("+") if p]
        if self.cfg.get("type") == "double":
            parts = [parts[0]]
            ctk.CTkLabel(self.keys_box, text=parts[0], text_color=TEXT, fg_color=CARD_HI, corner_radius=10,
                         height=38, width=max(46, 14 + 9 * len(parts[0])),
                         font=ctk.CTkFont(family=FONT, size=13, weight="bold")).pack(side="left")
            ctk.CTkLabel(self.keys_box, text="دوبار پشت‌هم", text_color="white", fg_color=ACCENT,
                         corner_radius=10, height=26, width=86,
                         font=ctk.CTkFont(family=FONT, size=11, weight="bold")).pack(side="left", padx=8)
            return
        for i, p in enumerate(parts):
            if i:
                ctk.CTkLabel(self.keys_box, text="+", text_color=MUTED, width=18).pack(side="left")
            ctk.CTkLabel(self.keys_box, text=p, text_color=TEXT, fg_color=CARD_HI, corner_radius=10,
                         height=38, width=max(46, 14 + 9 * len(p)),
                         font=ctk.CTkFont(family=FONT, size=13, weight="bold")).pack(side="left")

    # ───── منطق ─────
    def tick(self):
        if self.capturing:                               # دکمه‌های کناری ماوس را Tk گزارش نمی‌کند
            for vk, name in ((0x05, "Mouse Back"), (0x06, "Mouse Forward")):
                if _is_down(vk):
                    self.end_capture({"type": "mouse", "mods": 0, "vk": vk, "label": name})
                    break
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "status":
                    good = val.startswith(("فعال", "تبدیل شد"))
                    bad = val.startswith(("خطا", "این کلید"))
                    col = OK if good else ERR if bad else WARN
                    self.status.configure(text=val, text_color=TEXT if good else col)
                    self.dot.configure(text_color=col)
        except queue.Empty:
            pass
        hkl = fg_window_layout()
        tid = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        if hkl and tid != self.my_tid:
            self.last_hkl = hkl
        if self.last_hkl:
            cur, nxt, _ = pick_target(self.last_hkl)
            self.cur_lbl.configure(text=LAYOUTS[cur]["name"] if cur else "—")
            self.next_lbl.configure(text=LAYOUTS[nxt]["name"])
        self.root.after(300, self.tick)

    def report(self, text):
        self.q.put(("status", text))

    def on_switch(self):
        self.cfg["switch_layout"] = self.sw_var.get()
        save_config(self.cfg)

    def start_hotkey(self):
        self.stop_hotkey()
        kind = self.cfg.get("type", "combo")
        if kind in ("double", "mouse"):
            self.hk_thread = PollThread(kind, self.cfg["vk"], self.run_convert, self.report)
        else:
            self.hk_thread = HotkeyThread(self.cfg["mods"], self.cfg["vk"], self.run_convert, self.report)
        self.hk_thread.start()

    def stop_hotkey(self):
        if self.hk_thread:
            self.hk_thread.stop()
            self.hk_thread.join(timeout=0.5)
            self.hk_thread = None

    def start_capture(self):
        self.stop_hotkey()
        self.capturing = True
        self._down.clear(); self._last_mod = None
        self.show_hotkey("هر کلید یا ترکیبی را بزنید  •  دوبار Ctrl/Shift/Alt یا دکمه‌ی کناری ماوس هم قبوله  •  Esc = انصراف")
        self.hk_btn.configure(state="disabled")
        self.report("در انتظار کلید جدید…")
        self.root.focus_force()

    def on_key(self, e):
        if not self.capturing:
            return
        if e.keycode in MOD_NAMES:                       # تشخیص «دوبار فشردن» یک کلید تغییردهنده
            if e.keycode in self._down:
                return                                   # تکرار خودکار کلید نگه‌داشته‌شده
            self._down.add(e.keycode)
            now = time.time()
            if self._last_mod == e.keycode and now - self._last_mod_t < 0.5:
                name, vk = MOD_NAMES[e.keycode]
                return self.end_capture({"type": "double", "mods": 0, "vk": vk, "label": name})
            self._last_mod, self._last_mod_t = e.keycode, now
            return
        self._last_mod = None
        if e.keycode in (20, 91, 92):
            return
        if e.keysym == "Escape":
            return self.end_capture(None)
        mods, parts = 0, []
        if e.state & 0x4:
            mods |= MOD_CTRL; parts.append("Ctrl")
        if e.state & 0x20000:
            mods |= MOD_ALT; parts.append("Alt")
        if e.state & 0x1:
            mods |= MOD_SHIFT; parts.append("Shift")
        plain = e.keycode == 32 or 0x30 <= e.keycode <= 0x5A
        if plain and not (mods & (MOD_CTRL | MOD_ALT)):
            return self.report("برای حروف/اعداد/Space حتماً از Ctrl یا Alt هم استفاده کنید")
        ks = e.keysym
        parts.append(ks[:1].upper() + ks[1:] if len(ks) > 1 else ks.upper())
        self.end_capture({"type": "combo", "mods": mods, "vk": e.keycode, "label": "+".join(parts)})

    def end_capture(self, new):
        self.capturing = False
        if new:
            self.cfg.update(new)
            save_config(self.cfg)
        self.show_hotkey()
        self.hk_btn.configure(state="normal")
        self.start_hotkey()

    def _sync_auto_state(self):
        self.auto_btn.configure(state="normal" if self.auto_var.get() else "disabled")

    def on_auto(self):
        self.cfg["auto_select"] = self.auto_var.get()
        save_config(self.cfg)
        self._sync_auto_state()

    def on_auto_mode(self, choice):
        self.cfg["auto_mode"] = AUTO_MODES[choice]
        save_config(self.cfg)

    def _auto_select(self):
        """وقتی چیزی انتخاب نشده: متن اطراف مکان‌نما را خودکار انتخاب می‌کند."""
        mode = self.cfg.get("auto_mode", "all")
        if mode == "line":
            _combo(0x10, 0x24, ext=True)            # Shift+Home
        elif mode == "word":
            _combo(0x11, 0x10, 0x25, ext=True)      # Ctrl+Shift+←
        else:
            _combo(0x11, 0x41)                      # Ctrl+A
        time.sleep(0.06)

    def on_theme(self, choice):
        mode = self._themes[choice]
        self.cfg["theme"] = mode
        save_config(self.cfg)
        ctk.set_appearance_mode(mode)

    def run_convert(self):
        if self.busy or self.capturing:
            return
        self.busy = True
        try:
            _wait_release(self.cfg["vk"])
            old = pyperclip.paste()
            text = _copy_selection()                 # اول: اگر متنی انتخاب شده همان را بردار
            if not text and self.cfg.get("auto_select"):
                self._auto_select()                  # وگرنه خودکار انتخاب کن
                text = _copy_selection()
            if not text:
                pyperclip.copy(old)
                return self.report("متنی برای تبدیل پیدا نشد")
            hwnd = user32.GetForegroundWindow()
            cur, target, hkl = pick_target(fg_window_layout())
            if cur is None:  # زبان ناشناخته: از روی خود متن حدس می‌زنیم
                target = "en" if any(ch in REVERSE and ch not in KEYS for ch in text) else "fa"
            pyperclip.copy(convert(text, target))
            time.sleep(0.08)
            _combo(0x10, 0x2D, ext=True)  # Shift+Insert
            time.sleep(0.25)
            pyperclip.copy(old)
            if self.cfg["switch_layout"] and hkl:
                user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl)
            self.report("تبدیل شد به " + LAYOUTS[target]["name"])
        except Exception as ex:
            self.report("خطا: " + str(ex))
        finally:
            self.busy = False

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self):
        self.stop_hotkey()
        self.root.destroy()


if __name__ == "__main__":
    if "--make-icon" in sys.argv:
        here = os.path.dirname(os.path.abspath(__file__))
        make_logo(256).save(os.path.join(here, "icon.ico"),
                            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        make_logo(512).save(os.path.join(here, "logo.png"))
        print("icon.ico و logo.png ساخته شد.")
        sys.exit()
    _mutex = kernel32.CreateMutexW(None, False, "LayoutSwitcher_SingleInstance")
    if kernel32.GetLastError() == 183:
        user32.MessageBoxW(None, "برنامه از قبل در حال اجراست.", "تبدیل زبان کیبورد", 0x40)
        sys.exit()
    App().run()
