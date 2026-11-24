"""UCH level editor in its own window. Run: python editor.py

Left mouse draws (hold to keep drawing). Right mouse selects a rectangle; drag the selection to move it
(Delete removes it, Esc deselects). The wheel zooms, holding the wheel pans. Dragging a grid edge resizes the board.
Other keys: see the Settings window (defaults: KEYS). Ctrl+Z = undo, Ctrl+Y = redo, Ctrl+S = save.
The level goes to the game's snapshots folder as <name>.c.snapshot.
"""
import ctypes
import io
import json
import math
import os
import struct
import warnings

import pygame

import lang
import uch_level as L
from lang import tr

COLS = ROWS = 0
ZOOM_MAX = 64
SIDE = 231  # width of the panel (at the side) or of one of its columns (below the board)
PAD = 10  # padding from the panel's edge
SIDE_H, BOTTOM_H = 832, 272  # height of a window with the panel at the side / of the panel below the board
STATUS = 32
MARGIN = 12  # strip around the grid for grabbing its edges
DETAIL_OK = 0.93  # share of cells that must match the largest version for a smaller board to be good enough
MODES = {"brush": "brush", "erase": "eraser", "fill": "fill"}
KEYS = {"pl": dict(brush="P", erase="G", fill="W", preview="K", game="I"),  # defaults: first letters of the names; if taken, the second letter
        "en": dict(brush="B", erase="E", fill="F", preview="L", game="G")}
COLOR_KINDS = [k for k in L.KINDS if k.startswith("color")]
ITEMS = ["wood", "spike", "wire", "start", "goal"]
COLOR = {**{k: v["color"] for k, v in L.KINDS.items()}, "start": (200, 170, 60), "goal": (250, 215, 0)}
# The board looks like graph paper (light) and blueprint (dark). The panel is neutral grey so it does not distort block colors.
# accent (yellow) = something is waiting: unsaved level, unapplied size. on = selected. danger = deleting.
THEMES = {
    "dark": dict(bg=(33, 35, 37), panel=(48, 50, 51), hair=(66, 69, 70), grid=(36, 47, 62), thin=(47, 60, 78), thick=(84, 104, 133),
                 text=(238, 236, 230), muted=(178, 179, 175), off=(112, 115, 115), btn=(66, 69, 70), hover=(82, 85, 86),
                 on=(238, 236, 230), on_text=(33, 34, 35), field=(33, 35, 37), border=(124, 127, 128), focus=(246, 200, 62),
                 accent=(246, 200, 62), accent_text=(36, 30, 10), msg=(246, 214, 120), mark=(255, 255, 255), danger=(255, 166, 150)),
    "light": dict(bg=(205, 210, 213), panel=(240, 241, 240), hair=(214, 217, 217), grid=(255, 255, 255), thin=(219, 231, 243), thick=(149, 182, 217),
                  text=(33, 36, 38), muted=(86, 91, 94), off=(150, 154, 156), btn=(222, 225, 225), hover=(206, 210, 211),
                  on=(46, 50, 53), on_text=(255, 255, 255), field=(255, 255, 255), border=(132, 137, 140), focus=(36, 92, 168),
                  accent=(250, 203, 52), accent_text=(36, 30, 10), msg=(120, 78, 0), mark=(20, 20, 25), danger=(176, 34, 26)),
}
T = THEMES["dark"]
FONTS = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f) for f in ("bahnschrift.ttf", "segoeui.ttf")]
# icons on a 16x16 grid: polylines, and (x, y, r) is a circle
_UNDO = ((10.5, 12.5), (6, 12.5)), ((3, 6), (10, 6), (12.2, 6.9), (13.2, 9.2), (12.2, 11.6), (10, 12.5)), ((6, 3), (3, 6), (6, 9))
ICONS = {
    "brush": (((3, 13), (4, 9.7), (10.8, 2.9), (13.1, 5.2), (6.3, 12), (3, 13)), ((9, 4.7), (11.3, 7))),
    "erase": (((2.5, 9.8), (8.6, 3.7), (13, 8.1), (8.1, 13), (5.7, 13), (2.5, 9.8)), ((5.6, 6.8), (10, 11.2)), ((8.1, 13), (14, 13))),
    "fill": (((2.2, 8.4), (7.4, 3.2), (12.2, 8), (7, 13.2), (2.2, 8.4)), ((7.4, 3.2), (5.4, 1.2)), ((2.2, 8.4), (12, 8.2)), (14, 12, 1.5)),
    "undo": _UNDO,
    "redo": tuple(tuple((16 - x, y) for x, y in line) for line in _UNDO),
    "paste": (((2, 3), (14, 3), (14, 13), (2, 13), (2, 3)), ((2.4, 11.6), (6, 7.6), (9, 10.6), (10.8, 8.8), (13.6, 11.6)), (10.6, 6, 1.2)),
    "delete": (((2, 5), (2, 2), (5, 2)), ((11, 2), (14, 2), (14, 5)), ((14, 11), (14, 14), (11, 14)), ((5, 14), (2, 14), (2, 11)),
               ((5.6, 5.6), (10.4, 10.4)), ((10.4, 5.6), (5.6, 10.4))),
    "clear": (((2.6, 4.4), (13.4, 4.4)), ((6, 4.4), (6, 2.2), (10, 2.2), (10, 4.4)), ((4, 4.4), (4.8, 13.8), (11.2, 13.8), (12, 4.4)),
              ((6.9, 7), (7, 11)), ((9.1, 7), (9, 11))),
    "settings": (((2, 4), (14, 4)), ((2, 8), (14, 8)), ((2, 12), (14, 12)), (10.5, 4, 1.9), (5, 8, 1.9), (9, 12, 1.9)),
    "close": (((4, 4), (12, 12)), ((12, 4), (4, 12))),
    "check": (((3.2, 8.4), (6.6, 11.6), (12.8, 4.6)),),
}
SETTINGS = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "UCH level maker", "settings.json")
CURSORS = {"l": "SIZEWE", "r": "SIZEWE", "t": "SIZENS", "b": "SIZENS", "lt": "SIZENWSE", "rb": "SIZENWSE", "rt": "SIZENESW", "lb": "SIZENESW"}
SKY_TOP, SKY_BOTTOM = (88, 182, 222), (150, 214, 236)  # like the sky on the BlankLevel thumbnail


def fit_window(cols, rows, desk):
    """Best window for a board: (cell, is the panel below, (width, height)). The layout with less empty space wins."""
    w, h = max(desk[0] - 40, 1000), max(desk[1] - 110, SIDE_H)  # room for the window frame and the taskbar
    out = []
    for bottom in (False, True):
        cell = fit_cell(cols, rows, (w, h), bottom)
        bw, bh = cols * cell + 2 * MARGIN, rows * cell + 2 * MARGIN
        size = (max(bw, 4 * SIDE), bh + STATUS + BOTTOM_H) if bottom else (bw + SIDE, max(bh + STATUS, SIDE_H))
        out.append((bw * bh / (size[0] * size[1]), cell, bottom, size))
    return max(out)[1:]


def fit_cell(cols, rows, size, bottom):
    """Largest cell size at which the board fits the window."""
    w, h = size[0] - 2 * MARGIN, size[1] - 2 * MARGIN - STATUS
    return min(w // cols, (h - BOTTOM_H) // rows) if bottom else min((w - SIDE) // cols, h // rows)


class Camera:
    """View of the board: z = pixels per cell, (x, y) = world point at the center of the view (cell x spans x..x+1)."""

    def __init__(self):
        self.view = pygame.Rect(0, 0, 1, 1)
        self.z = self.target = self.raw = 10.0
        self.x = self.y = 0.0
        self.anchor = None  # (pixel, world point) that stays put while zooming
        self.to_center = False  # glide back to the center of the board (when the board outgrew the view)

    def fit(self):
        return max(min((self.view.w - 2 * MARGIN) // COLS, (self.view.h - 2 * MARGIN) // ROWS), 2)

    def reset(self):
        """The whole board, centered, without animation."""
        self.z = self.target = self.raw = float(self.fit())
        self.x, self.y = L.X_MIN + COLS / 2, L.Y_MIN + ROWS / 2
        self.anchor, self.to_center = None, False

    def world(self, pos):
        return self.x + (pos[0] - self.view.centerx) / self.z, self.y - (pos[1] - self.view.centery) / self.z

    def px(self, wx, wy):
        return (math.floor(self.view.centerx + (wx - self.x) * self.z + 0.5),
                math.floor(self.view.centery - (wy - self.y) * self.z + 0.5))

    def zoom(self, steps, pos):
        low = max(self.fit() * 0.4, 2)
        self.raw = min(max(self.raw * 1.2 ** steps, low), ZOOM_MAX)
        self.target = float(round(self.raw))  # a whole number of pixels at rest: all cells equal
        if self.target <= self.fit():  # the whole board is visible: back to the center
            self.anchor, self.to_center = None, True
        else:
            self.anchor, self.to_center = (pos, self.world(pos)), False

    def show_all(self):
        """Smoothly zooms out if the board does not fit the view."""
        if self.fit() < self.target:
            self.target = self.raw = float(self.fit())
        self.anchor, self.to_center = None, True

    def pan(self, dx, dy):
        self.anchor, self.to_center = None, False
        self.x -= dx / self.z
        self.y += dy / self.z
        self.clamp()

    def clamp(self):
        """The center of the view stays over the board, so it can't get lost."""
        self.x = min(max(self.x, L.X_MIN), L.X_MAX + 1)
        self.y = min(max(self.y, L.Y_MIN), L.Y_MAX + 1)

    def update(self, dt):
        """One animation frame; dt in seconds. The speed does not depend on the frame rate."""
        k = 1 - math.exp(-dt * 16)
        if self.z != self.target:
            self.z *= (self.target / self.z) ** k
            if abs(self.z / self.target - 1) < 0.003:
                self.z = self.target
        if self.anchor:
            (px, py), (wx, wy) = self.anchor
            self.x = wx - (px - self.view.centerx) / self.z
            self.y = wy + (py - self.view.centery) / self.z
            if self.z == self.target:
                self.anchor = None
        elif self.to_center:
            self.x += (L.X_MIN + COLS / 2 - self.x) * k
            self.y += (L.Y_MIN + ROWS / 2 - self.y) * k
        self.clamp()


cam = Camera()


def to_screen(x, y):
    return cam.px(x, y + 1)


def to_cell(px, py):
    wx, wy = cam.world((px, py))
    return math.floor(wx), math.floor(wy)


def grid_rect():
    x, y = cam.px(L.X_MIN, L.Y_MAX + 1)
    r, b = cam.px(L.X_MAX + 1, L.Y_MIN)
    return pygame.Rect(x, y, r - x, b - y)


def edges_at(pos):
    """Grid edges under the mouse: "l", "r", "t", "b" or a corner such as "lt"; "" = none. Grabbed just outside the grid."""
    g = grid_rect()
    if not cam.view.collidepoint(pos) or g.collidepoint(pos) or not g.inflate(2 * MARGIN, 2 * MARGIN).collidepoint(pos):
        return ""
    x, y = pos
    near = 4  # near a corner both sides are grabbed
    return ("l" if x < g.left + near else "r" if x >= g.right - near else "") + \
           ("t" if y < g.top + near else "b" if y >= g.bottom - near else "")


def label(t):
    if t.startswith("color"):
        return tr("Color {}", int(t[5:]) + 1)
    return tr({"start": "Start (4x1 plank)", "goal": "Goal (flag)"}.get(t) or L.KINDS[t]["label"])


def in_bounds(c):
    return L.X_MIN <= c[0] <= L.X_MAX and L.Y_MIN <= c[1] <= L.Y_MAX


def darker(c, f=0.7):
    return tuple(int(v * f) for v in c)


def clipboard_image():
    """Image from the Windows clipboard (e.g. after Win+Shift+S) as a pygame.Surface, or None."""
    CF_DIB = 8
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = k32.GlobalUnlock.argtypes = k32.GlobalSize.argtypes = [ctypes.c_void_p]
    u32.GetClipboardData.restype = ctypes.c_void_p
    if not u32.IsClipboardFormatAvailable(CF_DIB) or not u32.OpenClipboard(None):
        return None
    try:
        h = u32.GetClipboardData(CF_DIB)
        ptr = k32.GlobalLock(h)
        dib = ctypes.string_at(ptr, k32.GlobalSize(h))
        k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()
    # the clipboard holds a BMP without its 14-byte file header: add it
    hsize, bits, comp, used = struct.unpack_from("<I10xHI12xI", dib)
    offset = 14 + hsize + (used or (1 << bits if bits <= 8 else 0)) * 4 + (12 if comp == 3 and hsize == 40 else 0)
    return pygame.image.load(io.BytesIO(b"BM" + struct.pack("<IHHI", 14 + len(dib), 0, 0, offset) + dib), "x.bmp")


class Editor:
    def __init__(self):
        pygame.init()
        self.desk, self.screen = pygame.display.get_desktop_sizes()[0], None
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        for c, r in (((208, 101, 59), (2, 20, 18, 10)), ((69, 139, 179), (12, 10, 18, 10)), ((246, 200, 62), (22, 20, 8, 10))):
            icon.fill(c, r)
        pygame.display.set_icon(icon)
        font = next((f for f in FONTS if os.path.exists(f)), None)
        self.big, self.font, self.small = (pygame.font.Font(font, size) for size in (20, 15, 13))
        self.icons = {}
        self.mouse = -1, -1  # where to highlight buttons
        self.box = pygame.Rect(0, 0, 0, 0)  # the settings window
        self.grid, self.start, self.goal = {}, None, None
        self.saved = None  # level state at the last successful save
        self.image = None  # pasted image, until cells change: it can still be fitted to another board
        self.tool, self.tab = COLOR_KINDS[0], "colors"
        self.mode, self.preview, self.game_view = "brush", False, False
        self.undo, self.redo = [], []
        self.text, self.focus = {}, None  # text fields and the one being typed in
        self.sel = None  # selection: (x0, y0, x1, y1) inclusive
        self.sel_from = None  # cell where a new selection started
        self.move = None  # moving: see begin_move
        self.msg, self.drag, self.last = "", None, None
        self.tiles = self.surf = None  # merged blocks and the board image, recomputed after a change
        self.buttons = {}
        self.resize = None  # dragging an edge: (edges, mouse position, board, zoom at the start, was undo saved)
        self.settings = False  # the settings window is open; it covers the editor
        self.binding = None  # shortcut waiting in settings for a new letter
        self.panning = False
        self.board = None
        self.cursor = ""
        self.load_settings()
        self.text["name"] = tr("My level")
        self.set_board(L.board(40, 40))

    # --- settings ---
    def load_settings(self):
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        d = d if isinstance(d, dict) else {}
        mine = d.get("keys") if isinstance(d.get("keys"), dict) else {}
        self.keys = {l: dict(mine[l] if self.good_keys(mine.get(l)) else default) for l, default in KEYS.items()}
        self.apply_settings("light" if d.get("theme") == "light" else "dark", "pl" if d.get("lang") == "pl" else "en")

    def good_keys(self, k):
        """A full set of shortcuts: each one a different letter A-Z."""
        return isinstance(k, dict) and k.keys() == KEYS["pl"].keys() and \
            all(isinstance(v, str) and len(v) == 1 and "A" <= v <= "Z" for v in k.values()) and len(set(k.values())) == len(k)

    def rebind(self, letter):
        """New letter for self.binding; if it is taken, the shortcuts swap letters."""
        keys = self.keys[lang.current]
        for other, v in keys.items():
            if v == letter:
                keys[other] = keys[self.binding]
        keys[self.binding] = letter
        self.binding = None
        self.change_settings(self.theme, lang.current)

    def apply_settings(self, theme, language):
        global T
        self.theme, lang.current, T = theme, language, THEMES[theme]
        self.surf = None

    def change_settings(self, theme, language):
        self.apply_settings(theme, language)
        self.msg = ""
        try:
            os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
            with open(SETTINGS, "w", encoding="utf-8") as f:
                json.dump({"theme": theme, "lang": language, "keys": {l: k for l, k in self.keys.items() if k != KEYS[l]}}, f)
        except OSError as e:
            self.alert(tr("Can't save settings: {}", e))

    # --- state ---
    def reserved(self):
        out = set()
        if self.start:
            out |= {(self.start[0] + i, self.start[1]) for i in range(4)}
        if self.goal:
            out.add(self.goal)
        return out

    def push_undo(self):
        self.undo.append(self.state())
        del self.undo[:-50]
        self.redo.clear()

    def step(self, src, dst):
        """Undo: step(undo, redo). Redo: step(redo, undo)."""
        if src:
            dst.append(self.state())
            self.grid, self.start, self.goal, b = src.pop()
            self.image, self.msg = None, ""
            self.sel = self.sel_from = self.move = self.drag = self.resize = None
            if b != self.board:
                self.set_board(b)
            self.changed()

    def set_board(self, b, keep_window=False):
        """Resizes. Cells outside a smaller board stay in memory, they are just not saved.

        keep_window: while dragging the window stays put and is refitted only at the end.
        """
        global COLS, ROWS
        self.board = b
        L.set_board(b)
        COLS, ROWS = L.board_size(b)
        if keep_window:
            cam.show_all()
        else:
            _, self.bottom, size = fit_window(COLS, ROWS, self.desk)
            if not self.screen or self.screen.get_size() != size:
                self.screen = pygame.display.set_mode(size)
                pygame.display.set_window_position(((self.desk[0] - size[0]) // 2, max((self.desk[1] - size[1]) // 2 - 10, 32)))
            cam.view = pygame.Rect(0, 0, size[0], size[1] - STATUS - BOTTOM_H) if self.bottom else \
                pygame.Rect(0, 0, size[0] - SIDE, size[1] - STATUS)
            cam.reset()
        self.text["w"], self.text["h"] = str(COLS), str(ROWS)
        self.sel = self.sel_from = self.move = self.drag = self.resize = None
        self.changed()

    def on_wheel(self, steps, pos):
        if self.busy():
            return
        over = [k[1] for k, r in self.buttons.items() if k[0] == "field" and r.collidepoint(pos)]
        if over and over[0] != "name":
            self.set_focus(None)
            self.nudge(over[0], round(steps))
        elif cam.view.collidepoint(pos):
            cam.zoom(steps, pos)

    def busy(self):
        return self.drag is not None or self.move or self.sel_from or self.resize or self.panning

    def set_focus(self, f):
        """Changes the field being typed in. A typed size waits in its field for Apply or Enter."""
        for k, n in (("w", COLS), ("h", ROWS)):
            if k == self.focus and k != f:
                self.text[k] = self.text[k] or str(n)  # an empty field keeps the old number
        if f in ("w", "h") and f != self.focus:
            self.text[f] = ""  # typing starts a new number right away
        self.focus = f

    def typed_size(self):
        """Sizes from the fields, within the allowed range."""
        side = [int(self.text[k] or 0) or n for k, n in (("w", COLS), ("h", ROWS))]
        return [min(max(v, L.MIN_SIDE), L.MAX_SIDE) for v in side]

    def nudge(self, f, n):
        """Arrows next to a size field, the up/down keys and the wheel over a field."""
        v = self.typed_size()["wh".index(f)] + n
        self.text[f] = str(min(max(v, L.MIN_SIDE), L.MAX_SIDE))

    def apply_size(self):
        self.set_focus(None)
        side = self.typed_size()
        if side == [COLS, ROWS]:
            self.text["w"], self.text["h"] = str(COLS), str(ROWS)
        elif self.image:  # the pasted image adapts to the typed board
            self.place_image(L.resized(self.board, *side))
        else:
            self.push_undo()
            self.set_board(L.resized(self.board, *side))

    # --- selection ---
    def in_sel(self, c):
        return self.sel and self.sel[0] <= c[0] <= self.sel[2] and self.sel[1] <= c[1] <= self.sel[3]

    def select(self, a, b):
        self.sel = min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])

    def begin_move(self, c):
        """Lifts the selected cells (the start and the goal too, if fully inside the selection)."""
        x0, y0, x1, y1 = self.sel
        lifted = {k: v for k, v in self.grid.items() if self.in_sel(k)}
        base = {k: v for k, v in self.grid.items() if k not in lifted}
        st = self.start if self.start and self.in_sel(self.start) and self.start[0] + 3 <= x1 else None
        go = self.goal if self.goal and self.in_sel(self.goal) else None
        self.move = dict(at=c, sel=self.sel, lifted=lifted, base=base, start=st, goal=go, d=(0, 0), saved=False)

    def move_to(self, c):
        m = self.move
        x0, y0, x1, y1 = m["sel"]
        dx = min(max(c[0] - m["at"][0], L.X_MIN - x0), L.X_MAX - x1)  # stays on the board
        dy = min(max(c[1] - m["at"][1], L.Y_MIN - y0), L.Y_MAX - y1)
        if (dx, dy) == m["d"]:
            return
        if not m["saved"]:
            self.push_undo()
            m["saved"] = True
        m["d"] = dx, dy
        self.image = None
        self.grid = {**m["base"], **{(x + dx, y + dy): k for (x, y), k in m["lifted"].items()}}
        if m["start"]:
            self.start = m["start"][0] + dx, m["start"][1] + dy
        if m["goal"]:
            self.goal = m["goal"][0] + dx, m["goal"][1] + dy
        self.sel = x0 + dx, y0 + dy, x1 + dx, y1 + dy
        self.changed()

    def clear_sel(self):
        """Deletes everything selected, including the start and the goal if fully inside the selection."""
        if not self.sel:
            return
        self.begin_move((0, 0))
        m, self.move = self.move, None
        if m["lifted"] or m["start"] or m["goal"]:
            self.push_undo()
            self.grid, self.image = m["base"], None
            self.start = None if m["start"] else self.start
            self.goal = None if m["goal"] else self.goal
            self.changed()
        self.sel = None

    def changed(self):
        self.tiles = self.surf = None

    def paint(self, c, kind):
        if not in_bounds(c) or c in self.reserved():
            return
        if kind is None:
            self.grid.pop(c, None)
        else:
            self.grid[c] = kind
        self.changed()

    def paint_line(self, a, b, kind):
        n = max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1)
        for i in range(n + 1):
            self.paint((round(a[0] + (b[0] - a[0]) * i / n), round(a[1] + (b[1] - a[1]) * i / n)), kind)

    def click_grid(self, c):
        kind = None if self.mode == "erase" else self.tool
        if kind == "start":
            x = min(max(c[0], L.X_MIN), L.X_MAX - 3)
            self.start = (x, c[1])
            for i in range(4):
                self.grid.pop((x + i, c[1]), None)
        elif kind == "goal":
            self.goal = c
            self.grid.pop(c, None)
        elif self.mode == "fill":
            self.image = None
            L.flood_fill(self.grid, c, kind, lambda d: in_bounds(d) and d not in self.reserved())
        else:
            self.image = None
            self.paint(c, kind)
            self.drag, self.last = kind or "", c
        self.changed()

    def level_cells(self):
        res = self.reserved()
        return {c: k for c, k in self.grid.items() if c not in res and in_bounds(c)}

    def wire(self):
        """Wire runs, and wire cells with no block next to them (as on save)."""
        g = self.level_cells()
        return L.wire_chunks([c for c, k in g.items() if k == "wire"], {c for c, k in g.items() if k != "wire"})

    def percent(self, g):
        return round((L.fullness(g) + 10) * 100 / L.FULLNESS_LIMIT)  # +10 = the goal

    def alert(self, text, title=None, buttons=("OK",)):
        """System dialog; blocks the editor. Returns the button number: Enter = first, Esc and X = last."""
        self.drag = self.sel_from = self.move = self.resize = None  # the mouse release goes to the dialog, not to the editor
        self.panning = False
        self.draw()
        with warnings.catch_warnings():  # a parent window keeps the dialog on top; pygame warns that this will change someday
            warnings.simplefilter("ignore", DeprecationWarning)
            parent = pygame.Window.from_display_module()
        return pygame.display.message_box(title or tr("Warning"), text, "warn", parent, buttons, 0, len(buttons) - 1)

    def state(self):
        return dict(self.grid), self.start, self.goal, self.board

    def dirty(self):
        """Are there unsaved changes."""
        return bool(self.grid or self.start or self.goal) and (self.grid, self.start, self.goal, self.board) != self.saved

    def can_quit(self):
        """With unsaved changes asks: save, don't save or stay."""
        if not self.dirty():
            return True
        n = self.alert(tr("The level has unsaved changes. Save it before closing?"), tr("Unsaved level"),
                       (tr("Save"), tr("Don't save"), tr("Cancel")))
        return self.do_save() if n == 0 else n == 1

    def do_save(self):
        """Returns whether the level was saved."""
        g = self.level_cells()
        try:
            if self.start and not (in_bounds(self.start) and self.start[0] + 3 <= L.X_MAX) or self.goal and not in_bounds(self.goal):
                raise ValueError("The start or the goal is outside the board.")
            xml = L.build_xml(g, self.start, self.goal)
            path = L.save(self.text["name"], xml)
            self.saved = self.state()
            n = xml.count("<block") - xml.count("subElementName")
            pct = self.percent(g)
            self.msg = tr("Saved {} ({} blocks, {} cells), fullness {}%", os.path.basename(path), n, len(g), pct)
            problems = []
            if pct > 100:
                problems.append(tr("The level is {}% full. The game won't let you publish it.", pct))
            skipped = self.wire()[1]
            if skipped:
                problems.append(tr("Skipped {} wire cells that touch no block.", len(skipped)))
            if problems:
                self.alert("\n".join(problems), tr("Saved, with a warning"))
            return True
        except (ValueError, OSError) as e:
            self.msg = ""
            # ValueError carries a template, e.g. ("Level “{}” already exists...", name)
            self.alert(tr(*e.args) if isinstance(e, ValueError) else str(e), tr("Level not saved"))
            return False

    def convert(self, surf, board):
        """Image to cells for a given board: (cells, size). Up to 80x80 pixels without enlarging (1 pixel = 1 cell)."""
        w, h = surf.get_size()
        cols, rows = L.board_size(board)
        s = min(cols / w, rows / h)
        if max(w, h) <= L.MAX_SIDE:
            s = min(s, 1)
        nw, nh = max(1, round(w * s)), max(1, round(h * s))
        px = L.downsample(pygame.image.tobytes(surf, "RGBA"), w, h, nw, nh)
        return L.image_to_cells(px), (nw, nh)

    def normalize(self, surf):
        """Enlarged pixel art goes back to 1 pixel = 1 cell; any other image stays as it was."""
        surf = surf.convert_alpha()
        w, h = surf.get_size()
        data = pygame.image.tobytes(surf, "RGBA")
        if not any(data[3::4]):  # a clipboard BMP may have zero alpha: treat it as opaque
            surf = surf.convert()
            data = pygame.image.tobytes(surf, "RGBA")
        grid = max(w, h) > L.MAX_SIDE and L.find_grid(data, w, h)
        if not grid:
            return surf
        s, ox, oy = grid
        ox, oy = (o - s if o >= s * 0.4 else o for o in (ox, oy))  # a cropped outer cell stays if most of it is visible
        nw, nh = round((w - ox) / s), round((h - oy) / s)
        if max(nw, nh) > L.MAX_SIDE:
            return surf
        px = L.downsample(data, w, h, nw, nh, ox, oy, s, s)
        return pygame.image.frombytes(bytes(v for row in px for p in row for v in p), (nw, nh), "RGBA")

    def pick_board(self, surf):
        """Smallest board on which the image keeps its details; a larger one only within the game's fullness limit."""
        w, h = surf.get_size()
        default = L.board(72, 37)
        if w <= 72 and h <= 37:
            return default
        fit = lambda s: L.board(*(min(max(round(v * s), L.MIN_SIDE), L.MAX_SIDE) for v in (w, h)))
        if max(w, h) <= L.MAX_SIDE:
            return fit(1)
        lo, hi = min(72 / w, 37 / h), L.MAX_SIDE / max(w, h)
        boards = [default] + [fit(lo + (hi - lo) * t) for t in (1 / 3, 2 / 3, 1)]
        tries = [(b, *self.convert(surf, b)) for b in boards]
        ref, rsize = max(tries, key=lambda t: t[2][0] * t[2][1])[1:]
        best = tries[0]
        for t in tries:
            if t is not best and (t[2] == best[2] or self.percent(t[1]) > 100):
                continue
            best = t
            if L.agreement(t[1], t[2], ref, rsize) >= DETAIL_OK:
                break
        return best[0]

    def load_image(self, get_surf):
        """Turns an image into cells (keeping proportions), the background stays empty. get_surf returns a Surface or None."""
        try:
            surf = get_surf()
        except (pygame.error, OSError, ValueError, struct.error) as e:
            self.alert(tr("Can't load the image: {}", e))
            return
        if surf is None:
            self.alert(tr("No image on the clipboard. Take a screenshot (Win+Shift+S) or drop a file on the window."))
            return
        surf = self.normalize(surf)
        self.place_image(self.pick_board(surf), surf)

    def place_image(self, board, surf=None):
        """Puts the image (or the last pasted one) on a board of the given size."""
        surf = surf or self.image
        cells, (nw, nh) = self.convert(surf, board)
        self.push_undo()
        self.set_board(board)
        self.image = surf
        ox, oy = (COLS - nw) // 2, (ROWS - nh) // 2
        self.grid = {(L.X_MIN + ox + x, L.Y_MAX - oy - y): k for (x, y), k in cells.items()}
        self.changed()
        pct = self.percent(self.level_cells())
        self.msg = tr("Image: {}x{} cells on a {}x{} board, fullness {}%", nw, nh, COLS, ROWS, pct)
        if pct > 100:
            self.alert(tr("The image fills the level to {}%, over the game limit. Simplify the image or use a smaller board.", pct))

    def get_tiles(self):
        """Blocks after merging: (x0, y0, w, h, kind). Wire as runs."""
        if self.tiles is None:
            self.tiles = []
            g = self.level_cells()
            self.pct = self.percent(g)
            self.wires = self.wire()[0]
            for kind, info in L.KINDS.items():
                cells = [c for c, k in g.items() if k == kind]
                if cells and info["pieces"]:
                    self.tiles += [(x0, y0, fp[0], fp[1], kind) for x0, y0, _, fp in L.tile(cells, info["pieces"])]
            for _, run in self.wires:
                xs, ys = [c[0] for c in run], [c[1] for c in run]
                self.tiles.append((min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, "wire"))
        return self.tiles

    # --- drawing ---
    def rect_px(self, x0, y0, w, h):
        x, y = cam.px(x0, y0 + h)
        r, b = cam.px(x0 + w, y0)
        return pygame.Rect(x, y, r - x, b - y)

    def zone(self, x0, y0, w, h, color):
        r = self.rect_px(x0, y0, w, h)
        if r.colliderect(cam.view):
            s = pygame.Surface(r.size, pygame.SRCALPHA)
            s.fill((*color, 50))
            self.screen.blit(s, r)
            pygame.draw.rect(self.screen, color, r, 1)

    def draw_spikeball(self, c):
        cx, cy = self.rect_px(*c, 1, 1).center
        r = cam.z * 0.3
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.line(self.screen, (60, 60, 60), (cx, cy), (cx + math.cos(a) * cam.z * 0.48, cy + math.sin(a) * cam.z * 0.48), 2)
        pygame.draw.circle(self.screen, (120, 120, 120), (cx, cy), r)
        pygame.draw.circle(self.screen, (60, 60, 60), (cx, cy), r, 1)

    def draw_wire(self, rz, run):
        """Zigzag of wire along the side of the cell that touches the block."""
        s = L.rot((0, -1), rz)
        for c in run:
            r = self.rect_px(*c, 1, 1)
            if s[1]:  # lying or hanging: horizontal wire at the bottom/top edge
                y = r.bottom - cam.z * 0.3 if s[1] < 0 else r.top + cam.z * 0.3
                pts = [(r.left + i * cam.z / 4, y + (cam.z * 0.18 if i % 2 else -cam.z * 0.18)) for i in range(5)]
            else:  # at the side: vertical wire
                x = r.right - cam.z * 0.3 if s[0] > 0 else r.left + cam.z * 0.3
                pts = [(x + (cam.z * 0.18 if i % 2 else -cam.z * 0.18), r.top + i * cam.z / 4) for i in range(5)]
            pygame.draw.lines(self.screen, (40, 40, 40), False, pts, 2)

    def board_surface(self):
        """The board as an image with 1 pixel = 1 cell; drawing only scales it up, so zooming is smooth."""
        if self.surf is None:
            self.surf = pygame.Surface((COLS, ROWS))
            self.surf.fill(T["grid"])
            self.marks = []
            for (x, y), k in self.grid.items():
                if in_bounds((x, y)):
                    self.surf.set_at((x - L.X_MIN, L.Y_MAX - y), COLOR[k])
                    if k in ("wire", "spike"):
                        self.marks.append((x, y, k))
        return self.surf

    def draw_editor_view(self):
        scr, g, v = self.screen, grid_rect(), cam.view
        surf = self.board_surface()
        (x0, y1), (x1, y0) = to_cell(*v.topleft), to_cell(*v.bottomright)  # only visible cells
        x0, x1, y0, y1 = max(x0, L.X_MIN), min(x1, L.X_MAX), max(y0, L.Y_MIN), min(y1, L.Y_MAX)
        if x0 <= x1 and y0 <= y1:
            r = self.rect_px(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
            part = surf.subsurface((x0 - L.X_MIN, L.Y_MAX - y1, x1 - x0 + 1, y1 - y0 + 1))
            scr.blit(pygame.transform.scale(part, r.size), r)
            for x, y, k in self.marks:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    q = self.rect_px(x, y, 1, 1)
                    if k == "wire":  # so wire stands out from dark blocks
                        pygame.draw.line(scr, (230, 230, 230), (q.left + 3, q.centery), (q.right - 3, q.centery), 1)
                    else:
                        pygame.draw.circle(scr, (60, 60, 60), q.center, q.w // 3)
        # thick lines every 5 cells from the left and bottom, drawn last so thin lines do not cross them
        a, b = max(g.left, v.left), min(g.right, v.right)
        c, d = max(g.top, v.top), min(g.bottom, v.bottom)
        lines = [(i % 5 == 0, (x, c), (x, d)) for i in range(COLS + 1) for x in (cam.px(L.X_MIN + i, 0)[0],) if v.left <= x <= v.right] + \
                [(j % 5 == 0, (a, y), (b, y)) for j in range(ROWS + 1) for y in (cam.px(0, L.Y_MIN + j)[1],) if v.top <= y <= v.bottom]
        for thick, p, q in sorted(lines):
            if thick or cam.z >= 4:
                pygame.draw.line(scr, T["thick"] if thick else T["thin"], p, q)
        if self.preview:
            for x0, y0, w, h, _ in self.get_tiles():
                pygame.draw.rect(scr, T["mark"], self.rect_px(x0, y0, w, h), 2)
        if self.start:
            x, y = self.start
            self.zone(x, y + 1, 4, 4, (80, 220, 80))
            scr.fill(COLOR["start"], self.rect_px(x, y, 4, 1))
            if cam.z >= 14:
                t = self.small.render("START", True, (0, 0, 0))
                scr.blit(t, t.get_rect(center=self.rect_px(x, y, 4, 1).center))
        if self.goal:
            x, y = self.goal
            self.zone(x - 2, y + 1, 4, 4, (250, 215, 0))
            scr.fill(COLOR["goal"], self.rect_px(x, y, 1, 1))

    def draw_game_view(self):
        """Roughly as in the game: sky, no grid, blocks merged as on save."""
        scr = self.screen
        g = grid_rect()
        vis = g.clip(cam.view)
        for y in range(vis.top, vis.bottom):
            t = (y - g.top) / g.h
            pygame.draw.line(scr, [round(a + (b - a) * t) for a, b in zip(SKY_TOP, SKY_BOTTOM)], (vis.left, y), (vis.right - 1, y))
        for x0, y0, w, h, kind in self.get_tiles():
            r = self.rect_px(x0, y0, w, h)
            if not r.colliderect(cam.view):
                continue
            if kind == "spike":
                self.draw_spikeball((x0, y0))
            elif kind != "wire":
                scr.fill(COLOR[kind], r)
                pygame.draw.rect(scr, darker(COLOR[kind]), r, 2)
                if kind == "wood":  # wood grain
                    for i in range(1, 3):
                        yy = r.top + r.h * i // 3
                        pygame.draw.line(scr, darker(COLOR[kind], 0.85), (r.left + 3, yy), (r.right - 4, yy), 1)
        for rz, run in self.wires:
            self.draw_wire(rz, run)
        if self.start:
            r = self.rect_px(*self.start, 4, 1)
            scr.fill((150, 150, 150), r.inflate(0, -int(cam.z) // 3).move(0, -int(cam.z) // 6))
            pygame.draw.rect(scr, (90, 90, 90), r.inflate(0, -int(cam.z) // 3).move(0, -int(cam.z) // 6), 2)
        if self.goal:
            r = self.rect_px(*self.goal, 1, 1)
            scr.fill((110, 110, 110), r)
            pygame.draw.rect(scr, (70, 70, 70), r, 2)
            pole = r.centerx, r.top
            pygame.draw.line(scr, (60, 60, 60), pole, (pole[0], pole[1] - cam.z * 3), 3)
            pygame.draw.polygon(scr, (220, 30, 30), [(pole[0], pole[1] - cam.z * 3), (pole[0] - cam.z * 1.4, pole[1] - cam.z * 2.6),
                                                     (pole[0], pole[1] - cam.z * 2.2)])

    def draw(self):
        scr = self.screen
        scr.fill(T["bg"])
        scr.set_clip(cam.view)
        if self.game_view:
            self.draw_game_view()
        else:
            self.draw_editor_view()
        real = pygame.mouse.get_pos() if pygame.mouse.get_focused() else (-1, -1)
        mx, my = self.mouse = (-1, -1) if self.settings else real
        hover = to_cell(mx, my)
        hover = hover if in_bounds(hover) and cam.view.collidepoint(mx, my) else None
        edges = self.resize[0] if self.resize else edges_at((mx, my))
        if self.sel:
            r = self.rect_px(self.sel[0], self.sel[1], self.sel[2] - self.sel[0] + 1, self.sel[3] - self.sel[1] + 1)
            pygame.draw.rect(scr, (0, 0, 0), r.inflate(2, 2), 3)
            pygame.draw.rect(scr, (90, 200, 255), r, 2)
        g = grid_rect()
        for e, a, b in (("l", g.topleft, g.bottomleft), ("r", g.topright, g.bottomright),
                        ("t", g.topleft, g.topright), ("b", g.bottomleft, g.bottomright)):
            if e in edges:
                pygame.draw.line(scr, T["focus"], a, b, 4)
        if hover and not self.game_view and not (self.resize or self.panning or self.move or self.sel_from):
            r = self.rect_px(*hover, 1, 1)
            if not self.sel and self.mode == "brush" and (self.tool in ("start", "goal") or hover not in self.reserved()):  # what a click will place
                if self.tool == "start":
                    r = self.rect_px(min(max(hover[0], L.X_MIN), L.X_MAX - 3), hover[1], 4, 1)
                scr.fill(COLOR[self.tool], r)
            pygame.draw.rect(scr, (0, 0, 0), r.inflate(2, 2), 1)
            pygame.draw.rect(scr, (255, 255, 255), r, 1)
        pygame.draw.rect(scr, T["thick"], g.inflate(2, 2), 1)
        if self.resize:  # size next to the cursor while dragging an edge
            t = f"{COLS} x {ROWS}"
            r = pygame.Rect(mx + 16, my + 16, self.font.size(t)[0] + 16, 26).clamp(cam.view)
            pygame.draw.rect(scr, T["on"], r, border_radius=3)
            self.write(t, T["on_text"], center=r.center)
        scr.set_clip(None)
        if edges != self.cursor:
            self.cursor = edges
            pygame.mouse.set_cursor(getattr(pygame, "SYSTEM_CURSOR_" + CURSORS.get(edges, "ARROW")))
        self.draw_side()
        self.draw_status(hover)
        caption = f"{self.text['name']}{'*' if self.dirty() else ''} - UCH level maker"
        if pygame.display.get_caption()[0] != caption:
            pygame.display.set_caption(caption)
        self.mouse = real
        if self.settings:
            self.draw_settings()
        pygame.display.flip()

    def draw_status(self, hover):
        scr, v = self.screen, cam.view
        bar = pygame.Rect(0, v.bottom, scr.get_width(), STATUS)
        scr.fill(T["panel"], bar)
        pygame.draw.line(scr, T["hair"], bar.topleft, bar.topright)
        if self.bottom:
            pygame.draw.line(scr, T["hair"], bar.bottomleft, bar.bottomright)
        r = pygame.Rect(MARGIN, 0, 20, 20)
        r.centery = bar.centery
        if self.mode != "erase":  # the color being drawn with
            scr.fill(COLOR[self.tool], r)
            pygame.draw.rect(scr, T["border"], r, 1)
        else:
            self.icon("erase", r.center, T["text"])
        x = r.right + 8
        parts = [(tr("Eraser") if self.mode == "erase" else label(self.tool), "text")]
        if self.mode != "erase":
            parts.append((tr(MODES[self.mode]), "muted"))
        parts.append((f"{COLS} x {ROWS}", "muted"))
        if hover:
            parts.append((tr("cell x={} y={}", *hover), "muted"))
        if self.preview or self.game_view:
            n = len(self.get_tiles())
            parts.append((tr("merged blocks: {}, fullness {}%", n, self.pct), "muted"))
        for text, color in parts:
            self.write(text, T[color], midleft=(x, bar.centery))
            x += self.font.size(text)[0] + 18

    # --- controls ---
    def hot(self, r):
        return r.collidepoint(self.mouse)

    def icon(self, name, center, color):
        """16x16 icon, drawn 4 times larger and scaled down so it is smooth."""
        key = name, color
        if key not in self.icons:
            big = pygame.Surface((64, 64), pygame.SRCALPHA)
            big.fill((*color, 0))
            for line in ICONS[name]:
                if isinstance(line[0], tuple):
                    pts = [(x * 4, y * 4) for x, y in line]
                    pygame.draw.lines(big, color, False, pts, 6)
                    for p in pts:
                        pygame.draw.circle(big, color, p, 3)
                else:
                    pygame.draw.circle(big, color, (line[0] * 4, line[1] * 4), line[2] * 4)
            self.icons[key] = pygame.transform.smoothscale(big, (16, 16))
        self.screen.blit(self.icons[key], self.icons[key].get_rect(center=center))

    def write(self, text, color, font=None, **at):
        font = font or self.font
        t = font.render(text, True, color)
        r = t.get_rect(**at)
        if not any(k.startswith("top") for k in at):  # the middle of the capitals goes to the middle of the row, not the whole line with descenders
            r.y += round(r.h / 2 - font.get_ascent() + font.metrics("H")[0][3] / 2)
        self.screen.blit(t, r)

    def button(self, key, r, text, hint="", accent=False, enabled=True):
        """Plain button; accent = yellow, something waits for this action."""
        fill = T["accent"] if accent else T["hover"] if enabled and self.hot(r) else T["btn"]
        color = T["accent_text"] if accent else T["text"] if enabled else T["off"]
        pygame.draw.rect(self.screen, fill, r, border_radius=3)
        if accent and self.hot(r):
            pygame.draw.rect(self.screen, T["text"], r, 1, border_radius=3)
        if hint:
            self.write(text, color, midleft=(r.x + 10, r.centery))
            self.write(hint, color if accent or not enabled else T["muted"], self.small, midright=(r.right - 10, r.centery))
        else:
            self.write(text, color, self.small, center=r.center)
        self.buttons[key] = r

    def command(self, key, r, text, hint="", enabled=True, color=None):
        """Command with an icon, no background; highlighted under the mouse."""
        color = color or T["text"]
        if enabled and self.hot(r):
            pygame.draw.rect(self.screen, T["hover"], r.inflate(10, 0), border_radius=3)
        self.icon(key[0], (r.x + 9, r.centery), color if enabled else T["off"])
        self.write(text, color if enabled else T["off"], midleft=(r.x + 26, r.centery))
        self.write(hint, T["muted"] if enabled else T["off"], self.small, midright=(r.right, r.centery))
        self.buttons[key] = r

    def toggle(self, key, r, text, hint, on):
        """Toggle with a check mark."""
        if self.hot(r):
            pygame.draw.rect(self.screen, T["hover"], r.inflate(8, 0), border_radius=3)
        b = pygame.Rect(r.x + 1, r.centery - 8, 16, 16)
        pygame.draw.rect(self.screen, T["on"] if on else T["field"], b, border_radius=2)
        pygame.draw.rect(self.screen, T["on"] if on else T["border"], b, 1, border_radius=2)
        if on:
            self.icon("check", b.center, T["on_text"])
        self.write(text, T["text"], midleft=(b.right + 7, r.centery))
        self.write(hint, T["muted"], self.small, midright=(r.right, r.centery))
        self.buttons[key] = r

    def segments(self, rect, parts):
        """One strip to choose one thing from: (key, text, shortcut, selected). With a shortcut: icon above the text."""
        pygame.draw.rect(self.screen, T["btn"], rect, border_radius=4)
        for i, (key, text, hint, on) in enumerate(parts):
            x = rect.x + rect.w * i // len(parts)
            r = pygame.Rect(x, rect.y, rect.x + rect.w * (i + 1) // len(parts) - x, rect.h)
            if on or self.hot(r):
                pygame.draw.rect(self.screen, T["on" if on else "hover"], r.inflate(-4, -4), border_radius=3)
            color = T["on_text" if on else "text"]
            if hint:
                self.icon(key[1], (r.centerx, r.y + 16), color)
                self.write(text, color, self.small, midbottom=(r.centerx, r.bottom - 6))
                self.write(hint, color if on else T["muted"], self.small, topright=(r.right - 7, r.y + 5))
            else:
                self.write(text, color, center=r.center)
            self.buttons[key] = r

    def field(self, key, r, text):
        """Text field; when the text is too long its end is shown."""
        pygame.draw.rect(self.screen, T["field"], r, border_radius=3)
        pygame.draw.rect(self.screen, T["focus"] if self.focus == key else T["border"], r, 1, border_radius=3)
        inner, tw = r.inflate(-14, -4), self.font.size(text)[0]
        x = inner.x - max(tw + 2 - inner.w, 0) if self.focus == key else inner.x
        self.screen.set_clip(inner.inflate(4, 0))
        self.write(text, T["text"], midleft=(x, r.centery))
        if self.focus == key and pygame.time.get_ticks() // 500 % 2:
            pygame.draw.line(self.screen, T["text"], (x + tw + 1, r.centery - 8), (x + tw + 1, r.centery + 7))
        self.screen.set_clip(None)
        self.buttons[("field", key)] = r

    def size_field(self, k, x, y):
        """Size field with arrows inside."""
        r = pygame.Rect(x, y, 62, 30)
        self.field(k, r, self.text[k])
        self.buttons[("field", k)] = pygame.Rect(x, y, 44, 30)
        for n, ay in ((1, y + 1), (-1, y + 15)):
            a = pygame.Rect(x + 44, ay, 17, 14)
            if self.hot(a):
                self.screen.fill(T["hover"], a)
            cx, cy = a.center
            pygame.draw.polygon(self.screen, T["text"], [(cx - 4, cy + 2 * n), (cx + 4, cy + 2 * n), (cx, cy - 2 * n)])
            self.buttons[("nudge", k, n)] = a

    def wrapped(self, text, color, x, y, w):
        """Text wrapped to width w; returns y below it."""
        line = ""
        for wd in text.split(" "):
            if line and self.small.size(line + wd)[0] > w:
                self.write(line, color, self.small, topleft=(x, y))
                y, line = y + 18, ""
            line += wd + " "
        self.write(line, color, self.small, topleft=(x, y))
        return y + 18

    def draw_side(self):
        """Draws the panel and remembers its buttons; returns the bottom of the message (it must stay above the settings button)."""
        scr, w, v = self.screen, SIDE - 2 * PAD, cam.view
        area = pygame.Rect(0, v.bottom + STATUS, scr.get_width(), BOTTOM_H) if self.bottom else pygame.Rect(v.right, 0, SIDE, v.h)
        scr.fill(T["panel"], area)
        if not self.bottom:
            pygame.draw.line(scr, T["hair"], area.topleft, area.bottomleft)
        x0, y = area.x + PAD, area.y + 8
        top = y
        keys = self.keys[lang.current]
        self.buttons = {}

        def group(column):
            """New group: below a line, or in the next column of a panel below the board, if column."""
            nonlocal x0, y
            if self.bottom and column:
                x0, y = x0 + SIDE + 10, top + 4
            else:
                pygame.draw.line(scr, T["hair"], (x0, y + 8), (x0 + w - 1, y + 8))
                y += 17

        for i, (k, t) in enumerate((("colors", tr("Colors")), ("items", tr("Items")))):  # tabs
            r = pygame.Rect(x0 + i * (w // 2), y, w // 2, 30)
            on = self.tab == k
            self.write(t, T["text" if on or self.hot(r) else "muted"], center=(r.centerx, r.centery - 1))
            pygame.draw.line(scr, T["hair"], (r.left, r.bottom - 1), (r.right, r.bottom - 1))
            if on:
                scr.fill(T["text"], (r.left, r.bottom - 2, r.w, 2))
            self.buttons[("tab", k)] = r
        y += 38
        if self.tab == "colors":  # swatches: tiles on a 1 px grid
            scr.fill(T["border"], (x0, y, 211, 211))
            for i, k in enumerate(COLOR_KINDS):
                r = pygame.Rect(x0 + 1 + i % 6 * 35, y + 1 + i // 6 * 35, 34, 34)
                scr.fill(COLOR[k], r)
                self.buttons[("tool", k)] = r
            for k in COLOR_KINDS:
                r = self.buttons[("tool", k)]
                if self.hot(r) and k != self.tool:
                    pygame.draw.rect(scr, (255, 255, 255), r, 2)
            if self.tool in COLOR_KINDS:  # a white frame with a black one inside, visible on every color
                r = self.buttons[("tool", self.tool)]
                pygame.draw.rect(scr, (255, 255, 255), r.inflate(8, 8), 4)
                pygame.draw.rect(scr, (0, 0, 0), r, 1)
                pygame.draw.rect(scr, (0, 0, 0), r.inflate(10, 10), 1)
        else:
            for i, t in enumerate(ITEMS):
                r = pygame.Rect(x0, y + i * 40, w, 36)
                on = t == self.tool
                if on or self.hot(r):
                    pygame.draw.rect(scr, T["on" if on else "hover"], r, border_radius=3)
                sw = pygame.Rect(r.x + 8, r.y + 8, 20, 20)
                scr.fill(COLOR[t], sw)
                pygame.draw.rect(scr, T["border"], sw, 1)
                self.write(label(t), T["on_text" if on else "text"], midleft=(sw.right + 10, r.centery))
                self.write(str(i + 1), T["on_text" if on else "muted"], self.small, midright=(r.right - 10, r.centery))
                self.buttons[("tool", t)] = r
        y += 211 + 12  # same height in both tabs
        if self.bottom:
            x0, y = x0 + SIDE + 10, top + 4
        self.segments(pygame.Rect(x0, y, w, 52), [(("mode", m), t, keys[m], self.mode == m) for m, t in (
            ("brush", tr("Brush")), ("erase", tr("Eraser")), ("fill", tr("Fill")))])
        y += 58
        for i, (k, t, on) in enumerate((("preview", tr("Blocks"), self.preview), ("game", tr("Game view"), self.game_view))):
            self.toggle((k,), pygame.Rect(x0 + i * 96, y, 115 if i else 84, 28), t, keys[k], on)
        y += 28
        group(False)
        self.write(tr("Board, up to {}x{}", L.MAX_SIDE, L.MAX_SIDE), T["muted"], self.small, topleft=(x0, y))
        if self.image:  # fits the board to the pasted image
            self.button(("auto",), pygame.Rect(x0 + w - 64, y - 6, 64, 22), tr("Auto"))
        y += 20
        self.size_field("w", x0, y)
        self.write("x", T["muted"], center=(x0 + 70, y + 15))
        self.size_field("h", x0 + 78, y)
        waiting = self.typed_size() != [COLS, ROWS]
        self.button(("apply",), pygame.Rect(x0 + 146, y, w - 146, 30), tr("Apply"), accent=waiting, enabled=waiting)
        y += 30
        group(True)
        for k, t, hint, enabled in (("undo", tr("Undo"), "Ctrl+Z", bool(self.undo)), ("redo", tr("Redo"), "Ctrl+Y", bool(self.redo)),
                                    ("paste", tr("Paste image"), "Ctrl+V", True), ("delete", tr("Delete selection"), "Del", bool(self.sel)),
                                    ("clear", tr("Clear everything"), "", True)):
            self.command((k,), pygame.Rect(x0, y, w, 27), t, hint, enabled, T["danger"] if k == "clear" else None)
            y += 28
        group(True)
        self.write(tr("Level name"), T["muted"], self.small, topleft=(x0, y))
        y += 20
        self.field("name", pygame.Rect(x0, y, w, 30), self.text["name"])
        y += 36
        self.button(("save",), pygame.Rect(x0, y, w, 34), tr("Save"), "Ctrl+S", accent=self.dirty())
        y += 42
        end = self.wrapped(self.msg, T["msg"], x0, y, w)
        self.command(("settings",), pygame.Rect(x0, area.bottom - 36, w, 28), tr("Settings"))
        return end

    def draw_settings(self):
        """Window in the middle: theme, language and controls. While open, only its buttons work."""
        scr, keys, w, pad = self.screen, self.keys[lang.current], 300, 20
        mouse = [(tr("Draw"), tr("left button")), (tr("Select and move"), tr("right button")), (tr("Zoom"), tr("wheel")),
                 (tr("Pan the view"), tr("hold the wheel")), (tr("Resize the board"), tr("drag a grid edge")),
                 (tr("Paste an image file"), tr("drop it here"))]
        tools = [("brush", tr("Brush")), ("erase", tr("Eraser")), ("fill", tr("Fill")), ("preview", tr("Blocks")), ("game", tr("Game view"))]
        fixed = [(tr("Items"), f"1-{len(ITEMS)}"), (tr("Undo"), "Ctrl+Z"), (tr("Redo"), "Ctrl+Y"), (tr("Paste image"), "Ctrl+V"),
                 (tr("Save"), "Ctrl+S"), (tr("Apply size"), "Enter"), (tr("Delete selection"), "Delete"), (tr("Deselect"), "Esc")]
        wide = scr.get_width() >= 2 * w + 130
        left, right, head = 112 + 22 * len(mouse), 48 + 28 * len(tools) + 22 * len(fixed), 58
        box = self.box = pygame.Rect(0, 0, (2 * w + 30 if wide else w) + 2 * pad, head + (max(left, right) if wide else left + 14 + right) + 14)
        box.center = scr.get_rect().center
        dim = pygame.Surface(scr.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 120))
        scr.blit(dim, (0, 0))
        pygame.draw.rect(scr, T["panel"], box, border_radius=5)
        pygame.draw.rect(scr, T["border"], box, 1, border_radius=5)
        self.buttons = {}
        x, y = box.x + pad, box.y + head
        self.write(tr("Settings"), T["text"], self.big, midleft=(x, box.y + 30))
        r = pygame.Rect(box.right - pad - 28, box.y + 16, 28, 28)
        if self.hot(r):
            pygame.draw.rect(scr, T["hover"], r, border_radius=3)
        self.icon("close", r.center, T["text"])
        self.buttons[("close",)] = r

        def heading(text):
            nonlocal y
            self.write(text, T["text"], topleft=(x, y))
            pygame.draw.line(scr, T["hair"], (x, y + 22), (x + w - 1, y + 22))
            y += 28

        for what, parts in ((tr("Theme"), [(("theme", k), t, "", self.theme == k) for k, t in (("dark", tr("Dark")), ("light", tr("Light")))]),
                            (tr("Language"), [(("lang", k), t, "", lang.current == k) for k, t in (("pl", "Polski"), ("en", "English"))])):
            self.write(what, T["text"], midleft=(x, y + 16))
            self.segments(pygame.Rect(x + 100, y, w - 100, 32), parts)
            y += 40
        y += 4
        heading(tr("Mouse"))
        for what, how in mouse:
            self.write(what, T["text"], self.small, topleft=(x, y))
            self.write(how, T["muted"], self.small, topright=(x + w, y))
            y += 22
        if wide:
            x, y = x + w + 30, box.y + head
        else:
            y += 14
        heading(tr("Keys"))
        self.write(tr("Click a key to change it."), T["muted"], self.small, topleft=(x, y))
        y += 20
        for k, what in tools:
            self.write(what, T["text"], self.small, midleft=(x, y + 13))
            waiting = self.binding == k
            r = pygame.Rect(0, y, 116 if waiting else 30, 24)
            r.right = x + w
            pygame.draw.rect(scr, T["border"], r.move(0, 2), border_radius=4)  # side of the key cap
            pygame.draw.rect(scr, T["accent"] if waiting else T["hover" if self.hot(r) else "btn"], r, border_radius=4)
            self.write(tr("press a letter") if waiting else keys[k], T["accent_text" if waiting else "text"], self.small, center=r.center)
            self.buttons[("bind", k)] = r
            y += 28
        for what, how in fixed:
            self.write(what, T["text"], self.small, topleft=(x, y + 4))
            self.write(how, T["muted"], self.small, topright=(x + w, y + 4))
            y += 22

    # --- events ---
    def on_side_click(self, pos):
        for key, r in self.buttons.items():
            if not r.collidepoint(pos):
                continue
            self.set_focus(key[1] if key[0] == "field" else None)
            self.binding = key[1] if key[0] == "bind" else None
            if key[0] == "tab":
                self.tab = key[1]
            elif key[0] == "tool":
                self.pick_tool(key[1])
            elif key[0] == "mode":
                self.mode = key[1]
            elif key[0] == "theme":
                self.change_settings(key[1], lang.current)
            elif key[0] == "lang":
                self.change_settings(self.theme, key[1])
            elif key[0] in ("settings", "close"):
                self.settings = key[0] == "settings"
            elif key[0] == "nudge":
                self.nudge(key[1], key[2])
            elif key[0] == "apply":
                self.apply_size()
            elif key[0] == "auto":
                self.place_image(self.pick_board(self.image))
            elif key[0] == "delete":
                self.clear_sel()
            elif key[0] == "preview":
                self.preview = not self.preview
            elif key[0] == "game":
                self.game_view = not self.game_view
            elif key[0] == "undo":
                self.step(self.undo, self.redo)
            elif key[0] == "redo":
                self.step(self.redo, self.undo)
            elif key[0] == "paste":
                self.load_image(clipboard_image)
            elif key[0] == "save":
                self.do_save()
            elif key[0] == "clear":
                self.push_undo()
                self.grid, self.start, self.goal, self.sel, self.image = {}, None, None, None, None
                self.msg = tr("Cleared. Undo: Ctrl+Z")
                self.changed()
            return
        self.set_focus(None)

    def pick_tool(self, t):
        self.tool = t
        if self.mode == "erase":
            self.mode = "brush"

    def on_key(self, e):
        ctrl = e.mod & pygame.KMOD_CTRL
        action = {v: k for k, v in self.keys[lang.current].items()}.get(pygame.key.name(e.key).upper())
        if ctrl and e.key == pygame.K_s:
            self.set_focus(None)
            self.do_save()
        elif self.focus:
            if e.key == pygame.K_BACKSPACE:
                self.text[self.focus] = self.text[self.focus][:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.focus == "name":
                    self.set_focus(None)
                    self.do_save()
                else:
                    self.apply_size()
            elif e.key in (pygame.K_UP, pygame.K_DOWN) and self.focus != "name":
                self.nudge(self.focus, 1 if e.key == pygame.K_UP else -1)
            elif e.key == pygame.K_TAB and self.focus == "w":
                self.set_focus("h")
            elif e.key == pygame.K_ESCAPE:
                if self.focus in ("w", "h"):
                    self.text["w"], self.text["h"] = str(COLS), str(ROWS)
                self.set_focus(None)
        elif ctrl and e.key == pygame.K_z:
            self.step(self.undo, self.redo)
        elif ctrl and e.key == pygame.K_y:
            self.step(self.redo, self.undo)
        elif ctrl and e.key == pygame.K_v:
            self.load_image(clipboard_image)
        elif ctrl:
            pass
        elif action in MODES:
            self.mode = action
        elif action == "preview":
            self.preview = not self.preview
        elif action == "game":
            self.game_view = not self.game_view
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.apply_size()
        elif e.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and not self.busy():
            self.clear_sel()
        elif e.key == pygame.K_ESCAPE:
            self.sel = self.sel_from = self.move = None
        elif pygame.K_1 <= e.key < pygame.K_1 + len(ITEMS):
            self.pick_tool(ITEMS[e.key - pygame.K_1])
            self.tab = "items"

    def on_mouse_down(self, e):
        c = to_cell(*e.pos)
        if self.busy():
            pass  # second button during a drag
        elif not cam.view.collidepoint(e.pos):
            if e.button == 1:
                self.on_side_click(e.pos)
        elif e.button == 2:
            self.panning = True
        elif not in_bounds(c):
            self.set_focus(None)
            if e.button == 1 and edges_at(e.pos):
                self.resize = edges_at(e.pos), e.pos, self.board, cam.z, []
            elif e.button == 1:
                self.sel = None
        else:
            self.set_focus(None)
            if self.in_sel(c):
                self.begin_move(c)
            elif e.button == 3:
                self.sel_from = c
                self.select(c, c)
            elif self.sel:
                self.sel = None  # a click outside only deselects
            else:
                self.push_undo()
                self.click_grid(c)

    def handle(self, e):
        if self.settings:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.settings, self.binding = bool(self.binding), None  # first cancels changing a shortcut
            elif e.type == pygame.KEYDOWN and self.binding and pygame.K_a <= e.key <= pygame.K_z:
                self.rebind(pygame.key.name(e.key).upper())
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.settings = self.box.collidepoint(e.pos)  # a click outside closes it
                self.on_side_click(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 2, 3):
            self.on_mouse_down(e)
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 2:
            self.panning = False
        elif e.type == pygame.MOUSEBUTTONUP and e.button in (1, 3) and not self.panning:
            if self.move:  # whatever landed under the start or the goal disappears
                for c in self.reserved():
                    self.grid.pop(c, None)
            self.drag = self.sel_from = self.move = None
            if self.resize and e.button == 1:
                changed, self.resize = self.resize[2] != self.board, None
                if changed:
                    self.set_board(self.board)
        elif e.type == pygame.MOUSEMOTION and self.panning:
            cam.pan(*e.rel)
        elif e.type == pygame.MOUSEMOTION and self.resize:
            edges, start, b0, cell, saved = self.resize
            b = L.drag_edges(b0, edges, round((e.pos[0] - start[0]) / cell), round((start[1] - e.pos[1]) / cell))
            if b != self.board:
                if not saved:  # the whole drag is one undo step
                    self.push_undo()
                    saved.append(True)
                keep = self.resize
                self.set_board(b, keep_window=True)
                self.resize = keep
        elif e.type == pygame.MOUSEWHEEL:
            self.on_wheel(getattr(e, "precise_y", e.y), pygame.mouse.get_pos())
        elif e.type == pygame.MOUSEMOTION and (self.drag is not None or self.move or self.sel_from):
            x, y = to_cell(*e.pos)
            c = min(max(x, L.X_MIN), L.X_MAX), min(max(y, L.Y_MIN), L.Y_MAX)
            if self.move:
                self.move_to(c)
            elif self.sel_from:
                self.select(self.sel_from, c)
            else:
                self.paint_line(self.last, c, self.drag or None)
                self.last = c
        elif e.type == pygame.KEYDOWN:
            self.on_key(e)
        elif e.type == pygame.DROPFILE:
            self.load_image(lambda: pygame.image.load(e.file))
        elif e.type == pygame.TEXTINPUT and self.focus:
            t = self.text[self.focus] + e.text
            if self.focus == "name" and len(t) <= 40 or self.focus != "name" and t.isdecimal() and len(t) <= 3:
                self.text[self.focus] = t

    def run(self):
        clock = pygame.time.Clock()
        while True:
            dt = min(clock.tick(60) / 1000, 0.05)
            for e in pygame.event.get():
                if e.type != pygame.QUIT:
                    self.handle(e)
                elif self.can_quit():
                    return
            cam.update(dt)
            self.draw()


if __name__ == "__main__":
    Editor().run()
