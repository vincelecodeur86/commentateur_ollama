"""Genere commentateur.ico (carre noir, "C" clair et "//" vert).

Pur Python (zlib + struct) : aucune dependance. Usage :
    python installer/make_icon.py
"""

import math
import os
import struct
import zlib

TAILLES = (16, 24, 32, 48, 64, 128, 256)
SUR_ECHANTILLON = 4

FOND = (0, 0, 0)
CLAIR = (230, 230, 230)
VERT = (124, 252, 124)


def dans_carre_arrondi(x, y, marge=0.04, rayon=0.18):
    a, b = marge + rayon, 1 - marge - rayon
    dx = max(a - x, 0, x - b)
    dy = max(a - y, 0, y - b)
    return dx * dx + dy * dy <= rayon * rayon


def dans_c(x, y, cx=0.37, cy=0.5, r_ext=0.25, r_int=0.14):
    dx, dy = x - cx, y - cy
    d = math.hypot(dx, dy)
    if not (r_int <= d <= r_ext):
        return False
    # Ouverture du "C" vers la droite.
    return abs(math.degrees(math.atan2(dy, dx))) > 50


def dist_segment(x, y, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy)))
    return math.hypot(x - ax - t * vx, y - ay - t * vy)


def dans_barres(x, y, demi=0.04):
    return (dist_segment(x, y, 0.62, 0.72, 0.71, 0.28) <= demi or
            dist_segment(x, y, 0.77, 0.72, 0.86, 0.28) <= demi)


def couleur(x, y):
    if not dans_carre_arrondi(x, y):
        return None
    if dans_barres(x, y):
        return VERT
    if dans_c(x, y):
        return CLAIR
    return FOND


def rendre(taille):
    n = SUR_ECHANTILLON
    lignes = []
    for py in range(taille):
        ligne = bytearray([0])  # filtre PNG "None"
        for px in range(taille):
            r = g = b = a = 0
            for sy in range(n):
                for sx in range(n):
                    c = couleur((px + (sx + 0.5) / n) / taille, (py + (sy + 0.5) / n) / taille)
                    if c:
                        r += c[0]; g += c[1]; b += c[2]; a += 1
            if a:
                ligne += bytes((r // a, g // a, b // a, 255 * a // (n * n)))
            else:
                ligne += b"\0\0\0\0"
        lignes.append(bytes(ligne))
    return png(taille, b"".join(lignes))


def png(taille, brut):
    def bloc(genre, data):
        return (struct.pack(">I", len(data)) + genre + data +
                struct.pack(">I", zlib.crc32(genre + data) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", taille, taille, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", ihdr) +
            bloc(b"IDAT", zlib.compress(brut, 9)) + bloc(b"IEND", b""))


def ico(images):
    entete = struct.pack("<HHH", 0, 1, len(images))
    decalage = 6 + 16 * len(images)
    repertoire, donnees = b"", b""
    for taille, img in images:
        cote = 0 if taille >= 256 else taille
        repertoire += struct.pack("<BBBBHHII", cote, cote, 0, 0, 1, 32, len(img), decalage)
        donnees += img
        decalage += len(img)
    return entete + repertoire + donnees


if __name__ == "__main__":
    sortie = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commentateur.ico")
    with open(sortie, "wb") as f:
        f.write(ico([(t, rendre(t)) for t in TAILLES]))
    print("Icone ecrite :", sortie)
