# Format pliku `.snapshot` (sprawdzone 2026-11-24)

## Plik
- Gra zapisuje XML skompresowany LZMA „alone” (Python: `lzma.decompress(b, format=lzma.FORMAT_ALONE)`).
- `QuickSaver.TryLoadSnapshotXMLFromBytes`: jeśli pierwszy bajt to `<`, czyta zwykły XML. Edytor zapisuje zwykły XML.
- Lista leveli w grze (`UndergroundComputer.RefreshLocalSavesList`) to po prostu nazwy plików `*.snapshot` w folderze
  `snapshots`; przyrostek `.c` = challenge, `.v` = versus, brak = inne.

## XML
```
<scene levelSceneName="BlankLevel" saveFormatVersion="1" customLevelBackground="1" customLevelMusic="10" customLevelAmbience="10">
  <mods .../>                (opcjonalne; bez niego gra ustawia domyślne modyfikatory)
  <block sceneID blockID pX pY pZ rX rY rZ sX sY sZ [parentID mainID subElementName] placeableID [colR colG colB] />
  <moved placeableID path="StartPlank|LeftWall|RightWall|Ceiling|DeathPit" pX pY ... />   (elementy sceny)
  <destroyed path="GoalBlock" />
</scene>
```
- `levelSceneName` musi się zgadzać ze sceną, inaczej gra nie wczyta. Levele robione od zera to `BlankLevel`.
- `blockID` = indeks w `PlaceableMetadataList.allBlockPrefabs` (104 prefaby). Lista wyciągnięta z plików gry
  (`sharedassets2.assets`) biblioteką UnityPy. Najważniejsze: 0 `01_1x1 Box`, 1–5 deski 2–6 (`06_Beam` = 6),
  10 `11_1x1 Spike Block`, 11–13 drut x1–x3, 38 `StartPlank`, 39 `GoalBlock`, 40–50 `SetPiece` (1x1, 1x2, 1x3, 1x4, 1x8,
  1x14 (collider 16!), 2x4, 2x2, 4x4, 8x8, 16x6), 55 drut x3 SetPiece, 70 `InvisibleWall`.
- Rozmiar i punkt zaczepienia: z `SolidCollider` prefabu. Np. `101_SetPiece1x2` zajmuje x -0.5..1.5, więc jego pozycja
  to lewa kratka; `02_Plank2` ma środek na `.5`. Tabela jest w `uch_level.py`.
- Obrót `rZ` w stopniach przeciwnie do zegara: (x, y) -> (-y, x) dla 90. Sprawdzone na 530 levelach: z tą konwencją
  klocki prawie się nie nakładają (1%), z odwrotną 6x więcej.
- `placeableID`: gra używa 1000000 + numer*10 (+1 dla pod-elementów). `GoalBlock` z `placeableID="2"` przesuwa flagę,
  która już jest w BlankLevel (pętla w `QuickSaver` szuka obiektu sceny o tym samym ID).
- Drut x1 (11) = dwa wpisy: główny i pod-element `BarbedwirePiece` z `mainID` i `parentID` (klocek, do którego jest
  przyczepiony).
- Drut x3 SetPiece = wpis główny `blockID=55` (bez rodzica) + 1–3 części `blockID=13`, `subElementName=BarbedwireSetPiece1..3`,
  każda z `mainID` i `parentID` (klocek pod nią w układzie obróconym: rZ 0 leży, 180 wisi, 90 klocek z prawej, 270 z lewej).
  Przy rZ 0 część 1 jest na x-1 od głównego, 2 na głównym, 3 na x+1. Brakujące części są OK (1–2 kratki).
  Sam wpis 55 bez części gra niszczy („Destroying unused sub-element BarbedwireSetPiece1”) i drutu nie ma.
- Ściany przy domyślnym rozmiarze: LeftWall x=-41, RightWall x=40, Ceiling y=15, DeathPit y=-31.
  Ich krawędź jest 4.5 od pozycji (zmierzone w grze): wolne kratki x -36..35, y -26..10 (sufit nie sprawdzony).
- Drut x3 SetPiece (55) bez `colR/G/B` nie pojawił się w grze. Klocki kolorowalne zawsze zapisuj z kolorem.
- `GoalBlock`: strefa mety ok. 4x4 nad flagą, przesunięta w lewo (x -2.45..1.45, y 0.55..4.45).
- `StartPlank`: deska 4x1 + strefa startu 4x4 nad nią.
- Zapełnienie: `GameSettings.LevelFullnessScoreLimit` = 5000, koszt = `Placeable.placementCost` (SetPiece 5, deski/kula/meta 10,
  strzelające 100, większość ruchomych 30). Ponad limit kod gry blokuje publikowanie; blokady wczytywania nie znalazłem.
  W folderze są levele powyżej 5000.
- Największe plansze w folderze: 110x79 (20 leveli), najszersze ok. 113, najwyższe 90.
