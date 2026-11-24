"""Logika edytora: klocki z gry, łączenie kratek w jak najmniej klocków, wypełnianie i zapis .snapshot.

Siatka: 1 kratka = 1 jednostka w grze, kratka (x, y) ma środek w punkcie (x, y).
Rozmiary klocków i punkty zaczepienia wzięte z colliderów prefabów gry (PlaceableMetadataList.allBlockPrefabs,
indeks w tej tablicy = blockID w pliku). Szczegóły w notes/format-snapshot.md.
"""
import colorsys
import os
from xml.sax.saxutils import quoteattr

# Krawędź ściany jest 4.5 od jej pozycji (zmierzone w grze), więc ściana stoi 5 za skrajną wolną kratką.
MIN_SIDE, MAX_SIDE = 10, 80
X_RANGE, Y_RANGE = (-59, 57), (-44, 45)  # skrajne wolne kratki przy najdalszych ścianach w levelach z gry


def board(w, h):
    """Plansza w x h kratek: (x_min, x_max, y_min, y_max). 72x37 = domyślny BlankLevel; większe rosną w obie strony."""
    x, y = -(w // 2), -26 - round((h - 37) * 13 / 43)  # 80 wysokości: y -39..40, w zakresie leveli z gry
    return x, x + w - 1, y, y + h - 1


def resized(b, w, h):
    """Plansza b w nowym rozmiarze: rośnie i maleje w obie strony od swojego środka."""
    x = min(max((b[0] + (b[1] - b[0] + 1) // 2) - w // 2, X_RANGE[0]), X_RANGE[1] - w + 1)
    y = min(max((b[2] + (b[3] - b[2] + 1) // 2) - h // 2, Y_RANGE[0]), Y_RANGE[1] - h + 1)
    return x, x + w - 1, y, y + h - 1


def drag_edges(b, edges, dx, dy):
    """Plansza b po przesunięciu krawędzi (podzbiór "lrtb") o dx, dy kratek, w granicach MIN_SIDE..MAX_SIDE."""
    x0, x1, y0, y1 = b
    if "l" in edges:
        x0 = min(max(x0 + dx, x1 - MAX_SIDE + 1, X_RANGE[0]), x1 - MIN_SIDE + 1)
    if "r" in edges:
        x1 = max(min(x1 + dx, x0 + MAX_SIDE - 1, X_RANGE[1]), x0 + MIN_SIDE - 1)
    if "b" in edges:
        y0 = min(max(y0 + dy, y1 - MAX_SIDE + 1, Y_RANGE[0]), y1 - MIN_SIDE + 1)
    if "t" in edges:
        y1 = max(min(y1 + dy, y0 + MAX_SIDE - 1, Y_RANGE[1]), y0 + MIN_SIDE - 1)
    return x0, x1, y0, y1


X_MIN, X_MAX, Y_MIN, Y_MAX = board(40, 40)

# Limit zapełnienia (GameSettings.LevelFullnessScoreLimit w resources.assets). Ponad nim gra blokuje publikowanie.
FULLNESS_LIMIT = 5000


def set_board(b):
    global X_MIN, X_MAX, Y_MIN, Y_MAX
    X_MIN, X_MAX, Y_MIN, Y_MAX = b


def board_size(b):
    return b[1] - b[0] + 1, b[3] - b[2] + 1


SNAPSHOT_DIR = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "LocalLow",
                            "Clever Endeavour Games", "Ultimate Chicken Horse", "snapshots")


class Piece:
    """Przedmiot z gry. bounds = prostokąt zajmowany przy obrocie 0, względem punktu zaczepienia (pX, pY)."""

    def __init__(self, block_id, name, minx, miny, maxx, maxy):
        self.block_id, self.name = block_id, name
        self.bounds = (minx, miny, maxx, maxy)

    def footprints(self):
        """(w, h, rZ, minx, miny) dla obrotu 0 i 90 (180/270 dają te same kształty)."""
        minx, miny, maxx, maxy = self.bounds
        yield round(maxx - minx), round(maxy - miny), 0, minx, miny
        if maxx - minx != maxy - miny:
            # obrót o 90° w lewo: (x, y) -> (-y, x)
            yield round(maxy - miny), round(maxx - minx), 90, -maxy, minx


def _setpiece(bid, name, minx, miny, maxx, maxy):
    return Piece(bid, name, minx, miny, maxx, maxy)


# Klocki z trybu tworzenia (SetPiece): kolorowalne, twarde.
SETPIECES = [
    _setpiece(40, "100_SetPiece1x1", -0.5, -0.5, 0.5, 0.5),
    _setpiece(41, "101_SetPiece1x2", -0.5, -0.5, 1.5, 0.5),
    _setpiece(42, "102_SetPiece1x3", -1.5, -0.5, 1.5, 0.5),
    _setpiece(43, "103_SetPiece1x4", -1.5, -0.5, 2.5, 0.5),
    _setpiece(44, "104_SetPiece1x8", -4.5, -0.5, 3.5, 0.5),
    _setpiece(45, "105_SetPiece1x14", -7.5, -0.5, 8.5, 0.5),  # mimo nazwy collider ma 16 kratek
    _setpiece(46, "106_SetPiece2x4", -1.5, -1.5, 2.5, 0.5),
    _setpiece(47, "107_SetPiece2x2", -0.5, -1.5, 1.5, 0.5),
    _setpiece(48, "108_SetPiece4x4", -1.5, -2.5, 2.5, 1.5),
    _setpiece(49, "109_SetPiece8x8", -3.5, -4.5, 4.5, 3.5),
    _setpiece(50, "110_SetPiece16x6", -2.5, -8.5, 3.5, 7.5),
]
WOOD = [
    Piece(0, "01_1x1 Box", -0.5, -0.5, 0.5, 0.5),
    Piece(1, "02_Plank2", -1, -0.5, 1, 0.5),
    Piece(2, "03_Plank3", -1.5, -0.5, 1.5, 0.5),
    Piece(3, "04_Plank4", -2, -0.5, 2, 0.5),
    Piece(4, "05_Plank5", -2.5, -0.5, 2.5, 0.5),
    Piece(5, "06_Beam", -3, -0.5, 3, 0.5),
]
SPIKE = Piece(10, "11_1x1 Spike Block", -0.5, -0.5, 0.5, 0.5)
# Drut x3 = wpis główny (55) + 1-3 części (blockID 13, BarbedwireSetPiece1..3), każda przyczepiona (parentID) do klocka,
# na którym leży. Bez części gra niszczy drut ("Destroying unused sub-element"), więc odcinek 1-2 kratek też jest OK.
WIRE_MAIN, WIRE_PART = 55, 13
START = Piece(38, "StartPlank", -2, -0.5, 2, 0.5)  # deska 4x1, strefa startu 4x4 nad nią
GOAL = Piece(39, "GoalBlock", -0.5, -0.5, 0.5, 0.5)  # klocek 1x1, strefa mety nad nim: dx -2..1, dy 1..4

# Paleta kolorów klocków z gry: 36 kolorów, każdy użyty w >= 88 levelach z folderu snapshots
# (następne kolory to już zaokrąglone warianty tych samych, w <= 15 levelach).
PALETTE = [
    (0.053, 0.053, 0.053), (0.447, 0.447, 0.447), (0.2647059, 0.1474943, 0.1206748),
    (0.1911765, 0.1084139, 0.07590831), (0.3308824, 0.3308824, 0.3308824), (0.253, 0.253, 0.253),
    (0.4117647, 0.1987249, 0.1150519), (0.3676471, 0.1139868, 0.05136246), (0.2039216, 0.2039216, 0.2039216),
    (0.09511469, 0.2426471, 0.04817258), (0.1764706, 0.1764706, 0.1764706), (0.122, 0.122, 0.122),
    (0.1314879, 0.1899535, 0.4705882), (0.09482757, 0.1617647, 0.01903114), (0.5147059, 0.3879217, 0.04163063),
    (0.2083694, 0.291612, 0.6911765), (0.2647566, 0.3382353, 0.1815528), (0.1764706, 0.09083045, 0.1634769),
    (0.1323529, 0.1258427, 0.03795415), (0.2058824, 0.06963669, 0.06963669), (0.4679692, 0.4852941, 0.1712803),
    (0.2058823, 0.3904664, 0.5), (0.3382353, 0.1964749, 0.3167268), (0.1102941, 0.1051038, 0.06325691),
    (0.1911765, 0.03654844, 0.03654844), (0.2484533, 0.25, 0.1378676), (0.06433824, 0.09634889, 0.25),
    (0.1372188, 0.2679886, 0.3455882), (0.3970588, 0.1547362, 0.1547362), (0.5147059, 0.2308607, 0.2308607),
    (0.5514706, 0.1257028, 0.1257028), (0.2078362, 0.2205882, 0.1281358), (0.3414807, 0.3823529, 0.295199),
    (0.06617647, 0.06617647, 0.06617647), (0.4485294, 0.313311, 0.4447993), (0.0, 0.1955882, 0.2132353),
]
# shortcut: kolejność moja (szarości, potem odcienie od czerwonego), nie jak w księdze gry (tej nie znamy)
PALETTE.sort(key=lambda c: (colorsys.rgb_to_hsv(*c)[1] > 0.15, round(colorsys.rgb_to_hsv(*c)[0] * 12) % 12,
                            colorsys.rgb_to_hsv(*c)[2]))


def screen_color(rgb):
    """Jak kolor wygląda w grze: ok. 2x jaśniej niż colR/G/B (zmierzone na zrzucie)."""
    return tuple(min(255, round(v * 2 * 255)) for v in rgb)


# Rodzaje kratek w edytorze. rgb = kolor klocka w grze (colR/G/B), color = kolor w edytorze.
KINDS = {f"kolor{i}": dict(label=f"Kolor {i + 1}", color=screen_color(c), pieces=SETPIECES, rgb=c)
         for i, c in enumerate(PALETTE)}
KINDS.update({
    "drewno": dict(label="Drewno (deski)", color=(190, 140, 80), pieces=WOOD),
    "kolce":  dict(label="Kolczasta kula", color=(150, 150, 150), pieces=[SPIKE]),
    # drut nie dzieli się na prostokąty, tylko na odcinki po 3 wzdłuż klocka, do którego się przyczepia (wire_chunks)
    "drut":   dict(label="Drut kolczasty", color=(70, 70, 70), pieces=None, rgb=(0.1764706, 0.1764706, 0.1764706)),
})


def rot(v, rz):
    """Obrót wektora o rZ stopni w lewo (jak w grze)."""
    x, y = v
    return {0: (x, y), 90: (-y, x), 180: (-x, -y), 270: (y, -x)}[rz]


def wire_chunks(wire, solid):
    """Dzieli kratki drutu na odcinki (rZ, [kratki]) po max 3, każdy przyczepiony do klocków z `solid`.

    Drut leży na klocku pod nim (rZ 0), wisi pod klockiem (180) albo trzyma się boku (90: klocek z prawej, 270: z lewej).
    Zwraca (odcinki, kratki bez żadnego klocka obok).
    """
    groups, skipped = {}, []
    for c in wire:
        for rz in (0, 180, 270, 90):
            s = rot((0, -1), rz)
            if (c[0] + s[0], c[1] + s[1]) in solid:
                groups.setdefault(rz, []).append(c)
                break
        else:
            skipped.append(c)
    out = []
    for rz, cells in groups.items():
        a, b = rot((1, 0), rz), rot((0, 1), rz)
        dot = lambda c, v: c[0] * v[0] + c[1] * v[1]
        run = []
        for c in sorted(cells, key=lambda c: (dot(c, b), dot(c, a))):
            if run and (c != (run[-1][0] + a[0], run[-1][1] + a[1]) or len(run) == 3):
                out.append((rz, run))
                run = []
            run.append(c)
        if run:
            out.append((rz, run))
    return out, skipped


def tile(cells, pieces):
    """Dzieli zbiór kratek na prostokąty z dostępnych klocków, zachłannie: największy pasujący najpierw.

    Zwraca listę (x0, y0, piece, footprint), x0/y0 = lewa dolna kratka. Każda kratka trafia do dokładnie jednego klocka,
    o ile wśród klocków jest 1x1 (jest w każdym rodzaju).
    """
    left = set(cells)
    shapes = sorted(((fp, p) for p in pieces for fp in p.footprints()),
                    key=lambda s: (-s[0][0] * s[0][1], abs(s[0][0] - s[0][1])))
    out = []
    for fp, p in shapes:
        w, h = fp[0], fp[1]
        if not left:
            break
        # od lewego górnego rogu, jak się czyta
        for x0, y0 in sorted(left, key=lambda c: (-c[1], c[0])):
            if all((x0 + i, y0 + j) in left for j in range(h) for i in range(w)):
                left.difference_update((x0 + i, y0 + j) for j in range(h) for i in range(w))
                out.append((x0, y0, p, fp))
    assert not left, f"nie pokryte kratki: {sorted(left)[:5]}"
    return out


def flood_fill(grid, start, kind, in_bounds):
    """Wypełnianie jak w Paincie: zamienia spójny (4 sąsiadów) obszar tego samego rodzaju co `start` na `kind`.

    grid: dict (x, y) -> rodzaj; puste kratki nie są w dict. kind=None czyści obszar.
    """
    old = grid.get(start)
    if old == kind or not in_bounds(start):
        return
    stack = [start]
    while stack:
        c = stack.pop()
        if not in_bounds(c) or grid.get(c) != old:
            continue
        if kind is None:
            del grid[c]
        else:
            grid[c] = kind
        x, y = c
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]


def color_dist(a, b):
    """Odległość kolorów bliższa temu, jak widzi oko, niż zwykłe RGB („redmean”)."""
    r = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return ((2 + r / 256) * dr * dr + 4 * dg * dg + (2 + (255 - r) / 256) * db * db) ** 0.5


_nearest = {}


def nearest_kind(p):
    """Najbliższy kolor klocka, "white" dla prawie białego albo None dla przezroczystego."""
    if p[3] < 128:
        return None
    k = p[0] >> 1, p[1] >> 1, p[2] >> 1
    if k not in _nearest:
        if color_dist(p, (255, 255, 255)) < 45:  # najjaśniejszy klocek jest od białego o ok. 81
            _nearest[k] = "white"
        else:
            _nearest[k] = min((color_dist(p, v["color"]), n) for n, v in KINDS.items() if n.startswith("kolor"))[1]
    return _nearest[k]


def find_grid(data, w, h):
    """Siatka powiększonego pixel artu: (bok kratki, ox, oy) albo None. data = bajty RGBA.

    Wszystkie zmiany koloru muszą leżeć na liniach co `bok` pikseli (97%, żeby przeżyć pojedyncze wady i przycięcie).
    """
    def changes(n, lines, at):
        out = {}
        for j in range(0, lines, max(lines // 120, 1)):
            for i in range(1, n):
                a, b = at(i - 1, j), at(i, j)
                if data[a:a + 4] != data[b:b + 4] and sum(abs(data[a + c] - data[b + c]) for c in range(4)) > 40:
                    out[i] = out.get(i, 0) + 1
        return out

    cx = changes(w, h, lambda i, j: (j * w + i) * 4)
    cy = changes(h, w, lambda i, j: (i * w + j) * 4)
    if len(cx) < 4 or len(cy) < 4:
        return None
    for s in range(min(w, h) // 5, 1, -1):
        if max(w, h) / s > MAX_SIDE + 1:
            return None
        off = []
        for c in (cx, cy):
            mods = {}
            for i, n in c.items():
                mods[i % s] = mods.get(i % s, 0) + n
            o = max(mods, key=mods.get)
            if mods[o] >= 0.97 * sum(c.values()):
                off.append(o)
        if len(off) == 2:
            return s, off[0], off[1]
    return None


def downsample(data, w, h, nw, nh, ox=0.0, oy=0.0, sx=None, sy=None):
    """Zmniejsza obrazek RGBA do nw x nh: w każdej kratce wygrywa najczęstszy kolor, zamiast mieszania kolorów na krawędziach."""
    sx, sy = sx or w / nw, sy or h / nh
    out = []
    for y in range(nh):
        row = []
        for x in range(nw):
            votes = {}
            for j in (0.2, 0.4, 0.6, 0.8):
                for i in (0.2, 0.4, 0.6, 0.8):
                    a = (min(max(int(oy + (y + j) * sy), 0), h - 1) * w + min(max(int(ox + (x + i) * sx), 0), w - 1)) * 4
                    p = data[a:a + 4]
                    votes.setdefault(nearest_kind(p), []).append(p)
            ps = max(votes.values(), key=len)
            row.append(tuple(round(sum(p[c] for p in ps) / len(ps)) for c in range(4)))
        out.append(row)
    return out


def image_to_cells(pixels, step=30):
    """Obrazek (lista wierszy z góry na dół, piksele RGBA, już zmniejszony do rozmiaru kratek) -> {(kol, wiersz): rodzaj}.

    Jeśli co najmniej 10% obrazka jest białe, tłem jest tylko biel. W innym razie (np. zrzut z gry z niebem)
    tło jak wypełnianie w Paincie z tolerancją: zaczyna od kolorów, które zajmują >= 5% brzegu, i od najczęstszego
    koloru obrazka, i rozlewa się na sąsiednie piksele różniące się o mniej niż `step` (dzięki temu łapie też gradient nieba).
    Tło i przezroczyste piksele zostają puste, reszta dostaje najbliższy kolor z palety klocków. Wiersz 0 = góra obrazka.
    """
    h, w = len(pixels), len(pixels[0])
    key = lambda p: tuple(v // 32 for v in p[:3])
    pos = [(x, y) for y in range(h) for x in range(w) if pixels[y][x][3] >= 128]
    if not pos:
        return {}
    kinds = {(x, y): nearest_kind(pixels[y][x]) for x, y in pos}
    if sum(k == "white" for k in kinds.values()) >= 0.1 * len(pos):
        return {c: k for c, k in kinds.items() if k != "white"}
    edge = [c for c in pos if c[0] in (0, w - 1) or c[1] in (0, h - 1)]
    seed_keys = set()
    for cells, share in ((edge, 0.05), (pos, None)):
        count = {}
        for x, y in cells:
            count[key(pixels[y][x])] = count.get(key(pixels[y][x]), 0) + 1
        # shortcut: najczęstszy kolor zawsze jest tłem; obrazek bez tła (np. zdjęcie na cały ekran) straci ten kolor
        seed_keys |= {k for k, n in count.items() if n >= share * len(cells)} if share else {max(count, key=count.get)}
    bg = {c for c in pos if key(pixels[c[1]][c[0]]) in seed_keys}
    stack = list(bg)
    while stack:
        x, y = stack.pop()
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if q not in bg and 0 <= q[0] < w and 0 <= q[1] < h and pixels[q[1]][q[0]][3] >= 128 \
                    and color_dist(pixels[q[1]][q[0]], pixels[y][x]) < step:
                bg.add(q)
                stack.append(q)
    # kawałki tła odcięte od reszty (np. niebo pod podłogą): ten sam odcień co duża część znalezionego tła
    share = {}
    for x, y in bg:
        share[key(pixels[y][x])] = share.get(key(pixels[y][x]), 0) + 1
    bg |= {(x, y) for x, y in pos if share.get(key(pixels[y][x]), 0) >= 0.03 * len(pos)}
    # czarne pasy u góry i u dołu (letterbox); najciemniejszy klocek ma 27, więc go nie ruszają
    for rows in (range(h), range(h - 1, -1, -1)):
        bar, pending = set(), set()
        for y in rows:
            left = [(x, y) for x in range(w) if pixels[y][x][3] >= 128 and (x, y) not in bg]
            if any(max(pixels[y][x][:3]) >= 16 for x, _ in left):
                break
            pending.update(left)
            if len(left) >= w / 2:  # pas, a nie pojedyncze czarne piksele
                bar |= pending
        bg |= bar
    colors = [(k, KINDS[k]["color"]) for k in KINDS if k.startswith("kolor")]
    return {(x, y): min(colors, key=lambda kc: color_dist(pixels[y][x], kc[1]))[0] for x, y in pos if (x, y) not in bg}


def fullness(grid):
    """Punkty zapełnienia levelu (bez mety): klocek kolorowy 5, deska i kula 10, niezależnie od rozmiaru.

    Drut: 5 za wpis główny i 5 za każdą część (tak wychodzi 5% na zrzucie z gry; w plikach nie odczytane wprost).
    """
    by = {}
    for c, k in grid.items():
        by.setdefault(k, set()).add(c)
    wire = by.pop("drut", set())
    total = sum(len(tile(cells, KINDS[k]["pieces"])) * (5 if k.startswith("kolor") else 10) for k, cells in by.items())
    return total + sum(5 * (len(run) + 1) for _, run in wire_chunks(wire, set().union(*by.values()))[0])


def agreement(small, ssize, big, bsize):
    """Jaka część kratek dużej wersji obrazka wygląda tak samo w małej (0..1)."""
    same = sum(small.get((x * ssize[0] // bsize[0], y * ssize[1] // bsize[1])) == big.get((x, y))
               for x in range(bsize[0]) for y in range(bsize[1]))
    return same / (bsize[0] * bsize[1])


def place(x0, y0, fp):
    """Pozycja punktu zaczepienia klocka, którego lewa dolna kratka to (x0, y0)."""
    _, _, rz, minx, miny = fp
    return x0 - 0.5 - minx, y0 - 0.5 - miny, rz


def _num(v):
    return str(int(v)) if float(v).is_integer() else str(v)


def build_xml(grid, start, goal):
    """XML pliku .snapshot dla BlankLevel. start = lewa kratka deski startowej, goal = kratka flagi."""
    if start is None and goal is None:
        raise ValueError("Postaw start i metę przed zapisem.")
    if start is None:
        raise ValueError("Postaw start przed zapisem.")
    if goal is None:
        raise ValueError("Postaw metę przed zapisem.")
    lines = []
    sid = 0
    covered = {}  # kratka -> sceneID klocka (do przyczepienia drutu)

    def block(bid, px, py, rz, pid, extra=""):
        nonlocal sid
        lines.append(f'<block sceneID="{sid}" blockID="{bid}" pX="{_num(px)}" pY="{_num(py)}" pZ="0" '
                     f'rX="0" rY="0" rZ="{rz}" sX="1" sY="1" sZ="1"{extra} placeableID="{pid}" />')
        sid += 1
        return sid - 1

    seq = 100
    for kind in KINDS:
        cells = [c for c, k in grid.items() if k == kind]
        if not cells or KINDS[kind]["pieces"] is None:
            continue
        rgb = KINDS[kind].get("rgb")
        col = f' colR="{rgb[0]}" colG="{rgb[1]}" colB="{rgb[2]}"' if rgb else ""
        for x0, y0, p, fp in tile(cells, KINDS[kind]["pieces"]):
            px, py, rz = place(x0, y0, fp)
            # ID jak w grze: 1000000 + numer*10 (gra liczy z tego kolejne numery)
            s = block(p.block_id, px, py, rz, 1000000 + seq * 10, col)
            seq += 1
            for j in range(fp[1]):
                for i in range(fp[0]):
                    covered[(x0 + i, y0 + j)] = s
    rgb = KINDS["drut"]["rgb"]
    col = f' colR="{rgb[0]}" colG="{rgb[1]}" colB="{rgb[2]}"'
    # kratki drutu bez klocka obok są pomijane (gra i tak by je zniszczyła); edytor o nich ostrzega
    for rz, run in wire_chunks([c for c, k in grid.items() if k == "drut"], covered)[0]:
        pid = 1000000 + seq * 10
        seq += 1
        a, s = rot((1, 0), rz), rot((0, -1), rz)
        main = block(WIRE_MAIN, run[0][0] + a[0], run[0][1] + a[1], rz, pid, col)  # główny = środkowa część
        for k, (x, y) in enumerate(run, 1):
            parent = covered[(x + s[0], y + s[1])]
            block(WIRE_PART, x, y, rz, pid + k,
                  f' parentID="{parent}" mainID="{main}" subElementName="BarbedwireSetPiece{k}"{col}')

    gx, gy = goal
    block(GOAL.block_id, gx, gy, 0, 2)  # placeableID 2 = flaga, która już jest w BlankLevel (gra ją przesuwa)
    sx, sy, _ = place(start[0], start[1], next(START.footprints()))
    moved = [("7", "DeathPit", -0.9, Y_MIN - 5, 0), ("9", "LeftWall", X_MIN - 5, 2, 270),
             ("8", "Ceiling", 6.5, Y_MAX + 5, 180), ("6", "RightWall", X_MAX + 5, -25.9, 90), ("11", "StartPlank", sx, sy, 0)]
    for pid, path, px, py, rz in moved:
        lines.append(f'<moved placeableID="{pid}" path={quoteattr(path)} pX="{_num(px)}" pY="{_num(py)}" pZ="0" '
                     f'rX="0" rY="0" rZ="{rz}" sX="1" sY="1" sZ="1" />')
    head = ('<scene levelSceneName="BlankLevel" saveFormatVersion="1" customLevelBackground="1" '
            'customLevelMusic="10" customLevelAmbience="10">')
    return head + "".join(lines) + "</scene>"


def save(name, xml, folder=SNAPSHOT_DIR):
    """Zapisuje czysty XML jako <name>.c.snapshot (gra przyjmuje XML, gdy plik zaczyna się od '<').

    Nadpisuje tylko pliki z edytora (czysty XML); levele zapisane przez grę są skompresowane i zostają nietknięte.
    """
    name = "".join(ch for ch in name if ch not in '<>:"/\\|?*').strip()
    if not name:
        raise ValueError("Podaj nazwę levelu.")
    path = os.path.join(folder, name + ".c.snapshot")
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read(1) != b"<":
                raise ValueError("Level „{}” już istnieje i nie jest z edytora. Wybierz inną nazwę.", name)
        # stara miniaturka z gry pokazywałaby poprzednią wersję; gra zrobi nową przy następnym graniu
        for ext in (".jpg", ".png"):
            thumb = os.path.join(folder, "thumbnails", f"l_{name}{ext}")
            if os.path.exists(thumb):
                os.remove(thumb)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return path
