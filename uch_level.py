"""Editor logic: game blocks, merging cells into as few blocks as possible, flood fill and saving a .snapshot.

Grid: 1 cell = 1 game unit, cell (x, y) is centered at (x, y).
Block sizes and pivots match the game's colliders; block_id is the blockID used in the level file.
"""
import colorsys
import os
from xml.sax.saxutils import quoteattr

# A wall's edge is 4.5 from its position (measured in the game), so the wall sits 5 beyond the last free cell.
MIN_SIDE, MAX_SIDE = 10, 80
X_RANGE, Y_RANGE = (-59, 57), (-44, 45)  # outermost free cells with the farthest walls seen in real levels


def board(w, h):
    """Board of w x h cells: (x_min, x_max, y_min, y_max). 72x37 = the default BlankLevel; larger ones grow both ways."""
    x, y = -(w // 2), -26 - round((h - 37) * 13 / 43)  # height 80: y -39..40, within the range of real levels
    return x, x + w - 1, y, y + h - 1


def resized(b, w, h):
    """Board b in a new size: grows and shrinks both ways from its center."""
    x = min(max((b[0] + (b[1] - b[0] + 1) // 2) - w // 2, X_RANGE[0]), X_RANGE[1] - w + 1)
    y = min(max((b[2] + (b[3] - b[2] + 1) // 2) - h // 2, Y_RANGE[0]), Y_RANGE[1] - h + 1)
    return x, x + w - 1, y, y + h - 1


def drag_edges(b, edges, dx, dy):
    """Board b after moving edges (a subset of "lrtb") by dx, dy cells, within MIN_SIDE..MAX_SIDE."""
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

# The game's fullness limit. Above it the game blocks publishing.
FULLNESS_LIMIT = 5000


def set_board(b):
    global X_MIN, X_MAX, Y_MIN, Y_MAX
    X_MIN, X_MAX, Y_MIN, Y_MAX = b


def board_size(b):
    return b[1] - b[0] + 1, b[3] - b[2] + 1


SNAPSHOT_DIR = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "LocalLow",
                            "Clever Endeavour Games", "Ultimate Chicken Horse", "snapshots")


class Piece:
    """Item from the game. bounds = rectangle covered at rotation 0, relative to the pivot (pX, pY)."""

    def __init__(self, block_id, name, minx, miny, maxx, maxy):
        self.block_id, self.name = block_id, name
        self.bounds = (minx, miny, maxx, maxy)

    def footprints(self):
        """(w, h, rZ, minx, miny) for rotation 0 and 90 (180/270 give the same shapes)."""
        minx, miny, maxx, maxy = self.bounds
        yield round(maxx - minx), round(maxy - miny), 0, minx, miny
        if maxx - minx != maxy - miny:
            # rotate 90° left: (x, y) -> (-y, x)
            yield round(maxy - miny), round(maxx - minx), 90, -maxy, minx


def _setpiece(bid, name, minx, miny, maxx, maxy):
    return Piece(bid, name, minx, miny, maxx, maxy)


# Creative mode blocks (SetPiece): colorable, solid.
SETPIECES = [
    _setpiece(40, "100_SetPiece1x1", -0.5, -0.5, 0.5, 0.5),
    _setpiece(41, "101_SetPiece1x2", -0.5, -0.5, 1.5, 0.5),
    _setpiece(42, "102_SetPiece1x3", -1.5, -0.5, 1.5, 0.5),
    _setpiece(43, "103_SetPiece1x4", -1.5, -0.5, 2.5, 0.5),
    _setpiece(44, "104_SetPiece1x8", -4.5, -0.5, 3.5, 0.5),
    _setpiece(45, "105_SetPiece1x14", -7.5, -0.5, 8.5, 0.5),  # despite the name it is 16 cells long
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
# Wire x3 = a main entry (55) + 1-3 parts (blockID 13, BarbedwireSetPiece1..3), each attached (parentID) to the block
# it lies on. Without parts the game destroys the wire, so a run of 1-2 cells is fine too.
WIRE_MAIN, WIRE_PART = 55, 13
START = Piece(38, "StartPlank", -2, -0.5, 2, 0.5)  # 4x1 plank with a 4x4 start zone above
GOAL = Piece(39, "GoalBlock", -0.5, -0.5, 0.5, 0.5)  # 1x1 block with the goal zone above: dx -2..1, dy 1..4

# Block color palette: 36 colors, each used in >= 88 of 530 checked levels
# (the next ones are rounded variants of the same colors, in <= 15 levels).
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
# shortcut: the order is ours (greys, then hues from red), not the one in the game
PALETTE.sort(key=lambda c: (colorsys.rgb_to_hsv(*c)[1] > 0.15, round(colorsys.rgb_to_hsv(*c)[0] * 12) % 12,
                            colorsys.rgb_to_hsv(*c)[2]))


def screen_color(rgb):
    """How a color looks in the game: about 2x brighter than colR/G/B (measured on a screenshot)."""
    return tuple(min(255, round(v * 2 * 255)) for v in rgb)


# Cell kinds in the editor. rgb = block color in the game (colR/G/B), color = color in the editor.
KINDS = {f"color{i}": dict(label=f"Color {i + 1}", color=screen_color(c), pieces=SETPIECES, rgb=c)
         for i, c in enumerate(PALETTE)}
KINDS.update({
    "wood": dict(label="Wood (planks)", color=(190, 140, 80), pieces=WOOD),
    "spike":  dict(label="Spikeball", color=(150, 150, 150), pieces=[SPIKE]),
    # wire is not split into rectangles but into runs of 3 along the block it attaches to (wire_chunks)
    "wire":   dict(label="Barbed wire", color=(70, 70, 70), pieces=None, rgb=(0.1764706, 0.1764706, 0.1764706)),
})


def rot(v, rz):
    """Rotates a vector by rZ degrees to the left (as in the game)."""
    x, y = v
    return {0: (x, y), 90: (-y, x), 180: (-x, -y), 270: (y, -x)}[rz]


def wire_chunks(wire, solid):
    """Splits wire cells into runs (rZ, [cells]) of at most 3, each attached to blocks from `solid`.

    Wire lies on the block below (rZ 0), hangs under a block (180) or clings to a side (90: block on the right, 270: left).
    Returns (runs, cells with no block next to them).
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
    """Splits a set of cells into rectangles of the available blocks, greedily: the largest fitting one first.

    Returns a list of (x0, y0, piece, footprint), x0/y0 = bottom left cell. Each cell ends up in exactly one block,
    as long as there is a 1x1 block (every kind has one).
    """
    left = set(cells)
    shapes = sorted(((fp, p) for p in pieces for fp in p.footprints()),
                    key=lambda s: (-s[0][0] * s[0][1], abs(s[0][0] - s[0][1])))
    out = []
    for fp, p in shapes:
        w, h = fp[0], fp[1]
        if not left:
            break
        # from the top left corner, in reading order
        for x0, y0 in sorted(left, key=lambda c: (-c[1], c[0])):
            if all((x0 + i, y0 + j) in left for j in range(h) for i in range(w)):
                left.difference_update((x0 + i, y0 + j) for j in range(h) for i in range(w))
                out.append((x0, y0, p, fp))
    assert not left, f"nie pokryte kratki: {sorted(left)[:5]}"
    return out


def flood_fill(grid, start, kind, in_bounds):
    """Paint-style fill: turns a connected (4 neighbours) area of the same kind as `start` into `kind`.

    grid: dict (x, y) -> kind; empty cells are not in the dict. kind=None clears the area.
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
    """Color distance closer to how the eye sees it than plain RGB ("redmean")."""
    r = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return ((2 + r / 256) * dr * dr + 4 * dg * dg + (2 + (255 - r) / 256) * db * db) ** 0.5


_nearest = {}


def nearest_kind(p):
    """Nearest block color, "white" for almost white, or None for transparent."""
    if p[3] < 128:
        return None
    k = p[0] >> 1, p[1] >> 1, p[2] >> 1
    if k not in _nearest:
        if color_dist(p, (255, 255, 255)) < 45:  # the lightest block is about 81 away from white
            _nearest[k] = "white"
        else:
            _nearest[k] = min((color_dist(p, v["color"]), n) for n, v in KINDS.items() if n.startswith("color"))[1]
    return _nearest[k]


def find_grid(data, w, h):
    """Grid of enlarged pixel art: (cell side, ox, oy) or None. data = RGBA bytes.

    All color changes must lie on lines every `side` pixels (97%, to survive single flaws and cropping).
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
    """Shrinks an RGBA image to nw x nh: the most common color wins in each cell, instead of mixing colors at edges."""
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
    """Image (list of rows from top to bottom, RGBA pixels, already scaled to the cell size) -> {(col, row): kind}.

    If at least 10% of the image is white, only white is background. Otherwise (e.g. a game screenshot with sky)
    the background works like a paint fill with tolerance: it starts from colors covering >= 5% of the border and from
    the most common color, and spreads to neighbouring pixels differing by less than `step` (so it follows a sky gradient).
    Background and transparent pixels stay empty, the rest gets the nearest block color. Row 0 = top of the image.
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
        # shortcut: the most common color is always background; an image without one (e.g. a full screen photo) loses that color
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
    # background cut off from the rest (e.g. sky below the floor): the same shade as a large part of the found background
    share = {}
    for x, y in bg:
        share[key(pixels[y][x])] = share.get(key(pixels[y][x]), 0) + 1
    bg |= {(x, y) for x, y in pos if share.get(key(pixels[y][x]), 0) >= 0.03 * len(pos)}
    # black bars at the top and bottom (letterbox); the darkest block is 27, so it is not affected
    for rows in (range(h), range(h - 1, -1, -1)):
        bar, pending = set(), set()
        for y in rows:
            left = [(x, y) for x in range(w) if pixels[y][x][3] >= 128 and (x, y) not in bg]
            if any(max(pixels[y][x][:3]) >= 16 for x, _ in left):
                break
            pending.update(left)
            if len(left) >= w / 2:  # a bar, not single black pixels
                bar |= pending
        bg |= bar
    colors = [(k, KINDS[k]["color"]) for k in KINDS if k.startswith("color")]
    return {(x, y): min(colors, key=lambda kc: color_dist(pixels[y][x], kc[1]))[0] for x, y in pos if (x, y) not in bg}


def fullness(grid):
    """Fullness points of a level (without the goal): colored block 5, plank and ball 10, whatever the size.

    Wire: 5 for the main entry and 5 for each part (matches the percentage shown in the game, not read from its files).
    """
    by = {}
    for c, k in grid.items():
        by.setdefault(k, set()).add(c)
    wire = by.pop("wire", set())
    total = sum(len(tile(cells, KINDS[k]["pieces"])) * (5 if k.startswith("color") else 10) for k, cells in by.items())
    return total + sum(5 * (len(run) + 1) for _, run in wire_chunks(wire, set().union(*by.values()))[0])


def agreement(small, ssize, big, bsize):
    """Share of cells of the large version that look the same in the small one (0..1)."""
    same = sum(small.get((x * ssize[0] // bsize[0], y * ssize[1] // bsize[1])) == big.get((x, y))
               for x in range(bsize[0]) for y in range(bsize[1]))
    return same / (bsize[0] * bsize[1])


def place(x0, y0, fp):
    """Position of the pivot of a block whose bottom left cell is (x0, y0)."""
    _, _, rz, minx, miny = fp
    return x0 - 0.5 - minx, y0 - 0.5 - miny, rz


def _num(v):
    return str(int(v)) if float(v).is_integer() else str(v)


def build_xml(grid, start, goal):
    """XML of a .snapshot file for BlankLevel. start = left cell of the start plank, goal = cell of the flag."""
    if start is None and goal is None:
        raise ValueError("Place the start and the goal before saving.")
    if start is None:
        raise ValueError("Place the start before saving.")
    if goal is None:
        raise ValueError("Place the goal before saving.")
    lines = []
    sid = 0
    covered = {}  # cell -> sceneID of its block (for attaching wire)

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
            # IDs as in the game: 1000000 + number*10 (the game derives the next numbers from it)
            s = block(p.block_id, px, py, rz, 1000000 + seq * 10, col)
            seq += 1
            for j in range(fp[1]):
                for i in range(fp[0]):
                    covered[(x0 + i, y0 + j)] = s
    rgb = KINDS["wire"]["rgb"]
    col = f' colR="{rgb[0]}" colG="{rgb[1]}" colB="{rgb[2]}"'
    # wire cells with no block next to them are skipped (the game would destroy them anyway); the editor warns about them
    for rz, run in wire_chunks([c for c, k in grid.items() if k == "wire"], covered)[0]:
        pid = 1000000 + seq * 10
        seq += 1
        a, s = rot((1, 0), rz), rot((0, -1), rz)
        main = block(WIRE_MAIN, run[0][0] + a[0], run[0][1] + a[1], rz, pid, col)  # main = the middle part
        for k, (x, y) in enumerate(run, 1):
            parent = covered[(x + s[0], y + s[1])]
            block(WIRE_PART, x, y, rz, pid + k,
                  f' parentID="{parent}" mainID="{main}" subElementName="BarbedwireSetPiece{k}"{col}')

    gx, gy = goal
    block(GOAL.block_id, gx, gy, 0, 2)  # placeableID 2 = the flag already in BlankLevel (the game moves it)
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
    """Saves plain XML as <name>.c.snapshot (the game accepts XML when the file starts with '<').

    Overwrites only files made by the editor (plain XML); levels saved by the game are compressed and stay untouched.
    """
    name = "".join(ch for ch in name if ch not in '<>:"/\\|?*').strip()
    if not name:
        raise ValueError("Enter a level name.")
    path = os.path.join(folder, name + ".c.snapshot")
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read(1) != b"<":
                raise ValueError("Level “{}” already exists and was not made in this editor. Choose another name.", name)
        # the old thumbnail would show the previous version; the game makes a new one the next time the level is played
        for ext in (".jpg", ".png"):
            thumb = os.path.join(folder, "thumbnails", f"l_{name}{ext}")
            if os.path.exists(thumb):
                os.remove(thumb)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return path
