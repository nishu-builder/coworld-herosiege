from __future__ import annotations

import struct
import zlib
from pathlib import Path

TILE = 16
TRANSPARENT = (0, 0, 0, 0)

PALETTES: dict[str, dict[str, tuple[int, int, int, int]]] = {
    "hero_knight": {
        ".": TRANSPARENT,
        "s": (210, 214, 222, 255),
        "S": (140, 146, 158, 255),
        "p": (60, 110, 210, 255),
        "e": (24, 26, 36, 255),
    },
    "monster_skeleton": {
        ".": TRANSPARENT,
        "b": (228, 228, 214, 255),
        "B": (170, 170, 156, 255),
        "e": (20, 20, 24, 255),
    },
    "monster_demon": {
        ".": TRANSPARENT,
        "r": (198, 44, 60, 255),
        "R": (130, 22, 34, 255),
        "h": (240, 196, 70, 255),
        "e": (24, 8, 10, 255),
    },
    "sanctum": {
        ".": TRANSPARENT,
        "g": (245, 200, 70, 255),
        "G": (200, 150, 40, 255),
        "f": (255, 240, 180, 255),
        "s": (120, 100, 60, 255),
    },
    "demon_portal": {
        ".": TRANSPARENT,
        "p": (162, 60, 214, 255),
        "P": (96, 30, 140, 255),
        "v": (230, 180, 255, 255),
        "e": (30, 12, 44, 255),
    },
    "gold_shrine": {".": TRANSPARENT, "g": (245, 200, 70, 255), "G": (190, 140, 40, 255), "s": (150, 120, 70, 255)},
}

GLYPHS: dict[str, list[str]] = {
    "hero_knight": [
        "......ss........",
        ".....ssss.......",
        ".....sSSs.......",
        ".....seeS.......",
        "....ssssss......",
        "...sppSppps.....",
        "..sppppppps.....",
        "..spppppppps....",
        "..sSppppppSs....",
        "...sppppppp.....",
        "....ss..ss......",
        "....sS..Ss......",
        "...sSs..sSs.....",
        "...ss....ss.....",
        "................",
        "................",
    ],
    "monster_skeleton": [
        "................",
        ".....bbbb.......",
        "....bBbbBb......",
        "....beebee......",
        "....bbBBbb......",
        ".....bbbb.......",
        "....bbbbbb......",
        "...bb bbbb bb...",
        "..b..bbbb..b....",
        ".....bbbb.......",
        ".....b..b.......",
        "....bb..bb......",
        "....b....b......",
        "...bb....bb.....",
        "................",
        "................",
    ],
    "monster_demon": [
        "...h......h.....",
        "...hh....hh.....",
        "....rrRRrr......",
        "...rRrrrrRr.....",
        "...reRrrRer.....",
        "...rrrRRrrr.....",
        "...rRrrrrRr.....",
        "..rrrrrrrrrr....",
        ".rRrrrrrrrrRr...",
        ".rrrrrrrrrrrr...",
        "..rr.rrrr.rr....",
        "..rR..rr..Rr....",
        "..rr..rr..rr....",
        ".rrr..rr..rrr...",
        "................",
        "................",
    ],
    "sanctum": [
        ".......ff.......",
        "......ffff......",
        ".....ffffff.....",
        "......ffff......",
        "....g.ffff.g....",
        "...gg.ffff.gg...",
        "..gGgggggggGg...",
        "..gGGGGGGGGGg...",
        "..gGgggggggGg...",
        "..gGGGGGGGGGg...",
        "..gGgggggggGg...",
        "..ssssssssssss..",
        ".ssssssssssssss.",
        "..ssssssssssss..",
        "................",
        "................",
    ],
    "demon_portal": [
        "....pppppp......",
        "...pPPPPPPp.....",
        "..pPvvvvvvPp....",
        "..pPvppppvPp....",
        ".pPvpeeeePpvPp..",
        ".pPvpePPePpvPp..",
        ".pPvpePPePpvPp..",
        ".pPvpeeeePpvPp..",
        "..pPvppppvPp....",
        "..pPvvvvvvPp....",
        "...pPPPPPPp.....",
        "....pppppp......",
        ".....e..e.......",
        "................",
        "................",
    ],
    "gold_shrine": [
        "................",
        ".....gggg.......",
        "....gGGGGg......",
        "...gGggggGg.....",
        "...gGggggGg.....",
        "....gGGGGg......",
        ".....gggg.......",
        "......gg........",
        ".....ssss.......",
        "....ssssss......",
        "...ssssssss.....",
        "..ssssssssss....",
        ".ssssssssssss...",
        "ssssssssssssss..",
        "................",
        "................",
    ],
}


def _png(path: Path, glyph: list[str], palette: dict[str, tuple[int, int, int, int]]) -> None:
    raw = bytearray()
    for row in glyph:
        cells = row.ljust(TILE, ".")[:TILE]
        raw.append(0)
        for ch in cells:
            raw.extend(palette.get(ch, TRANSPARENT))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", TILE, TILE, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def main() -> None:
    out = Path(__file__).parent
    for name, glyph in GLYPHS.items():
        _png(out / f"{name}.png", glyph, PALETTES[name])
        print(f"wrote {name}.png")


if __name__ == "__main__":
    main()
