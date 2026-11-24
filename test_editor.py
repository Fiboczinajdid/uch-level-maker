"""Tests of the editor window without a screen (mouse and keys). Run: python test_editor.py (or pytest)."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
import json
import re
import tempfile
import time

import pygame

import editor as E
import lang
import uch_level as L

E.SETTINGS = os.path.join(tempfile.mkdtemp(), "settings.json")  # keep real settings untouched

pygame.mouse.set_cursor = lambda *a: None  # no cursors without a screen
pygame.mouse.get_pos = lambda: (-50, -50)  # and the mouse sits at (0, 0), which is the corner of the grid

boxes = []  # dialogs that popped up: (title, text)
pygame.display.message_box = lambda title, text, *a: boxes.append((title, text))


def px(c):
    r = E.to_screen(*c)
    return r[0] + int(E.cam.z) // 2, r[1] + int(E.cam.z) // 2


def down(ed, c, b=1):
    ed.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=b, pos=px(c)))


def to(ed, c):
    ed.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=px(c)))


def up(ed, b=1):
    ed.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=b, pos=(0, 0)))


def drag(ed, a, b, button=1):
    down(ed, a, button), to(ed, b), up(ed, button)


def key(ed, k, mod=0):
    ed.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))


def click(ed, name):
    ed.draw()
    ed.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=ed.buttons[name].center))
    up(ed)


def write(ed, t):
    for ch in t:
        ed.handle(pygame.event.Event(pygame.TEXTINPUT, text=ch))


def test_eraser_button():
    ed = E.Editor()
    drag(ed, (0, 0), (4, 0))
    assert len(ed.grid) == 5
    drag(ed, (0, 0), (4, 0), 3)  # the right button does not erase
    assert len(ed.grid) == 5
    key(ed, pygame.K_ESCAPE)
    click(ed, ("mode", "erase"))
    drag(ed, (0, 0), (1, 0))
    assert set(ed.grid) == {(2, 0), (3, 0), (4, 0)}
    click(ed, ("tool", E.COLOR_KINDS[3]))  # choosing a color goes back to the brush
    down(ed, (0, 0)), up(ed)
    assert ed.grid[(0, 0)] == E.COLOR_KINDS[3]


def test_select_and_move():
    ed = E.Editor()
    ed.grid = {(0, 0): "color0", (1, 0): "color1", (5, 5): "color2", (3, 2): "color5"}
    ed.start, ed.goal = (0, -3), (9, 9)
    before = dict(ed.grid)
    drag(ed, (4, -3), (0, 0), 3)
    assert ed.sel == (0, -3, 4, 0)
    for button, back in ((1, False), (3, True)):  # dragged with the left or the right button
        drag(ed, (2, -1), (4, 1), button)
        assert ed.grid == {(2, 2): "color0", (3, 2): "color1", (5, 5): "color2"}  # (3, 2) overwritten
        assert ed.start == (2, -1) and ed.goal == (9, 9) and ed.sel == (2, -1, 6, 2)
        key(ed, pygame.K_z, pygame.KMOD_CTRL)  # one undo step for the whole move
        assert ed.grid == before and ed.start == (0, -3) and ed.sel is None
        drag(ed, (4, -3), (0, 0), 3)
    n = len(ed.undo)
    down(ed, (1, 0)), up(ed)  # a click without moving changes nothing
    assert ed.grid == before and len(ed.undo) == n
    down(ed, (15, 0)), up(ed)  # a click outside only deselects
    assert ed.sel is None and ed.grid == before


def test_move_stops_at_edge_and_delete():
    ed = E.Editor()
    ed.grid = {(0, 0): "color0"}
    drag(ed, (0, 0), (2, 0), 3)
    down(ed, (1, 0)), to(ed, (L.X_MAX, L.Y_MAX)), to(ed, (L.X_MIN, L.Y_MIN)), up(ed)
    assert ed.grid == {(L.X_MIN, L.Y_MIN): "color0"}  # dragging back and forth loses no cells
    key(ed, pygame.K_DELETE)
    assert ed.grid == {}


def test_size_fields():
    ed = E.Editor()
    ed.set_board(L.board(72, 37))
    ed.grid = {(35, 0): "color0", (0, 0): "color1"}
    click(ed, ("field", "w"))
    write(ed, "5x0")
    key(ed, pygame.K_TAB)
    write(ed, "999")
    key(ed, pygame.K_RETURN)
    assert (E.COLS, E.ROWS) == (50, 80) and ed.text["h"] == "80"  # letters rejected, max 80
    assert set(ed.level_cells()) == {(0, 0)} and len(ed.grid) == 2
    click(ed, ("field", "w"))
    key(ed, pygame.K_RETURN)  # an empty field changes nothing
    assert E.COLS == 50
    click(ed, ("field", "w"))
    write(ed, "3")
    n = len(ed.grid)
    down(ed, (0, 5)), up(ed)  # a click on the board draws, the size still waits for Apply
    assert E.COLS == 50 and ed.text["w"] == "3" and len(ed.grid) == n + 1
    click(ed, ("apply",))
    assert E.COLS == L.MIN_SIDE and ed.text["w"] == "10"
    for _ in range(3):  # size, drawing, size
        key(ed, pygame.K_z, pygame.KMOD_CTRL)
    assert (E.COLS, E.ROWS) == (72, 37)
    assert set(ed.level_cells()) == {(0, 0), (35, 0)}


def test_size_arrows():
    ed = E.Editor()
    for _ in range(3):
        click(ed, ("nudge", "w", 1))
    click(ed, ("nudge", "h", -1))
    assert (ed.text["w"], ed.text["h"]) == ("43", "39") and (E.COLS, E.ROWS) == (40, 40) and not ed.undo
    key(ed, pygame.K_RETURN)  # Enter = Apply, also without a cursor in the field
    assert (E.COLS, E.ROWS) == (43, 39) and len(ed.undo) == 1
    click(ed, ("field", "h"))
    key(ed, pygame.K_UP), key(ed, pygame.K_UP), key(ed, pygame.K_DOWN)
    key(ed, pygame.K_RETURN)
    assert (E.COLS, E.ROWS) == (43, 40)
    for _ in range(60):
        click(ed, ("nudge", "w", 1))
    assert ed.text["w"] == "80"  # stays within the limit
    n = len(ed.undo)
    click(ed, ("field", "w")), key(ed, pygame.K_ESCAPE)
    key(ed, pygame.K_RETURN)  # Esc brings back the current size
    assert E.COLS == 43 and len(ed.undo) == n


def test_settings_window():
    ed = E.Editor()
    ed.desk = (1600, 900)
    for size in ((80, 10), (10, 80), (40, 40)):  # the window fits for every board shape
        ed.set_board(L.board(*size))
        click(ed, ("settings",))
        ed.draw()
        assert set(ed.buttons) == {("theme", "dark"), ("theme", "light"), ("lang", "pl"), ("lang", "en"), ("close",)} | {("bind", k) for k in E.KEYS["pl"]}
        assert all(ed.screen.get_rect().contains(ed.box) and ed.box.contains(r) for r in ed.buttons.values()), size
        for t in (pygame.K_ESCAPE, None, (2, 2)):
            ed.settings = True
            if t == (2, 2):  # a click outside the window
                ed.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=t))
            else:
                key(ed, t) if t else click(ed, ("close",))
            assert not ed.settings
    click(ed, ("settings",))
    z = E.cam.target
    down(ed, (0, 0)), up(ed), wheel(ed, 3, px((0, 0))), key(ed, pygame.K_e), key(ed, pygame.K_g)
    assert not ed.grid and E.cam.target == z and ed.mode == "brush"  # the editor underneath does not react


def test_shortcuts():
    ed = E.Editor()
    for language, want in (("pl", "pgwki"), ("en", "beflg")):
        lang.current = language
        assert len(set(E.KEYS[language].values())) == len(E.KEYS[language])
        ed.mode, ed.preview, ed.game_view = "", False, False
        for ch, mode in zip(want, ("brush", "erase", "fill", "fill", "fill")):
            key(ed, ord(ch), pygame.KMOD_CTRL)
            key(ed, ord(ch))
            assert ed.mode == mode
        assert ed.preview and ed.game_view
    lang.current = "en"


def test_save_waits():
    ed = E.Editor()
    assert not ed.dirty()
    down(ed, (0, 0)), up(ed)
    assert ed.dirty()
    ed.draw()
    assert pygame.display.get_caption()[0] == "My level* - UCH level maker"
    ed.saved = ed.state()
    ed.draw()
    assert not ed.dirty() and pygame.display.get_caption()[0] == "My level - UCH level maker"


def test_change_shortcuts():
    ed = E.Editor()
    click(ed, ("settings",)), click(ed, ("bind", "game"))
    key(ed, pygame.K_5), key(ed, pygame.K_ESCAPE)  # a digit changes nothing, Esc cancels the change, not the window
    assert ed.settings and ed.binding is None and ed.keys == E.KEYS
    click(ed, ("bind", "game")), key(ed, pygame.K_f)  # taken letter: swap
    assert ed.keys["en"]["game"] == "F" and ed.keys["en"]["fill"] == "G" and ed.keys["pl"] == E.KEYS["pl"]
    click(ed, ("bind", "brush")), key(ed, pygame.K_x), click(ed, ("close",))
    key(ed, pygame.K_f), key(ed, pygame.K_g)
    assert ed.game_view and ed.mode == "fill"
    key(ed, pygame.K_x)
    assert ed.mode == "brush" and E.KEYS["en"]["brush"] == "B"  # defaults unchanged
    again = E.Editor()
    assert again.keys == ed.keys  # remembered
    good = dict(E.KEYS["en"], game="Z")
    for bad in (5, {"en": 5}, {"en": {}}, {"en": dict(good, game="B")}, {"en": dict(good, game="1")}, {"en": dict(good, game=["Z"])}):
        json.dump({"theme": "dark", "lang": "en", "keys": bad}, open(E.SETTINGS, "w"))
        assert E.Editor().keys == E.KEYS, bad  # broken shortcuts = defaults
    json.dump({"theme": "dark", "lang": "en"}, open(E.SETTINGS, "w"))  # a file from an older version
    assert E.Editor().keys == E.KEYS


def test_grid_squares_are_5x5():
    ed = E.Editor()
    ed.set_board(L.board(80, 80))
    ed.draw()
    assert E.cam.z == int(E.cam.z)
    g, z = E.grid_rect(), int(E.cam.z)
    thick = lambda p: ed.screen.get_at(p)[:3] == E.T["thick"]
    mid = z * 2 + z // 2
    xs = [i for i in range(81) if thick((g.x + i * z, g.y + mid))]
    ys = [j for j in range(81) if thick((g.x + mid, g.y + j * z))]
    assert xs == ys == list(range(0, 81, 5))  # 16 x 16 full squares, no leftovers at the edges


def test_window_fits_board():
    for desk in ((1920, 1080), (1600, 900)):
        for cols in range(10, 81, 5):
            for rows in range(10, 81, 5):
                cell, bottom, (w, h) = E.fit_window(cols, rows, desk)
                assert cell >= 5 and cols * cell + 2 * E.MARGIN <= w and rows * cell + 2 * E.MARGIN + E.STATUS <= h
                assert w <= desk[0] and h <= desk[1]
    # the panel (all buttons) fits the window and does not cover the board
    ed = E.Editor()
    ed.desk = (1920, 1080)
    for size in ((80, 80), (72, 37), (80, 12), (10, 80), (10, 10), (40, 60)):
        ed.set_board(L.board(*size))
        for ed.tab in ("colors", "items"):
            ed.draw()
            area, grid = ed.screen.get_rect(), E.cam.view
            assert grid.contains(E.grid_rect())
            assert all(area.contains(r) and not grid.colliderect(r) for r in ed.buttons.values()), size


def wheel(ed, n, pos):
    pygame.mouse.get_pos = lambda: pos  # a real wheel event has no position
    ed.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=n))
    pygame.mouse.get_pos = lambda: (-50, -50)


def settle():
    for _ in range(120):
        E.cam.update(1 / 60)


def test_wheel_zooms_only():
    ed = E.Editor()
    assert (E.COLS, E.ROWS) == (40, 40)  # the default size
    win, z0 = ed.screen.get_size(), E.cam.z
    pos = px((10, 5))
    before = E.cam.world(pos)
    wheel(ed, 3, pos)
    last = E.cam.z
    for _ in range(120):  # smooth: zoom grows bit by bit and the point under the cursor stays put
        E.cam.update(1 / 60)
        assert last <= E.cam.z <= last * 1.2
        now = E.cam.world(pos)
        assert abs(now[0] - before[0]) < 0.02 and abs(now[1] - before[1]) < 0.02
        last = E.cam.z
    assert E.cam.z > z0 and E.cam.z == int(E.cam.z)  # up = closer, equal cells at the end
    wheel(ed, -2, pos)
    settle()
    assert E.cam.z < last  # down = farther
    for n in (200, -200):
        wheel(ed, n, pos)
        settle()
        ed.draw()
    assert E.cam.z >= 2 and E.cam.view.contains(E.grid_rect())  # a zoomed out board is fully visible
    assert (E.COLS, E.ROWS) == (40, 40) and ed.screen.get_size() == win and not ed.undo  # grid and window unchanged


def test_zoomed_clicks_and_pan():
    ed = E.Editor()
    wheel(ed, 8, px((10, 5)))
    settle()
    down(ed, (10, 5)), up(ed)
    assert set(ed.grid) == {(10, 5)}
    a = E.cam.world((100, 100))
    ed.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=2, pos=(200, 200)))
    ed.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(150, 180), rel=(-50, -20)))
    ed.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=2, pos=(150, 180)))
    b = E.cam.world((50, 80))
    assert abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6 and len(ed.grid) == 1
    ed.draw()
    n = len(ed.grid)
    ed.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=ed.buttons[("tool", E.COLOR_KINDS[5])].center)), up(ed)
    assert len(ed.grid) == n and ed.tool == E.COLOR_KINDS[5]  # the panel does not draw on the zoomed board underneath
    z = E.cam.z
    key(ed, pygame.K_z, pygame.KMOD_CTRL)
    assert ed.grid == {} and E.cam.z == z  # undoing a drawing does not move the view


def test_wheel_over_size_field():
    ed = E.Editor()
    ed.draw()
    win = ed.screen.get_size()
    for _ in range(3):
        wheel(ed, 1, ed.buttons[("field", "w")].center)
    assert ed.text["w"] == "43" and (E.COLS, E.ROWS) == (40, 40) and ed.screen.get_size() == win
    click(ed, ("apply",))
    assert (E.COLS, E.ROWS) == (43, 40) and len(ed.undo) == 1
    settle()
    assert E.cam.view.contains(E.grid_rect())


def test_frame_time():
    ed = E.Editor()
    ed.desk = (1920, 1080)
    ed.set_board(L.board(80, 80))
    ed.grid = {(x, y): E.COLOR_KINDS[(x * 7 + y * 3) % 36] for x in range(-40, 40) for y in range(-39, 41)}
    ed.changed()
    worst = {}
    for ed.game_view in (False, True):
        ed.draw()
        ts = []
        for i in range(60):
            wheel(ed, 1 if i < 30 else -1, (400, 400))
            t = time.perf_counter()
            E.cam.update(1 / 60)
            ed.draw()
            ts.append(time.perf_counter() - t)
        worst[ed.game_view] = sorted(ts)[30] * 1000  # median: single frames suffer from computer load
    print("   frame while zooming, 6400 cells: editor %.1f ms, game view %.1f ms" % (worst[False], worst[True]))
    assert worst[False] < 16.6 or os.environ.get("CI")  # shared build machines are too slow to judge


def test_delete_selection():
    ed = E.Editor()
    ed.grid = {(0, 0): "color0", (1, 0): "color1", (9, 9): "color2"}
    ed.start, ed.goal = (0, 1), (12, 5)
    click(ed, ("delete",))  # nothing without a selection
    assert len(ed.grid) == 3 and not ed.undo
    drag(ed, (-1, -1), (5, 3), 3)
    click(ed, ("delete",))
    assert ed.grid == {(9, 9): "color2"} and ed.start is None and ed.goal == (12, 5) and ed.sel is None
    key(ed, pygame.K_z, pygame.KMOD_CTRL)
    assert len(ed.grid) == 3 and ed.start == (0, 1)
    for k in (pygame.K_DELETE, pygame.K_BACKSPACE):
        drag(ed, (9, 9), (12, 5), 3)
        key(ed, k)
        assert (9, 9) not in ed.grid and ed.goal is None
        key(ed, pygame.K_z, pygame.KMOD_CTRL)


def test_problems_pop_up():
    old, L.SNAPSHOT_DIR = L.SNAPSHOT_DIR, tempfile.mkdtemp()
    real, L.save = L.save, lambda n, x: real(n, x, L.SNAPSHOT_DIR)  # do not save to the game's folder
    try:
        ed = E.Editor()
        boxes.clear()
        key(ed, pygame.K_s, pygame.KMOD_CTRL)
        ed.start = (-10, 0)
        click(ed, ("save",))
        ed.start, ed.goal = None, (5, 0)
        click(ed, ("save",))
        ed.start, ed.goal = (-10, 0), (500, 0)
        click(ed, ("save",))
        ed.goal, ed.text["name"] = (5, 0), "  "
        click(ed, ("save",))
        open(os.path.join(L.SNAPSHOT_DIR, "game.c.snapshot"), "wb").write(b"]compressed")
        ed.text["name"] = "game"
        click(ed, ("save",))
        assert [b[0] for b in boxes] == ["Level not saved"] * 6
        assert [b[1][:30] for b in boxes] == ["Place the start and the goal b", "Place the goal before saving.", "Place the start before saving.",
                                              "The start or the goal is outsi", "Enter a level name.", "Level “game” already exists an"]
        assert os.listdir(L.SNAPSHOT_DIR) == ["game.c.snapshot"]
        boxes.clear()
        ed.text["name"], ed.grid = "ok", {(0, 0): "color0"}
        click(ed, ("save",))
        assert not boxes and "ok.c.snapshot" in ed.msg  # a successful save does not pop up
        ed.grid[(0, 5)] = "wire"
        click(ed, ("save",))
        assert boxes == [("Saved, with a warning", "Skipped 1 wire cells that touch no block.")]
        boxes.clear()
        ed.load_image(lambda: None)

        def bad():
            raise pygame.error("broken file")
        ed.load_image(bad)
        assert len(boxes) == 2 and "clipboard" in boxes[0][1] and "broken file" in boxes[1][1]
        down(ed, (1, 1))  # Ctrl+S while drawing: after the dialog the brush does not keep drawing
        ed.start = None
        key(ed, pygame.K_s, pygame.KMOD_CTRL)
        to(ed, (8, 1))
        assert (8, 1) not in ed.grid
    finally:
        L.SNAPSHOT_DIR, L.save = old, real


def test_quit_asks_about_unsaved():
    old, L.SNAPSHOT_DIR = L.SNAPSHOT_DIR, tempfile.mkdtemp()
    real, L.save = L.save, lambda n, x: real(n, x, L.SNAPSHOT_DIR)
    box, answer = pygame.display.message_box, [2]
    pygame.display.message_box = lambda title, *a: boxes.append(title) or answer[0]
    try:
        ed = E.Editor()
        boxes.clear()
        ed.set_board(L.board(30, 30))
        assert ed.can_quit() and not boxes  # empty level: no question
        down(ed, (0, 0)), up(ed)
        for answer[0], leave in ((2, False), (1, True)):  # Cancel stays, Don't save leaves
            assert ed.can_quit() == leave and boxes.pop() == "Unsaved level"
        answer[0] = 0
        assert not ed.can_quit() and boxes == ["Unsaved level", "Level not saved"]  # failed save (no goal): stays
        ed.start, ed.goal = (-10, 0), (5, 0)
        boxes.clear()
        assert ed.can_quit() and os.listdir(L.SNAPSHOT_DIR) == ["My level.c.snapshot"]
        boxes.clear()
        assert ed.can_quit() and not boxes  # saved: no question
        drag(ed, (2, 2), (4, 2))
        answer[0] = 2
        assert not ed.can_quit()  # a change after saving
        key(ed, pygame.K_z, pygame.KMOD_CTRL)
        boxes.clear()
        assert ed.can_quit() and not boxes  # undone back to the saved state
        key(ed, pygame.K_s, pygame.KMOD_CTRL)
        ed.goal = (6, 0)
        assert not ed.can_quit()  # the goal alone counts too
    finally:
        L.SNAPSHOT_DIR, L.save, pygame.display.message_box = old, real, box


def test_auto_only_with_image():
    ed = E.Editor()
    ed.draw()
    assert ("auto",) not in ed.buttons
    s = pygame.Surface((1000, 500))
    s.fill((255, 255, 255)), s.fill((208, 101, 59), (100, 100, 300, 300))
    ed.load_image(lambda: s)
    size = E.COLS, E.ROWS
    ed.draw()
    assert ("auto",) in ed.buttons
    click(ed, ("field", "w"))
    write(ed, "40")
    key(ed, pygame.K_RETURN)
    assert E.COLS == 40 and max(x for x, _ in ed.grid) <= L.X_MAX and len(ed.grid) < 400  # the image shrank to the board
    click(ed, ("auto",))
    assert (E.COLS, E.ROWS) == size
    down(ed, (0, 0)), up(ed)  # changing cells ends fitting the image
    ed.draw()
    assert ("auto",) not in ed.buttons


def test_drag_edges():
    ed = E.Editor()
    ed.grid = {(-20, 0): "color0"}
    x0, x1, y0, y1 = ed.board
    g, n = E.grid_rect(), int(E.cam.z)
    starts = {"l": (g.left - 5, g.centery), "r": (g.right + 5, g.centery), "t": (g.centerx, g.top - 5), "b": (g.centerx, g.bottom + 5),
              "lt": (g.left - 5, g.top - 5), "rb": (g.right + 5, g.bottom + 5)}
    want = {"l": (x0 + 3, x1, y0, y1), "r": (x0, x1 + 3, y0, y1), "t": (x0, x1, y0, y1 - 2), "b": (x0, x1, y0 - 2, y1),
            "lt": (x0 + 3, x1, y0, y1 - 2), "rb": (x0, x1 + 3, y0 - 2, y1)}
    ed.undo = []
    for e, pos in starts.items():
        assert E.edges_at(pos) == e
        ed.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        for k in (1, 2, 3):
            ed.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(pos[0] + k * n, pos[1] + min(k, 2) * n)))
        up(ed)
        assert ed.board == want[e], e  # only the grabbed edge moves
        assert ed.grid == {(-20, 0): "color0"} and len(ed.undo) == 1
        key(ed, pygame.K_z, pygame.KMOD_CTRL)
        assert ed.board == (x0, x1, y0, y1)
    assert E.edges_at(g.center) == ""
    pos = starts["r"]  # far right: at most 80 and within the game's walls; a click without moving changes nothing
    ed.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)), up(ed)
    assert not ed.undo
    ed.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    ed.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(pos[0] + 200 * n, pos[1]))), up(ed)
    assert E.COLS <= 80 and L.X_MAX <= L.X_RANGE[1] and L.X_MIN == x0


def test_theme_and_language():
    ed = E.Editor()
    assert ed.theme == "dark" and lang.current == "en"
    click(ed, ("settings",)), click(ed, ("theme", "light")), click(ed, ("lang", "pl")), click(ed, ("close",))
    assert json.load(open(E.SETTINGS)) == {"theme": "light", "lang": "pl", "keys": {}} and E.T is E.THEMES["light"]
    ed.do_save()
    assert boxes[-1] == (lang.PL["Level not saved"], lang.PL["Place the start and the goal before saving."]) and ed.msg == ""
    ed = E.Editor()  # a new start remembers the choice
    assert ed.theme == "light" and lang.current == "pl"
    for ed.tab in ("colors", "items"):
        ed.draw()
    open(E.SETTINGS, "w").write("broken")
    assert E.Editor().theme == "dark" and lang.current == "en"


def test_all_texts_translated():
    here = os.path.dirname(os.path.abspath(E.__file__))
    src = open(os.path.join(here, "editor.py"), encoding="utf-8").read()
    used = set(re.findall(r'tr\("((?:[^"\\]|\\.)*)"', src)) | set(E.MODES.values())
    for f in ("editor.py", "uch_level.py"):
        used |= set(re.findall(r'ValueError\("([^"]*)"', open(os.path.join(here, f), encoding="utf-8").read()))
    used |= {v["label"] for k, v in L.KINDS.items() if not k.startswith("color")} | {"Start (4x1 plank)", "Goal (flag)"}
    assert used <= set(lang.PL), used - set(lang.PL)
    for en, pl in lang.PL.items():
        assert pl.count("{}") == en.count("{}"), en


def test_texts_fit():
    ed = E.Editor()
    ed.desk = (1920, 1080)
    w = E.SIDE - 20
    for language in ("pl", "en"):
        lang.current = language
        size = lambda f, t: f.size(lang.tr(t, 80, 80))[0]
        for t, hint in (("Paste image", "Ctrl+V"), ("Delete selection", "Del"), ("Clear everything", ""), ("Settings", "")):
            assert 26 + size(ed.font, t) + 6 + ed.small.size(hint)[0] <= w, (language, t)
        for t in ("Brush", "Eraser", "Fill"):
            assert size(ed.small, t) + 10 <= w // 3, (language, t)
        for t, width in (("Blocks", 84), ("Game view", 115)):
            assert 24 + size(ed.font, t) + 4 + 10 <= width, (language, t)
        assert size(ed.small, "Apply") + 8 <= w - 146 and size(ed.small, "Auto") + 8 <= 64
        assert size(ed.small, "Board, up to {}x{}") + 8 <= w - 64
        assert size(ed.small, "press a letter") + 8 <= 116
        for a, b in (("Draw", "left button"), ("Select and move", "right button"), ("Pan the view", "hold the wheel"),
                     ("Resize the board", "drag a grid edge"), ("Paste an image file", "drop it here")):
            assert size(ed.small, a) + size(ed.small, b) + 12 <= 300, (language, a)
        ed.msg = lang.tr("Saved {} ({} blocks, {} cells), fullness {}%", "quite a long name.c.snapshot", 1234, 6400, 256)
        for size in ((80, 80), (72, 37), (80, 12), (10, 10), (10, 80), (40, 60)):  # the message does not cover the settings button at the bottom
            ed.set_board(L.board(*size))
            end = ed.draw_side()
            assert end <= ed.buttons[("settings",)].top, (language, size, end)
    lang.current = "en"


def test_redo_and_clear():
    ed = E.Editor()
    down(ed, (0, 0)), up(ed)
    drag(ed, (3, 3), (5, 3))
    full = dict(ed.grid)
    click(ed, ("clear",))
    assert ed.grid == {} and ed.msg
    click(ed, ("undo",))
    assert ed.grid == full and not ed.msg
    key(ed, pygame.K_z, pygame.KMOD_CTRL)
    assert set(ed.grid) == {(0, 0)}
    key(ed, pygame.K_y, pygame.KMOD_CTRL)
    assert ed.grid == full
    click(ed, ("redo",))
    assert ed.grid == {}
    click(ed, ("redo",))  # nothing left to redo
    assert ed.grid == {} and len(ed.undo) == 3
    key(ed, pygame.K_z, pygame.KMOD_CTRL)
    down(ed, (9, 9)), up(ed)  # a new change clears redo
    assert not ed.redo
    ed.set_focus("w"), write(ed, "30"), key(ed, pygame.K_RETURN)
    key(ed, pygame.K_z, pygame.KMOD_CTRL)
    key(ed, pygame.K_y, pygame.KMOD_CTRL)  # the board size comes back too
    assert (E.COLS, E.ROWS) == (30, 40)


def test_enlarged_pixel_art():
    import random
    rnd = random.Random(5)
    ed = E.Editor()
    white = (255, 255, 255)
    for (w, h), k in (((72, 37), 20), ((80, 60), 9), ((50, 80), 13)):
        # grey rocks cover most of the image and its border; neighbouring shades differ
        kinds = {(x, y): rnd.choice(E.COLOR_KINDS[:8]) for x in range(w) for y in range(h) if rnd.random() < 0.75}
        small = pygame.Surface((w, h))
        small.fill(white)
        for c, n in kinds.items():
            small.set_at(c, E.COLOR[n])
        for crop in (0, 3):
            big = pygame.transform.scale(small, (w * k, h * k))
            big = big.subsurface((crop, crop, w * k - 2 * crop, h * k - 2 * crop))  # a screenshot cropped by a few pixels
            ed.load_image(lambda: big)
            got = {(x - L.X_MIN, L.Y_MAX - y): n for (x, y), n in ed.grid.items()}
            dx = (E.COLS - w) // 2
            dy = (E.ROWS - h) // 2
            assert {(x - dx, y - dy): n for (x, y), n in got.items()} == kinds, ((w, h), k, crop)


def test_image_board():
    ed = E.Editor()
    for w, h, size in ((72, 37, (72, 37)), (80, 60, (80, 60)), (30, 70, (30, 70))):
        s = pygame.Surface((w, h))
        s.fill((255, 255, 255)), s.fill((208, 101, 59), (2, 3, 12, 4))
        ed.load_image(lambda: s)
        assert (E.COLS, E.ROWS) == size and len(ed.grid) == 48
    s = pygame.Surface((1000, 1400))
    s.fill((255, 255, 255)), s.fill((208, 101, 59), (100, 200, 500, 300))
    ed.load_image(lambda: s)
    assert E.COLS <= 80 and E.ROWS <= 80


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
