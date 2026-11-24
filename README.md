# UCH level maker

Level editor for Ultimate Chicken Horse (Windows, Python): draw on a grid or paste an image, and it saves a playable
level made of as few blocks as possible. The editor itself has an English mode (Settings); the docs below are in Polish.

Nieoficjalny, fanowski projekt, niezwiązany z Clever Endeavour Games. Repo nie zawiera kodu ani grafik z gry.

Edytor leveli do Ultimate Chicken Horse w osobnym oknie. Rysujesz level na kratkach (1 kratka = 1 klocek w grze),
a przy zapisie edytor łączy kratki tego samego rodzaju w jak najmniej dużych klocków (8x8, 16x6, 4x4, 1x16…).

## Uruchomienie
Windows i Python 3 (sprawdzane na 3.13):
```
pip install -r requirements.txt
python editor.py
```

## Sterowanie
- **LPM**: rysuj (przytrzymaj, żeby rysować ciągle). **Gumka**: przycisk albo **G**
- **PPM**: zaznacz prostokąt, potem przeciągnij zaznaczenie (lewym albo prawym), żeby je przesunąć. **Delete**, **Backspace** albo przycisk „Usuń zaznaczenie” usuwa je razem ze startem i metą, **Esc** odznacza
- **Kółko myszy**: w górę przybliża, w dół oddala (rozmiar siatki się nie zmienia). Wciśnięte kółko przesuwa widok
- Zakładka **Kolory**: 36 kolorów klocków z gry. Zakładka **Przedmioty** (klawisze 1–5): drewno, kolczasta kula, drut kolczasty, start, meta
- **P** pędzel, **W** wypełnianie jak w Paincie (po angielsku skróty są od angielskich nazw: B, E, F, L, G)
- **K**: podgląd, jak kratki zostaną połączone w klocki (i ile ich będzie)
- **I**: widok jak w grze (niebo, bez siatki, klocki złączone tak jak przy zapisie)
- **Obraz na kratki**: zrzut ekranu (Win+Shift+S) i **Ctrl+V** albo przycisk „Wklej obraz”, albo przeciągnij plik obrazka na okno. Białe tło (albo niebo na zrzucie z gry) zostaje puste, reszta dostaje najbliższy kolor z palety. Powiększony pixel art (np. 1440x740 = 72x37 po 20 pikseli) wczytuje się 1:1
- **Plansza**: domyślnie 40x40. Wpisz szerokość i wysokość (10–80) albo zmień je strzałkami lub kółkiem nad polem i kliknij **Zastosuj** (Enter). Możesz też przeciągnąć krawędź lub róg siatki. Wklejony obrazek sam wybiera najmniejszą planszę, na której nie gubi szczegółów i mieści się w limicie zapełnienia gry (5000 punktów: klocek kolorowy 5, deska i kula 10, bez względu na rozmiar). Dopóki nie zmienisz kratek, nowy wymiar dopasowuje obrazek do planszy, a przycisk **Auto** wraca do rozmiaru wybranego samo. Obrazek do 80x80 pikseli: 1 piksel = 1 kratka
- **Ustawienia**: tryb jasny/ciemny, English/Polski i lista sterowania. Skróty P, G, W, K, I można tam zmienić (klik w literę, potem nowa litera; osobno dla każdego języka). Wybór zapisuje się w `settings.json`
- **Cofnij** (Ctrl+Z) i **Ponów** (Ctrl+Y): przyciski albo klawisze; cofa też „Wyczyść wszystko”. **Ctrl+S** zapisz; żółty przycisk i gwiazdka w tytule okna = są niezapisane zmiany
- Start (deska 4x1) i meta (flaga): kliknij, żeby postawić albo przesunąć. Przezroczyste pola nad nimi to strefa startu i mety.

## Granie
Zapis tworzy `<nazwa>.c.snapshot` w folderze gry
`%USERPROFILE%\AppData\LocalLow\Clever Endeavour Games\Ultimate Chicken Horse\snapshots`.
W grze level jest na liście Twoich leveli (komputer w podziemiach, zakładka challenge).
Edytor nadpisuje tylko swoje pliki; levelu zapisanego przez grę o tej samej nazwie nie ruszy.

## Pliki
- `editor.py`: okno edytora
- `lang.py`: angielskie teksty
- `uch_level.py`: klocki z gry, łączenie kratek w klocki, wypełnianie, zapis XML
- `test_uch_level.py`, `test_editor.py`: testy (uruchom przez `python`)
- `notes/format-snapshot.md`: jak zbudowany jest plik `.snapshot`
