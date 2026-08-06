#!/usr/bin/env python3
"""
Chequea la salud de las imagenes del catalogo antes de commitear.

Detecta:
  - Imagenes referenciadas en index.html que no existen en disco
  - Archivos de 0 bytes (el caso que llego a produccion: git los acepta,
    Vercel los sirve con HTTP 200, y el browser no puede decodificarlos)
  - Archivos con contenido que no es una imagen valida (magic bytes rotos)
  - Extension que no coincide con el contenido real (warning, no error:
    los browsers sniffean el tipo igual)
  - Archivos huerfanos: existen en la carpeta pero no los usa nadie

Uso:  python3 scripts/check-imagenes.py
Sale con codigo 1 si hay errores, 0 si esta todo bien.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "index.html"
IMG_DIR = ROOT / "imagenes-supply-final"

# Firmas de archivo. Un .jpeg de verdad SIEMPRE arranca con FF D8 FF.
SIGNATURES = [
    ("jpeg", (b"\xff\xd8\xff",), {".jpg", ".jpeg"}),
    ("png", (b"\x89PNG\r\n\x1a\n",), {".png"}),
    ("gif", (b"GIF87a", b"GIF89a"), {".gif"}),
    ("webp", (b"RIFF",), {".webp"}),  # RIFF....WEBP, se valida aparte
    ("svg", (b"<svg", b"<?xml"), {".svg"}),
]

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def detect_kind(head: bytes) -> str | None:
    """Devuelve el tipo real segun los primeros bytes, o None si no es imagen."""
    for kind, magics, _ in SIGNATURES:
        if any(head.startswith(m) for m in magics):
            if kind == "webp" and head[8:12] != b"WEBP":
                continue
            return kind
    return None


def expected_kinds(suffix: str) -> set[str]:
    return {kind for kind, _, exts in SIGNATURES if suffix.lower() in exts}


def referenced_images(html: str) -> set[str]:
    """Nombres de archivo referenciados desde el HTML."""
    return set(re.findall(r"imagenes-supply-final/([A-Za-z0-9._-]+)", html))


def main() -> int:
    if not HTML.exists():
        print(f"{RED}No encuentro index.html en {ROOT}{RESET}")
        return 1

    refs = referenced_images(HTML.read_text(encoding="utf-8"))
    on_disk = {p.name for p in IMG_DIR.iterdir() if p.is_file() and p.name != ".gitkeep"}

    errors: list[str] = []
    warnings: list[str] = []

    for name in sorted(refs):
        path = IMG_DIR / name
        if not path.exists():
            errors.append(f"NO EXISTE      {name}  (referenciada en index.html)")
            continue

        size = path.stat().st_size
        if size == 0:
            errors.append(f"VACIA (0 KB)   {name}")
            continue

        head = path.read_bytes()[:16]
        kind = detect_kind(head)
        if kind is None:
            errors.append(
                f"CORRUPTA       {name}  ({size:,} bytes, pero no es una imagen valida)"
            )
            continue

        expected = expected_kinds(path.suffix)
        if expected and kind not in expected:
            warnings.append(
                f"EXTENSION      {name}  es {kind.upper()} de verdad, no {path.suffix.lstrip('.').upper()}"
            )

    orphans = sorted(on_disk - refs)

    print(f"\n{DIM}Referenciadas: {len(refs)}  ·  En disco: {len(on_disk)}{RESET}\n")

    for e in errors:
        print(f"  {RED}✗{RESET}  {e}")
    for w in warnings:
        print(f"  {YELLOW}!{RESET}  {w}")
    for o in orphans:
        print(f"  {DIM}·  HUERFANA      {o}  (existe pero no la usa ningun producto){RESET}")

    if not errors and not warnings and not orphans:
        print(f"  {GREEN}✓{RESET}  Todas las imagenes estan sanas.\n")
        return 0

    print()
    if errors:
        print(f"{RED}{len(errors)} imagen(es) rota(s). Se van a ver mal en la web.{RESET}\n")
        return 1

    print(f"{GREEN}Sin errores bloqueantes.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
