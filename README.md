# UCH Level Maker

A level editor for Ultimate Chicken Horse, which can save the levels straight to UCH levelnet

## Install

1. Download **[UCH-Level-Maker-Setup.exe](https://github.com/Fiboczinajdid/uch-level-maker/releases/latest/download/UCH-Level-Maker-Setup.exe)** (Windows).
2. Run it. It needs no admin rights and puts an icon on your desktop.

The installer is not signed, so Windows may warn about an unknown publisher: click **More info**, then **Run anyway**.

## What it does

- 1 cell = 1 block in the game, boards up to 80x80.
- When saving, it optimises (merges cells into as few blocks as possible (8x8, 16x6, 4x4, 1x16...)), so more fits under the game's fullness limit and it looks better.
- All 36 block colors found in real levels, wooden planks, spikeballs, barbed wire, start and goal (can add others too in the future if anyone wants).
- Paste a picture or drop an image file: it becomes blocks, with the background removed. Pixel art is imported 1:1.
- Game view preview, undo and redo, selecting and moving, light and dark theme, English and Polish.

## Playing a level

Saved levels appear in the game under **Local Levels** on the underground computer.
The editor only overwrites its own files; levels saved by the game stay untouched.

## Running from source

Needs Python 3 on Windows (tested on 3.13):

```
pip install -r requirements.txt
python editor.py
```

Unofficial fan project, not affiliated with Clever Endeavour Games. It contains no code or art from the game.
