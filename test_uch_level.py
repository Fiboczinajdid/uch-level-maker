"""Testy logiki edytora. Uruchom: python test_uch_level.py (albo pytest)."""
import random
import xml.etree.ElementTree as ET

import uch_level as L
from uch_level import SETPIECES, WOOD, KINDS, tile, flood_fill, place, build_xml, wire_chunks, image_to_cells


def rect(x0, y0, w, h):
    return {(x0 + i, y0 + j) for i in range(w) for j in range(h)}


def covered(parts):
    out = []
    for x0, y0, _, fp in parts:
        out += rect(x0, y0, fp[0], fp[1])
    return out


def test_tile_covers_each_cell_once():
    rnd = random.Random(1)
    for _ in range(30):
        cells = {(rnd.randint(-20, 20), rnd.randint(-10, 10)) for _ in range(rnd.randint(1, 400))}
        for pieces in (SETPIECES, WOOD):
            cov = covered(tile(cells, pieces))
            assert sorted(cov) == sorted(cells)  # bez dziur, bez nakładania, nic poza obszarem


def test_tile_uses_big_pieces():
    assert len(tile(rect(0, 0, 8, 8), SETPIECES)) == 1
    assert len(tile(rect(0, 0, 6, 16), SETPIECES)) == 1
    assert len(tile(rect(0, 0, 16, 6), SETPIECES)) == 1  # obrócony 16x6
    assert len(tile(rect(0, 0, 4, 4), SETPIECES)) == 1
    assert len(tile(rect(0, 0, 5, 1), SETPIECES)) == 2
    assert len(tile(rect(0, 0, 5, 1), WOOD)) == 1  # deska 5
    assert len(tile(rect(0, 0, 10, 2), SETPIECES)) == 3
    assert len(tile(rect(0, 0, 80, 45), SETPIECES)) <= 45  # dolna granica: 3600/96 = 38


def test_place_matches_game_positions():
    # 1x2 leży na kratkach (0,0),(1,0): w grze środek zaczepienia jest na lewej kratce
    fp = next(SETPIECES[1].footprints())
    assert place(0, 0, fp) == (0, 0, 0)
    # deska 2 ma środek między kratkami (.5), jak StartPlank (-18.5)
    assert place(0, 0, next(WOOD[1].footprints())) == (0.5, 0, 0)
    # pionowa 1x2 (obrót 90) na (0,0),(0,1): zaczepienie dalej w (0,0)
    fp90 = list(SETPIECES[1].footprints())[1]
    assert fp90[:3] == (1, 2, 90) and place(0, 0, fp90) == (0, 0, 90)


def test_flood_fill():
    grid = {c: "kolor0" for c in rect(0, 0, 5, 1)}
    grid[(2, 1)] = "kolce"
    inb = lambda c: -1 <= c[0] <= 5 and -1 <= c[1] <= 2
    flood_fill(grid, (0, 0), "drewno", inb)
    assert all(grid[c] == "drewno" for c in rect(0, 0, 5, 1)) and grid[(2, 1)] == "kolce"
    flood_fill(grid, (0, 1), "kolor0", inb)  # puste dookoła, ograniczone ramką
    assert grid[(-1, 2)] == "kolor0" and grid[(2, 1)] == "kolce" and grid[(0, 0)] == "drewno"
    flood_fill(grid, (0, 0), None, inb)
    assert (0, 0) not in grid


def test_letterbox_is_background():
    frame, black, sky, red = (70, 70, 78, 255), (0, 0, 0, 255), (100, 190, 230, 255), (250, 60, 60, 255)
    img = [[frame] + [black if y < 5 or y > 14 else sky] * 18 + [frame] for y in range(20)]
    img[10][4] = red
    img[0] = img[19] = [frame] * 20
    assert set(image_to_cells(img)) == {(4, 10)}


def test_wire_chunks():
    solid = rect(0, 0, 8, 8)
    chunks, skipped = wire_chunks(rect(0, 8, 4, 1) | rect(-1, 0, 1, 2) | {(20, 20)}, solid)
    assert skipped == [(20, 20)]
    assert sorted((rz, len(r)) for rz, r in chunks) == [(0, 1), (0, 3), (90, 2)]  # na górze 3+1, z boku pionowy
    # jak w levelu z gry: drut pod sufitem (rZ 180), część 1 na x=24, główny (część 2) na x=23
    (rz, run), = wire_chunks([(23, 4), (24, 4)], rect(23, 5, 2, 1))[0]
    assert rz == 180 and run == [(24, 4), (23, 4)]


def test_image_to_cells():
    sky, red, black = (100, 190, 230, 255), (250, 60, 60, 255), (10, 10, 10, 255)
    img = [[sky] * 10 for _ in range(6)]
    for y in range(2, 5):
        for x in range(3, 6):
            img[y][x] = red
    img[0][9] = (0, 0, 0, 0)  # przezroczysty
    img[5][0] = black
    cells = image_to_cells(img)
    assert set(cells) == {(x, y) for x in range(3, 6) for y in range(2, 5)} | {(0, 5)}  # niebo i przezroczyste puste
    red_kind = cells[(3, 2)]
    assert KINDS[red_kind]["color"] == (255, 64, 64)  # najbliższy czerwony z palety
    assert sum(KINDS[cells[(0, 5)]]["color"]) < 100  # czarny -> najciemniejszy


def test_boards_and_walls():
    assert L.board(72, 37) == (-36, 35, -26, 10)  # domyślny BlankLevel
    try:
        for size, walls in (((72, 37), ("-41", "40", "15", "-31")), ((80, 80), ("-45", "44", "45", "-44"))):
            L.set_board(L.board(*size))
            m = {e.get("path"): e for e in ET.fromstring(build_xml({}, (0, 0), (9, 0))).findall("moved")}
            assert (m["LeftWall"].get("pX"), m["RightWall"].get("pX"), m["Ceiling"].get("pY"), m["DeathPit"].get("pY")) == walls
    finally:
        L.set_board(L.board(40, 40))
    for w in range(L.MIN_SIDE, L.MAX_SIDE + 1):
        for h in range(L.MIN_SIDE, L.MAX_SIDE + 1):
            assert L.board_size(L.board(w, h)) == (w, h)
            b = L.resized(L.board(40, 40), w, h)
            assert L.board_size(b) == (w, h) and L.X_RANGE[0] <= b[0] and b[1] <= L.X_RANGE[1] and L.Y_RANGE[0] <= b[2] and b[3] <= L.Y_RANGE[1]


def test_fullness():
    assert L.fullness({c: "kolor0" for c in rect(0, 0, 8, 8)}) == 5  # 8x8 kosztuje tyle co 1x1
    g = {c: "drewno" for c in rect(0, 0, 5, 1)}
    g.update({c: "drut" for c in rect(0, 1, 3, 1)})
    assert L.fullness(g) == 10 + 5 * 4
    assert L.fullness({}) == 0 and image_to_cells([[(0, 0, 0, 0)]]) == {}


def test_agreement():
    assert L.agreement({(0, 0): "a"}, (1, 1), {c: "a" for c in rect(0, 0, 2, 2)}, (2, 2)) == 1
    assert L.agreement({(0, 0): "a"}, (1, 1), {(0, 0): "a"}, (2, 2)) == 0.25


def test_build_xml():
    grid = {c: "kolor0" for c in rect(0, 0, 8, 8)}
    grid.update({c: "drut" for c in rect(0, 8, 4, 1)})  # odcinki 3 + 1
    grid[(30, 30)] = "drut"  # w powietrzu: pominięty
    grid[(-5, 0)] = "kolce"
    root = ET.fromstring(build_xml(grid, start=(-10, 0), goal=(10, 0)))
    assert root.get("levelSceneName") == "BlankLevel"
    blocks = root.findall("block")
    ids = [b.get("blockID") for b in blocks]
    assert ids.count("49") == 1 and ids.count("55") == 2 and ids.count("13") == 4 and ids.count("10") == 1
    parts = [b for b in blocks if b.get("subElementName")]
    for sub in parts:
        parent = [b for b in blocks if b.get("sceneID") == sub.get("parentID")][0]
        main = [b for b in blocks if b.get("sceneID") == sub.get("mainID")][0]
        assert parent.get("blockID") == "49" and main.get("blockID") == "55"  # przyczepiony do klocka pod nim
    assert {(p.get("pX"), p.get("subElementName")) for p in parts if p.get("pX") in "012"} == \
        {("0", "BarbedwireSetPiece1"), ("1", "BarbedwireSetPiece2"), ("2", "BarbedwireSetPiece3")}
    goal = [b for b in blocks if b.get("blockID") == "39"][0]
    assert goal.get("placeableID") == "2" and (goal.get("pX"), goal.get("pY")) == ("10", "0")
    sp = [m for m in root.findall("moved") if m.get("path") == "StartPlank"][0]
    assert (sp.get("pX"), sp.get("pY")) == ("-8.5", "0")
    assert len({b.get("sceneID") for b in blocks}) == len(blocks)
    assert len({b.get("placeableID") for b in blocks}) == len(blocks)


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
