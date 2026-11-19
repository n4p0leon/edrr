"""
SHADOW FIGHTER — 2D файтинг на pygame
Главное меню, выбор бойца и оружия, режим 1 игрок (vs ИИ) и 2 игрока,
раунды (до 2 побед), цепочки комбо, кувырки и «человеческие» персонажи
(скелет с суставами вместо палочек).

Запуск:  python shadow_fighter.py
"""
import math
import random
import sys

import pygame

pygame.init()

WIDTH, HEIGHT, FPS = 1280, 720, 60
GROUND = 612            # линия пола (y, где стоят ноги)
GRAV = 0.75
ROUNDS_TO_WIN = 2
ROUND_TIME = 99

try:
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
except pygame.error:
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Shadow Fighter")
clock = pygame.time.Clock()
canvas = pygame.Surface((WIDTH, HEIGHT))
fx_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

FONT = pygame.font.Font(None, 34)
SMALL_FONT = pygame.font.Font(None, 24)
MID_FONT = pygame.font.Font(None, 52)
BIG_FONT = pygame.font.Font(None, 130)

WHITE = (255, 255, 255)
GREEN = (80, 220, 120)
RED = (235, 80, 80)
GOLD = (255, 214, 102)
OUTLINE = (16, 14, 24)


# ==================== УТИЛИТЫ ====================

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mixc(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(c, k):
    return tuple(clamp(int(v * k), 0, 255) for v in c)


def vec(a_deg, length):
    """Вектор «от вертикали вниз»: 0° — вниз, +90° — вперёд, 180° — вверх."""
    r = math.radians(a_deg)
    return math.sin(r) * length, math.cos(r) * length


def vec_up(a_deg, length):
    """Вектор вверх с наклоном вперёд на a_deg."""
    r = math.radians(a_deg)
    return math.sin(r) * length, -math.cos(r) * length


def add(a, b, k=1.0):
    return a[0] + b[0] * k, a[1] + b[1] * k


def unit(v):
    d = math.hypot(v[0], v[1]) or 1.0
    return v[0] / d, v[1] / d


def text(surf, font, s, color, pos, anchor="center", shadow=True):
    img = font.render(s, True, color)
    r = img.get_rect()
    setattr(r, anchor, pos)
    if shadow:
        surf.blit(font.render(s, True, (0, 0, 0)), r.move(2, 2))
    surf.blit(img, r)
    return r


# ==================== ПОЗЫ (скелетная анимация) ====================
# Углы в градусах: 0 — вниз, +90 — вперёд, 180 — вверх (в сторону, куда смотрит боец).
# lean — наклон корпуса, fs/fe — плечо/локоть передней руки, bs/be — задней,
# fh/fk — бедро/колено передней ноги, bh/bk — задней, rot — поворот всего тела (кувырок, падение)

STAND = dict(lean=5, fs=40, fe=95, bs=25, be=110, fh=18, fk=12, bh=-16, bk=14, rot=0, hd=0)
POSE_KEYS = tuple(STAND)


def pz(**kw):
    d = dict(STAND)
    d.update(kw)
    return d


def mix(a, b, t):
    return {k: a[k] + (b[k] - a[k]) * t for k in POSE_KEYS}


def swap_arms(p):
    q = dict(p)
    q["fs"], q["fe"], q["bs"], q["be"] = p["bs"], p["be"], p["fs"], p["fe"]
    return q


CROUCH = pz(lean=14, fh=68, fk=118, bh=44, bk=108)
BLOCK = pz(lean=-2, fs=55, fe=100, bs=45, be=105)
CBLOCK = pz(lean=10, fs=55, fe=100, bs=45, be=105, fh=68, fk=118, bh=44, bk=108)
JUMP = pz(lean=4, fs=70, fe=60, bs=50, be=60, fh=60, fk=80, bh=20, bk=70)
TUCK = pz(lean=28, fs=100, fe=95, bs=90, be=100, fh=100, fk=130, bh=85, bk=130)
HURT = pz(lean=-20, fs=15, fe=35, bs=-35, be=25, fh=22, fk=25, bh=-24, bk=22, hd=-18)
LAUNCH = pz(lean=-30, fs=120, fe=25, bs=100, be=25, fh=45, fk=40, bh=12, bk=50, rot=-35)
DOWN = pz(lean=0, fs=15, fe=8, bs=-8, be=8, fh=6, fk=0, bh=-4, bk=0, rot=-90)
WIN = pz(lean=-4, fs=165, fe=12, bs=170, be=10, fh=10, fk=5, bh=-10, bk=5)


# ==================== БОЙЦЫ И ОРУЖИЕ ====================

CHARACTERS = [
    dict(name="SHADOW", hp=100, speed=5.0, dmg=1.00, scale=1.00, jump=14.0,
         desc="Balanced assassin",
         look=dict(skin=(232, 190, 150), hair=(25, 25, 35), style="spiky",
                   shirt=(44, 46, 64), pants=(30, 32, 46), shoes=(18, 18, 24),
                   belt=(210, 50, 60), band=(210, 50, 60), scarf=(210, 50, 60),
                   sleeves="long", wraps=(220, 220, 230))),
    dict(name="NINJA", hp=92, speed=5.7, dmg=0.95, scale=0.98, jump=15.0,
         desc="Fast & agile",
         look=dict(skin=(226, 180, 140), hair=None, style="hood",
                   shirt=(40, 74, 118), pants=(34, 56, 92), shoes=(20, 24, 36),
                   belt=(230, 200, 80), band=(230, 230, 240), scarf=None,
                   sleeves="long", wraps=(210, 210, 220))),
    dict(name="SAMURAI", hp=112, speed=4.4, dmg=1.15, scale=1.03, jump=13.5,
         desc="Slow but deadly",
         look=dict(skin=(214, 170, 130), hair=(20, 20, 24), style="topknot",
                   shirt=(228, 228, 236), pants=(150, 32, 44), shoes=(40, 30, 30),
                   belt=(30, 30, 44), band=None, scarf=None,
                   sleeves="long", wraps=None, wide=1.3)),
    dict(name="BRAWLER", hp=128, speed=4.0, dmg=1.10, scale=1.10, jump=13.0,
         desc="Tough bruiser",
         look=dict(skin=(205, 150, 110), hair=(232, 190, 80), style="short",
                   shirt=(242, 242, 242), pants=(50, 82, 150), shoes=(200, 200, 205),
                   belt=(120, 80, 40), band=(220, 60, 40), scarf=None,
                   sleeves="none", wraps=(240, 240, 240))),
]

WEAPONS = [
    dict(id="fists", name="FISTS", dmg=1.00, reach=0, spd=1.00, desc="Fast, no reach bonus"),
    dict(id="sword", name="KATANA", dmg=1.30, reach=58, spd=1.15, desc="Balanced blade"),
    dict(id="staff", name="BO STAFF", dmg=1.10, reach=58, spd=1.20, desc="Long reach"),
    dict(id="nunchaku", name="NUNCHAKU", dmg=1.10, reach=26, spd=0.90, desc="Quick strikes"),
    dict(id="dagger", name="KUNAI", dmg=0.95, reach=22, spd=0.80, desc="Very fast, short"),
    dict(id="axe", name="WAR AXE", dmg=1.65, reach=42, spd=1.45, desc="Slow, huge damage"),
]


# ==================== ТАБЛИЦА АТАК ====================
# s/a/r — кадры замаха/активной фазы/восстановления, dmg — урон, reach — дальность (px),
# y — высота хитбокса над землёй, push — отбрасывание, hs — хитстоп, kd — сбивает с ног,
# chain — на какую клавишу можно продолжить комбо

ATTACKS = {
    "jab": dict(kind="punch", s=4, a=3, r=8, dmg=4, reach=62, y=(80, 150), push=20, hs=3, stun=14,
                limb="f", ps=pz(fs=30, fe=110),
                pa=pz(lean=12, fs=88, fe=3, fh=26, fk=22, bh=-22, bk=10),
                chain={"J": "cross", "K": "kick", "L": "heavy"}),
    "cross": dict(kind="punch", s=5, a=3, r=10, dmg=5, reach=66, y=(80, 150), push=26, hs=4, stun=15,
                  limb="b", back=True, ps=pz(bs=10, be=125, lean=-6),
                  pa=pz(lean=20, bs=88, be=3, fs=45, fe=100, fh=32, fk=28, bh=-30, bk=8),
                  chain={"J": "hook", "K": "kick", "L": "heavy"}),
    "hook": dict(kind="punch", s=7, a=4, r=18, dmg=8, reach=72, y=(80, 160), push=40, hs=7, kd=True,
                 limb="f", ps=pz(lean=-14, fs=150, fe=40, fh=10, fk=15, bh=-25, bk=10),
                 pa=pz(lean=24, fs=75, fe=15, fh=38, fk=30, bh=-34, bk=5), chain={}),
    "kick": dict(kind="kick", s=6, a=3, r=10, dmg=5, reach=78, y=(35, 120), push=30, hs=4, stun=15,
                 limb="lf", ps=pz(lean=-6, fh=75, fk=100),
                 pa=pz(lean=-12, fh=88, fk=4, bh=-6, bk=6),
                 chain={"K": "round", "J": "cross", "L": "heavy"}),
    "round": dict(kind="kick", s=7, a=4, r=14, dmg=7, reach=82, y=(90, 165), push=36, hs=5, stun=17,
                  limb="lf", ps=pz(lean=-8, fh=50, fk=115),
                  pa=pz(lean=-30, fh=108, fk=6, bh=-8, bk=4, fs=60, fe=70, bs=-30, be=40),
                  chain={"K": "spin", "J": "hook"}),
    "spin": dict(kind="kick", s=8, a=4, r=20, dmg=10, reach=88, y=(70, 165), push=60, hs=8, kd=True,
                 limb="lb", ps=pz(lean=12, fs=70, fe=60, bs=50, be=70, fh=30, fk=40, bh=-30, bk=60),
                 pa=pz(lean=-34, bh=100, bk=0, fh=-6, fk=6, fs=110, fe=0, bs=-70, be=0), chain={}),
    "heavy": dict(kind="kick", s=12, a=4, r=20, dmg=11, reach=90, y=(95, 170), push=70, hs=9, kd=True,
                  limb="lb", ps=pz(lean=8, bh=70, bk=120, fs=60, fe=80),
                  pa=pz(lean=-34, bh=102, bk=0, fh=-6, fk=6, fs=110, fe=0, bs=-70, be=0), chain={}),
    "upper": dict(kind="punch", s=6, a=4, r=18, dmg=8, reach=58, y=(50, 178), push=40, hs=8, kd=True,
                  launch=13, limb="f", ps=pz(lean=16, fs=0, fe=100, fh=60, fk=100, bh=40, bk=100),
                  pa=pz(lean=10, fs=125, fe=25, fh=20, fk=10, bh=-18, bk=10), chain={}),
    "sweep": dict(kind="kick", s=7, a=5, r=20, dmg=6, reach=92, y=(0, 24), push=30, hs=5, kd=True,
                  low=True, limb="lf", ps=pz(lean=18, fh=70, fk=105, bh=45, bk=110),
                  pa=pz(lean=28, fh=84, fk=2, bh=85, bk=160, fs=-20, fe=40, bs=-10, be=30), chain={}),
    "lunge": dict(kind="punch", s=8, a=5, r=16, dmg=7, reach=76, y=(80, 150), push=36, hs=5, lunge=6,
                  limb="f", ps=pz(lean=-8, fs=70, fe=60, fh=30, fk=50, bh=-30, bk=30),
                  pa=pz(lean=30, fs=90, fe=0, fh=55, fk=30, bh=-38, bk=6), chain={"J": "hook"}),
    "dkick": dict(kind="kick", s=7, a=5, r=14, dmg=7, reach=82, y=(50, 125), push=40, hs=5, lunge=6,
                  limb="lf", ps=pz(lean=-10, fh=80, fk=100),
                  pa=pz(lean=-18, fh=92, fk=2, bh=-8, bk=4), chain={"K": "round"}),
    # --- воздушные ---
    "airj": dict(kind="punch", air=True, s=3, a=8, r=8, dmg=5, reach=64, y=(10, 125), push=20, hs=3,
                 limb="f", ps=pz(lean=6, fs=50, fe=90, fh=60, fk=80, bh=20, bk=70),
                 pa=pz(lean=10, fs=82, fe=8, fh=60, fk=80, bh=20, bk=70), chain={}),
    "airk": dict(kind="kick", air=True, s=3, a=10, r=8, dmg=7, reach=76, y=(-10, 80), push=30, hs=4,
                 limb="lf", ps=pz(lean=0, fh=70, fk=90, bh=20, bk=70),
                 pa=pz(lean=-12, fh=95, fk=8, bh=30, bk=80, fs=60, fe=70), chain={}),
    "airl": dict(kind="punch", air=True, s=5, a=14, r=6, dmg=9, reach=62, y=(-40, 110), push=30, hs=7,
                 kd=True, dive=11, limb="f",
                 ps=pz(lean=10, fs=170, fe=15, bs=165, be=15, fh=40, fk=60, bh=20, bk=60),
                 pa=pz(lean=34, fs=95, fe=30, bs=90, be=30, fh=70, fk=95, bh=40, bk=95), chain={}),
    # --- атаки в сальто вперёд ---
    "flipk": dict(kind="kick", air=True, s=6, a=26, r=0, dmg=10, reach=74, y=(-30, 95), push=50, hs=7,
                  kd=True, limb="lf", ps=TUCK,
                  pa=pz(lean=28, fh=105, fk=5, bh=80, bk=125, fs=100, fe=95, bs=90, be=100), chain={}),
    "flipj": dict(kind="punch", air=True, s=6, a=26, r=0, dmg=9, reach=70, y=(-20, 110), push=45, hs=7,
                  kd=True, limb="f", ps=TUCK,
                  pa=pz(lean=28, fs=100, fe=5, bs=90, be=100, fh=100, fk=130, bh=85, bk=130), chain={}),
}


# ==================== ЭФФЕКТЫ ====================

particles = []
rings = []


def spawn(x, y, color, count, speed, size):
    for _ in range(count):
        a = random.uniform(0, math.tau)
        v = random.uniform(speed * 0.3, speed)
        particles.append([x, y, math.cos(a) * v, math.sin(a) * v - 1,
                          random.randint(14, 28), color, random.uniform(size * 0.5, size)])


def update_effects():
    for p in particles:
        p[0] += p[2]
        p[1] += p[3]
        p[3] += 0.25
        p[2] *= 0.97
        p[4] -= 1
    particles[:] = [p for p in particles if p[4] > 0]
    for r in rings:
        r[2] += r[3]
        r[3] *= 0.86
        r[4] -= 14
    rings[:] = [r for r in rings if r[4] > 0]


def draw_effects(surf):
    for p in particles:
        pygame.draw.circle(surf, p[5], (int(p[0]), int(p[1])), max(1, int(p[6] * min(1, p[4] / 12))))
    for r in rings:
        pygame.draw.circle(fx_layer, (255, 240, 200, clamp(int(r[4]), 0, 255)),
                           (int(r[0]), int(r[1])), int(r[2]), 3)


# ==================== СКЕЛЕТ И РИСОВАНИЕ ПЕРСОНАЖА ====================

def skeleton(f):
    """Считает позиции суставов (в мировых координатах) по текущей позе бойца."""
    s, p = f.scale, f.pose
    TORSO, UA, FA, TH, SH, FT = 54 * s, 28 * s, 26 * s, 38 * s, 38 * s, 14 * s
    tv = vec_up(p["lean"], TORSO)
    pts = {"hip": (0.0, 0.0), "sh": tv, "pv": (tv[0] * 0.93, tv[1] * 0.93)}
    hv = vec_up(p["lean"] * 0.6 + p["hd"], 27 * s)
    pts["head"] = (tv[0] + hv[0], tv[1] + hv[1])

    def arm(a, e, k):
        el = add(pts["pv"], vec(a, UA))
        pts["e" + k] = el
        pts["h" + k] = add(el, vec(a + e, FA))

    def leg(h, kn, k):
        knee = vec(h, TH)
        ank = add(knee, vec(h - kn, SH))
        toe = add(ank, vec(clamp(90 + (h - kn) * 0.35, 30, 125), FT))
        pts["k" + k], pts["a" + k], pts["t" + k] = knee, ank, toe

    arm(p["fs"], p["fe"], "f")
    arm(p["bs"], p["be"], "b")
    leg(p["fh"], p["fk"], "f")
    leg(p["bh"], p["bk"], "b")

    low0 = max(pts["af"][1] + 6 * s, pts["ab"][1] + 6 * s, pts["tf"][1] + 3 * s, pts["tb"][1] + 3 * s)

    rot = p["rot"]
    if abs(rot) > 0.01:
        c = (tv[0] * 0.5, tv[1] * 0.5)
        cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        for k, (x, y) in list(pts.items()):
            dx, dy = x - c[0], y - c[1]
            pts[k] = (c[0] + dx * cr - dy * sr, c[1] + dx * sr + dy * cr)

    if f.state in ("down", "getup", "dead"):      # лежим — прижимаем самую низкую точку к полу
        low = max(y + (13 if k == "head" else 7) * s for k, (x, y) in pts.items())
    else:
        low = low0
    oy = f.gy - f.air - low
    return {k: (f.x + f.facing * x, oy + y) for k, (x, y) in pts.items()}


def chain(surf, segs):
    """Рисует цепочку сегментов (a, b, ширина_a, ширина_b, цвет) с общей обводкой."""
    for outline in (True, False):
        for a, b, wa, wb, col in segs:
            ra = wa / 2 + (2 if outline else 0)
            rb = wb / 2 + (2 if outline else 0)
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / ln, dx / ln
            c = OUTLINE if outline else col
            pygame.draw.polygon(surf, c, [(a[0] + nx * ra, a[1] + ny * ra), (b[0] + nx * rb, b[1] + ny * rb),
                                          (b[0] - nx * rb, b[1] - ny * rb), (a[0] - nx * ra, a[1] - ny * ra)])
            pygame.draw.circle(surf, c, (int(a[0]), int(a[1])), max(1, int(ra)))
            pygame.draw.circle(surf, c, (int(b[0]), int(b[1])), max(1, int(rb)))


def dot(surf, pos, r, col):
    pygame.draw.circle(surf, OUTLINE, (int(pos[0]), int(pos[1])), int(r + 2))
    pygame.draw.circle(surf, col, (int(pos[0]), int(pos[1])), int(r))


def draw_head(surf, f, C):
    P, L, s = f.pts, f.look, f.scale
    head, sh = P["head"], P["sh"]
    u = unit((head[0] - sh[0], head[1] - sh[1]))
    fw = (-u[1] * f.facing, u[0] * f.facing)
    R = 13 * s

    def hp(a, b):
        return head[0] + fw[0] * a * s + u[0] * b * s, head[1] + fw[1] * a * s + u[1] * b * s

    def pie(a0, a1, rad, col, cx=-2.0):
        pts = [hp(cx, 0)]
        n = 8
        for i in range(n + 1):
            ang = math.radians(a0 + (a1 - a0) * i / n)
            pts.append(hp(math.cos(ang) * rad, math.sin(ang) * rad))
        pygame.draw.polygon(surf, col, pts)

    style = L["style"]
    skin = C(L["skin"])
    if style == "hood":
        dot(surf, head, R, C(L["shirt"]))
        pygame.draw.polygon(surf, skin, [hp(3, 3.5), hp(13, 3.5), hp(13, -2), hp(3, -2)])
    else:
        dot(surf, head, R, skin)
        hair = C(L["hair"])
        if style == "spiky":
            for ang, ln in ((70, 1.7), (105, 1.8), (140, 1.8), (175, 1.6), (210, 1.4)):
                a1 = math.radians(ang)
                a0, a2 = math.radians(ang - 14), math.radians(ang + 14)
                pygame.draw.polygon(surf, hair, [hp(math.cos(a0) * 13, math.sin(a0) * 13),
                                                 hp(math.cos(a1) * 13 * ln, math.sin(a1) * 13 * ln),
                                                 hp(math.cos(a2) * 13, math.sin(a2) * 13)])
            pie(35, 245, 13.5, hair)
        elif style == "topknot":
            dot(surf, hp(-9, 17), 5 * s, hair)
            pie(30, 250, 13.5, hair)
        else:
            pie(40, 230, 13.5, hair)
        # глаз и бровь
        pygame.draw.circle(surf, WHITE, tuple(map(int, hp(7.5, 1))), max(2, int(3 * s)))
        pygame.draw.circle(surf, OUTLINE, tuple(map(int, hp(8.5, 1))), max(1, int(1.7 * s)))
        pygame.draw.line(surf, OUTLINE, hp(4, 5.5), hp(11, 3.5), max(1, int(2 * s)))
    if L.get("band"):
        bc = C(L["band"])
        pygame.draw.line(surf, bc, hp(-12, 6), hp(12.5, 6.5), max(2, int(4 * s)))
        sw = math.sin(f.time * 0.2) * 3
        pygame.draw.line(surf, bc, hp(-12, 6), hp(-24, 3 + sw), max(2, int(3 * s)))
        pygame.draw.line(surf, bc, hp(-12, 6), hp(-32, -1 + sw * 1.6), max(2, int(3 * s)))


def draw_weapon(surf, f, C):
    shapes, tip = f.weapon_shapes()
    for sh in shapes:
        if sh[0] == "line":
            pygame.draw.line(surf, OUTLINE, sh[1], sh[2], int(sh[3]) + 3)
        else:
            pygame.draw.polygon(surf, OUTLINE, sh[1], 3)
    for sh in shapes:
        if sh[0] == "line":
            pygame.draw.line(surf, C(sh[4]), sh[1], sh[2], max(1, int(sh[3])))
        else:
            pygame.draw.polygon(surf, C(sh[2]), sh[1])


def draw_fighter(surf, f):
    P, L, s = f.pts, f.look, f.scale
    flash = f.flash > 0

    def C(c):
        return mixc(c, WHITE, 0.65) if flash else c

    # тень на полу
    k = 1 - min(0.7, f.air / 260)
    pygame.draw.ellipse(surf, (28, 20, 28),
                        (f.x - 38 * s * k, f.gy - 6 * s * k, 76 * s * k, 14 * s * k))

    sleeve = L["shirt"] if L["sleeves"] in ("short", "long") else L["skin"]
    fore = L["shirt"] if L["sleeves"] == "long" else L["skin"]
    wide = L.get("wide", 1.0)

    def arm(k, dark):
        m = 0.72 if dark else 1.0
        chain(surf, [(P["pv"], P["e" + k], 10 * s, 9 * s, C(shade(sleeve, m))),
                     (P["e" + k], P["h" + k], 9 * s, 7 * s, C(shade(fore, m)))])

    def hand(k, dark):
        col = L["wraps"] or L["skin"]
        dot(surf, P["h" + k], 5.5 * s, C(shade(col if L["wraps"] else L["skin"], 0.75 if dark else 1)))

    def leg(k, dark):
        m = 0.72 if dark else 1.0
        w = wide
        chain(surf, [(P["hip"], P["k" + k], 14 * s * w, 11 * s * w, C(shade(L["pants"], m))),
                     (P["k" + k], P["a" + k], 11 * s * w, 8 * s * w, C(shade(L["pants"], m)))])
        chain(surf, [(P["a" + k], P["t" + k], 9 * s, 6 * s, C(shade(L["shoes"], m)))])

    hip, sh = P["hip"], P["sh"]
    u = unit((P["head"][0] - sh[0], P["head"][1] - sh[1]))
    fw = (-u[1] * f.facing, u[0] * f.facing)

    # шарф (хвост за спиной)
    if L.get("scarf"):
        sc = C(L["scarf"])
        w1 = math.sin(f.time * 0.17) * 5 * s
        w2 = math.sin(f.time * 0.17 + 1.3) * 8 * s
        n0 = add(sh, u, 2 * s)
        p1 = add(add(n0, fw, -16 * s), u, w1 * 0.4 - 2 * s)
        p2 = add(add(p1, fw, -18 * s), u, w2 * 0.5 - 4 * s)
        chain(surf, [(n0, p1, 8 * s, 7 * s, sc), (p1, p2, 7 * s, 5 * s, shade(sc, 0.85) if not flash else sc)])

    arm("b", True)
    leg("b", True)
    hand("b", True)
    # шея, торс
    chain(surf, [(sh, add(P["head"], u, -9 * s), 8 * s, 8 * s, C(L["skin"]))])
    dot(surf, hip, 9 * s, C(L["pants"]))
    mid = (hip[0] * 0.45 + sh[0] * 0.55, hip[1] * 0.45 + sh[1] * 0.55)
    shirt = C(L["shirt"])
    chain(surf, [(hip, mid, 19 * s, 17 * s, shirt), (mid, sh, 17 * s, 23 * s, shirt)])
    b0 = (hip[0] * 0.92 + sh[0] * 0.08, hip[1] * 0.92 + sh[1] * 0.08)
    b1 = (hip[0] * 0.8 + sh[0] * 0.2, hip[1] * 0.8 + sh[1] * 0.2)
    chain(surf, [(b0, b1, 19 * s, 18 * s, C(L["belt"]))])
    if L.get("scarf"):
        dot(surf, add(sh, u, 3 * s), 7.5 * s, C(L["scarf"]))
    draw_head(surf, f, C)
    leg("f", False)
    arm("f", False)
    if f.weapon["id"] == "staff":
        hand("b", False)
    if f.weapon["id"] != "fists":
        draw_weapon(surf, f, C)
    hand("f", False)


def draw_trail(f):
    t = f.trail
    for i in range(1, len(t)):
        a = int(200 * i / len(t))
        w = int(2 + 7 * i / len(t))
        pygame.draw.line(fx_layer, (255, 255, 255, a), t[i - 1], t[i], w)


# ==================== БОЕЦ ====================

class Fighter:
    def __init__(self, x, char_idx, weapon_idx, facing, zoom=1.0, gy=GROUND):
        self.char = CHARACTERS[char_idx]
        self.look = self.char["look"]
        self.weapon = WEAPONS[weapon_idx]
        self.name = self.char["name"]
        self.scale = self.char["scale"] * zoom
        self.gy = gy
        self.x, self.facing = float(x), facing
        self.max_hp = self.char["hp"]
        self.hp = float(self.max_hp)
        self.shown_hp = float(self.max_hp)
        self.air = 0.0
        self.vx = self.vy = 0.0
        self.state = "normal"
        self.t = 0
        self.pose = dict(STAND)
        self.walk = 0.0
        self.time = random.randint(0, 100)
        self.move_dir = 0
        self.want_crouch = self.want_block = False
        self.atk = None
        self.ad = None
        self.atk_t = 0
        self.atk_count = 0
        self.hit_done = False
        self.buffer = None
        self.prev = dict(STAND)
        self.stun = 0
        self.blocked = False
        self.inv = 0
        self.flash = 0
        self.flip = 0
        self.flip_t = 0
        self.flip_len = 1
        self.jump_req = 0
        self.dead = False
        self.victory = False
        self.combo = 0          # сколько ударов подряд получил
        self.combo_show = 0     # счётчик комбо, который показываем (для атакующего)
        self.combo_t = 0
        self.trail = []
        self.nun = (0.0, 1.0)
        self.shake_req = 0
        self.pts = {}
        self.tip = (0, 0)
        self.refresh()

    # ----- вспомогательное -----
    @property
    def height(self):
        crouching = self.want_crouch and self.state in ("normal", "attack") and self.air == 0
        return (100 if crouching else 168) * self.scale

    @property
    def forward_held(self):
        return self.move_dir * self.facing > 0

    @property
    def back_held(self):
        return self.move_dir * self.facing < 0

    def active_attack(self):
        if self.atk and not self.hit_done:
            d = self.ad
            if d["s"] <= self.atk_t < d["s"] + d["a"]:
                return d
        return None

    # ----- ввод -----
    def jump_input(self):
        if self.state == "normal":
            self.jump_req = 3       # небольшой буфер, чтобы «W+A» можно было нажать не идеально синхронно

    def attack_input(self, key):
        st = self.state
        if st == "normal":
            if self.want_crouch:
                name = {"J": "upper", "K": "sweep", "L": "heavy"}[key]
            elif self.forward_held:
                name = {"J": "lunge", "K": "dkick", "L": "heavy"}[key]
            else:
                name = {"J": "jab", "K": "kick", "L": "heavy"}[key]
            self.jump_req = 0
            self.start_attack(name)
        elif st == "attack":
            if key in self.ad["chain"]:
                self.buffer = key
        elif st == "air" and self.atk is None:
            if self.flip > 0 and key in ("J", "K"):
                self.start_attack("flipj" if key == "J" else "flipk")
            else:
                self.start_attack({"J": "airj", "K": "airk", "L": "airl"}[key])

    def start_attack(self, name):
        d = dict(ATTACKS[name])
        w = self.weapon
        if d["kind"] == "punch" and w["id"] != "fists":
            d["s"] = max(2, round(d["s"] * w["spd"]))
            d["r"] = round(d["r"] * w["spd"])
            d["reach"] += w["reach"]
            d["dmg"] *= w["dmg"]
            if d.get("back"):
                d["ps"], d["pa"] = swap_arms(d["ps"]), swap_arms(d["pa"])
                d["limb"] = "f"
        d["dmg"] *= self.char["dmg"]
        d["reach"] *= self.scale
        self.ad, self.atk, self.atk_t = d, name, 0
        self.atk_count += 1
        self.hit_done = False
        self.buffer = None
        self.prev = dict(self.pose)
        if not d.get("air"):
            self.state = "attack"
            self.t = 0

    def start_jump(self, kind):
        self.state = "air"
        self.air = 0.1
        self.vy = self.char["jump"]
        self.flip, self.flip_t, self.atk, self.t = 0, 0, None, 0
        self.vx = 0.0
        if kind in ("back", "fwd"):
            self.vy += 0.8
            self.flip = -1 if kind == "back" else 1
            self.vx = self.facing * (-5.2 if kind == "back" else 5.6)
            if kind == "back":
                self.inv = 18       # уклонение: первые кадры кувырка назад неуязвимы
            spawn(self.x, self.gy, (190, 180, 170), 8, 3, 4)
        self.flip_len = int(2 * self.vy / GRAV) + 1

    def land(self):
        self.air, self.vy = 0.0, 0.0
        self.vx *= 0.3
        self.flip = 0
        self.atk = None
        self.pose["rot"] = 0
        self.state = "normal"
        self.t = 0
        spawn(self.x, self.gy, (190, 180, 170), 6, 3, 4)

    # ----- позы -----
    def target_pose(self):
        if self.victory:
            return WIN
        c, b = self.want_crouch, self.want_block
        if c and b:
            return CBLOCK
        if c:
            return CROUCH
        base = BLOCK if b else STAND
        p = dict(base)
        if self.move_dir:
            ph = self.walk
            p["fh"] = 18 + math.sin(ph) * 28
            p["bh"] = -16 - math.sin(ph) * 28
            p["fk"] = 14 + 35 * max(0.0, math.cos(ph))
            p["bk"] = 14 + 35 * max(0.0, -math.cos(ph))
            p["lean"] += 3
        else:
            p["lean"] += math.sin(self.time * 0.08) * 1.5
            p["fs"] += math.sin(self.time * 0.08) * 3
        return p

    def attack_pose(self):
        d, t = self.ad, self.atk_t
        s, a, r = d["s"], d["a"], d["r"]
        if t < s:
            u = t / s
            return mix(self.prev, d["ps"], u * 2) if u < 0.5 else mix(d["ps"], d["pa"], (u - 0.5) * 2)
        if t < s + a:
            return d["pa"]
        return mix(d["pa"], JUMP if d.get("air") else STAND, min(1.0, (t - s - a) / max(1, r)))

    # ----- состояния -----
    def update(self, opp):
        self.time += 1
        if self.flash > 0:
            self.flash -= 1
        if self.inv > 0:
            self.inv -= 1
        if self.combo_t > 0:
            self.combo_t -= 1
            if self.combo_t == 0:
                self.combo_show = 0
        if self.air == 0 and self.state not in ("air", "launch"):
            self.x += self.vx
            self.vx *= 0.8
        getattr(self, "_" + self.state)(opp)
        self.x = clamp(self.x, 50, WIDTH - 50)
        self.refresh()
        self.update_trail()

    def _normal(self, opp):
        self.facing = 1 if opp.x >= self.x else -1
        if self.jump_req > 0:
            back, fwd = self.back_held, self.forward_held
            self.jump_req -= 1
            if back or fwd or self.jump_req == 0:
                self.jump_req = 0
                self.start_jump("back" if back else "fwd" if fwd else "up")
                return
        if not self.want_crouch:
            spd = self.char["speed"] * (0.5 if self.want_block else 1.0)
            self.x += self.move_dir * spd
            if self.move_dir:
                self.walk += spd * 0.11
        self.pose = mix(self.pose, self.target_pose(), 0.35)

    def _attack(self, opp):
        self.atk_t += 1
        d = self.ad
        s, a, r = d["s"], d["a"], d["r"]
        if d.get("lunge") and self.atk_t < s + a:
            self.x += self.facing * d["lunge"]
        if self.buffer and self.atk_t >= s + a:
            nxt = d["chain"].get(self.buffer)
            self.buffer = None
            if nxt:
                self.start_attack(nxt)
                self.atk_t = 1
                d = self.ad
                s, a, r = d["s"], d["a"], d["r"]
        if self.atk_t >= s + a + r:
            self.atk = None
            self.state = "normal"
            self.pose = mix(self.pose, STAND, 0.5)
            return
        self.pose = dict(self.attack_pose())

    def _air(self, opp):
        if self.flip == 0:
            self.vx += (self.move_dir * self.char["speed"] * 0.8 - self.vx) * 0.08
        self.x += self.vx
        self.air += self.vy
        self.vy -= GRAV
        if self.flip:
            self.flip_t += 1
        if self.atk:
            self.atk_t += 1
            d = self.ad
            if d.get("dive") and self.atk_t < d["s"] + d["a"]:
                self.vy = min(self.vy, -d["dive"])
            if self.atk_t >= d["s"] + d["a"] + d["r"]:
                self.atk = None
        if self.atk:
            self.pose = dict(self.attack_pose())
        else:
            self.pose = mix(self.pose, TUCK if self.flip else JUMP, 0.3)
        if self.flip:
            prog = clamp(self.flip_t / max(1, self.flip_len - 4), 0, 1)
            self.pose["rot"] = 360 * self.flip * prog
        if self.air <= 0 and self.vy < 0:
            self.land()

    def _hurt(self, opp):
        self.t += 1
        self.pose = mix(self.pose, BLOCK if self.blocked else HURT, 0.4)
        if self.t >= self.stun:
            self.state = "normal"
            self.blocked = False
            self.combo = 0

    def _launch(self, opp):
        self.x += self.vx
        self.air += self.vy
        self.vy -= GRAV
        self.pose = mix(self.pose, LAUNCH, 0.3)
        if self.air <= 0 and self.vy < 0:
            self.air, self.vy, self.vx = 0.0, 0.0, 0.0
            self.state, self.t = "down", 0
            self.shake_req = 8
            spawn(self.x, self.gy, (190, 180, 170), 12, 4, 5)

    def _down(self, opp):
        self.t += 1
        self.pose = mix(self.pose, DOWN, 0.35)
        if not self.dead and self.t >= 42:
            self.state, self.t = "getup", 0

    _dead = _down

    def _getup(self, opp):
        self.t += 1
        self.pose = mix(DOWN, STAND, clamp(self.t / 22, 0, 1))
        if self.t >= 22:
            self.state, self.combo, self.inv = "normal", 0, 12

    # ----- визуальная часть -----
    def refresh(self):
        self.pts = skeleton(self)

    def weapon_shapes(self):
        """Геометрия оружия в руке; возвращает (список фигур, кончик)."""
        P, s, wid = self.pts, self.scale, self.weapon["id"]
        hf = P["hf"]
        d = unit((hf[0] - P["ef"][0], hf[1] - P["ef"][1]))
        n = (-d[1] * self.facing, d[0] * self.facing)
        steel, wood = (205, 210, 225), (110, 70, 40)
        shapes, tip = [], hf
        if wid == "sword":
            g = add(hf, d, 5 * s)
            tip = add(hf, d, 60 * s)
            shapes.append(("line", add(hf, d, -9 * s), g, 5 * s, (60, 40, 30)))
            shapes.append(("line", add(g, n, 7 * s), add(g, n, -7 * s), 4 * s, (210, 175, 70)))
            shapes.append(("poly", [add(g, n, 3.5 * s), add(add(tip, d, -8 * s), n, 2 * s), tip,
                                    add(g, n, -3.5 * s)], steel))
        elif wid == "staff":
            hb = P["hb"]
            dd = unit((hf[0] - hb[0], hf[1] - hb[1])) if math.hypot(hf[0] - hb[0], hf[1] - hb[1]) > 12 else d
            mid = ((hf[0] + hb[0]) / 2, (hf[1] + hb[1]) / 2)
            tip = add(mid, dd, 68 * s)
            back = add(mid, dd, -68 * s)
            shapes.append(("line", back, tip, 5 * s, wood))
            shapes.append(("line", add(tip, dd, -9 * s), tip, 6 * s, (170, 170, 185)))
            shapes.append(("line", add(back, dd, 9 * s), back, 6 * s, (170, 170, 185)))
        elif wid == "nunchaku":
            e1 = add(hf, d, 26 * s)
            c1 = add(e1, self.nun, 8 * s)
            tip = add(c1, self.nun, 26 * s)
            shapes.append(("line", add(hf, d, -5 * s), e1, 5 * s, wood))
            shapes.append(("line", e1, c1, 2 * s, (160, 160, 170)))
            shapes.append(("line", c1, tip, 5 * s, wood))
        elif wid == "dagger":
            g = add(hf, d, 4 * s)
            tip = add(hf, d, 28 * s)
            shapes.append(("line", add(hf, d, -6 * s), g, 5 * s, (60, 40, 30)))
            shapes.append(("line", add(g, n, 5 * s), add(g, n, -5 * s), 3 * s, (210, 175, 70)))
            shapes.append(("poly", [add(g, n, 2.6 * s), tip, add(g, n, -2.6 * s)], steel))
        elif wid == "axe":
            tip = add(hf, d, 46 * s)
            shapes.append(("line", add(hf, d, -8 * s), tip, 5 * s, wood))
            shapes.append(("poly", [add(add(hf, d, 30 * s), n, 3 * s), add(add(hf, d, 26 * s), n, 20 * s),
                                    add(add(hf, d, 48 * s), n, 22 * s), add(add(hf, d, 46 * s), n, 3 * s)],
                           (170, 175, 190)))
        # инерция второй палки нунчак
        tgt = unit((d[0], d[1] + 0.9))
        self.nun = unit((self.nun[0] * 0.7 + tgt[0] * 0.3, self.nun[1] * 0.7 + tgt[1] * 0.3))
        self.tip = tip
        return shapes, tip

    def update_trail(self):
        d = self.ad if self.atk else None
        if d and d["s"] <= self.atk_t < d["s"] + d["a"] + 3:
            limb = d["limb"]
            if limb in ("f", "b"):
                if self.weapon["id"] != "fists":
                    self.weapon_shapes()
                    pt = self.tip
                else:
                    pt = self.pts["h" + limb]
            else:
                pt = self.pts["t" + limb[1]]
            self.trail.append((int(pt[0]), int(pt[1])))
            if len(self.trail) > 8:
                self.trail.pop(0)
        elif self.trail:
            self.trail.pop(0)

    def idle_preview(self):
        self.time += 1
        self.pose = mix(self.pose, self.target_pose(), 0.3)
        self.refresh()


# ==================== БОЕВАЯ ЛОГИКА ====================

def find_hit(a, b):
    """Проверяет, попадает ли текущая атака a по бойцу b. Возвращает (данные, точка, блок) или None."""
    d = a.active_attack()
    if not d or b.inv > 0 or b.state in ("launch", "down", "getup", "dead"):
        return None
    f = a.facing
    x0, x1 = a.x + f * 8, a.x + f * d["reach"]
    lo, hi = min(x0, x1), max(x0, x1)
    ylo, yhi = a.air + d["y"][0], a.air + d["y"][1]
    bx0, bx1 = b.x - 20 * b.scale, b.x + 20 * b.scale
    by0, by1 = b.air, b.air + b.height
    if not (lo < bx1 and hi > bx0 and ylo < by1 and yhi > by0):
        return None
    pt = (b.x - f * 12, a.gy - (max(ylo, by0) + min(yhi, by1)) / 2)
    can_block = ((b.state == "normal" or (b.state == "hurt" and b.blocked)) and b.want_block
                 and b.air == 0 and b.facing == -f)
    blocked = can_block and (not d.get("low") or b.want_crouch)
    return d, pt, blocked


def apply_hit(a, b, d, pt, blocked):
    """Применяет попадание. Возвращает (хитстоп, тряска)."""
    a.hit_done = True
    f = a.facing
    push = d["push"]
    if blocked:
        b.hp = max(1.0, b.hp - d["dmg"] * 0.08)
        b.state, b.t, b.stun, b.blocked = "hurt", 0, 10, True
        b.vx = f * push * 0.14
        a.vx = -f * push * 0.08
        b.atk, b.buffer = None, None
        spawn(pt[0], pt[1], (150, 200, 255), 8, 5, 3)
        rings.append([pt[0], pt[1], 6, 6, 200])
        return 3, 2
    # комбо: урон падает с каждым ударом
    b.combo = b.combo + 1 if b.state == "hurt" and not b.blocked else 1
    a.combo_show, a.combo_t = b.combo, 100
    dmg = d["dmg"] * max(0.45, 1 - 0.1 * (b.combo - 1))
    b.hp -= dmg
    b.flash = 4
    b.atk, b.buffer, b.flip, b.jump_req = None, None, 0, 0
    b.pose["rot"] = 0
    head = pt[1] < a.gy - 130 * b.scale
    heavy = d.get("kd") or d["dmg"] >= 9
    if b.hp <= 0:
        b.hp, b.dead = 0.0, True
    if d.get("kd") or b.dead or b.air > 0:
        b.state, b.blocked = "launch", False
        b.vy = d.get("launch", 7 if d.get("kd") or b.dead else 4)
        b.vx = f * (3 + push * 0.05)
        if b.air == 0:
            b.air = 0.1
    else:
        b.state, b.t, b.blocked = "hurt", 0, False
        b.stun = max(9, d.get("stun", 16) - b.combo)
        b.vx = f * push * 0.2
    spawn(pt[0], pt[1], (255, 110, 70) if heavy else (255, 205, 100), 16 if heavy else 9, 7 if heavy else 5, 4)
    rings.append([pt[0], pt[1], 8, 8, 255])
    return d["hs"] + (3 if head else 0) + (10 if b.dead else 0), (8 if heavy else 4)


# ==================== ИИ ====================

COMBOS = [
    [("J", ""), ("J", ""), ("J", "")],
    [("K", ""), ("K", ""), ("K", "")],
    [("J", ""), ("K", ""), ("L", "")],
    [("J", ""), ("J", ""), ("K", "")],
    [("J", "S")],
    [("K", "S")],
    [("L", "")],
    [("J", "F"), ("J", "")],
    [("K", "F"), ("K", "")],
]


class AI:
    def __init__(self, level=0.6):
        self.level = level
        self.cd = 30
        self.queue = []
        self.qt = 0
        self.block_t = 0
        self.retreat = 0
        self.seen = 0

    def update(self, me, opp):
        me.move_dir = 0
        me.want_crouch = False
        me.want_block = self.block_t > 0
        if self.block_t > 0:
            self.block_t -= 1
        if self.cd > 0:
            self.cd -= 1
        if me.state in ("hurt", "launch", "down", "getup", "dead"):
            self.queue = []
            return
        dist = abs(opp.x - me.x)
        toward = 1 if opp.x > me.x else -1

        # реакция на атаку соперника (решение принимается один раз — в начале удара)
        if opp.atk and opp.atk_count != self.seen:
            self.seen = opp.atk_count
            r = random.random() if (dist < 190 and me.state == "normal") else 1.0
            if r < self.level * 0.55:
                self.block_t = 24
                if opp.ad.get("low") or opp.atk == "sweep":
                    me.want_crouch = True
                self.queue = []
            elif r < self.level * 0.75:
                me.move_dir = -toward
                me.jump_input()
                self.queue = []
        if self.block_t > 0:
            me.want_crouch = me.want_crouch or opp.atk == "sweep"
            return

        if me.state == "air":
            if me.atk is None and dist < 110 and random.random() < 0.12:
                me.attack_input(random.choice("JK"))
            me.move_dir = toward if dist > 70 else 0
            return

        if self.queue:
            self.qt -= 1
            if self.qt <= 0:
                key, mod = self.queue.pop(0)
                me.want_crouch = mod == "S"
                if mod == "F":
                    me.move_dir = toward
                me.attack_input(key)
                self.qt = random.randint(9, 14)
            return

        if self.retreat > 0:
            self.retreat -= 1
            me.move_dir = -toward
            return

        if dist > 190:
            me.move_dir = toward
            if self.cd == 0 and random.random() < 0.01:
                me.move_dir = toward
                me.jump_input()          # сальто вперёд
                self.cd = 60
        elif dist > 105:
            me.move_dir = toward
            if self.cd == 0 and random.random() < 0.05:
                self.queue = [random.choice([("J", "F"), ("K", "F")])]
                self.qt = 0
                self.cd = 50
        else:
            if self.cd == 0 and random.random() < 0.06 + 0.06 * self.level:
                self.queue = list(random.choice(COMBOS))
                self.qt = 0
                self.cd = int(80 - 45 * self.level)
                if random.random() < 0.4:
                    self.retreat = random.randint(15, 40)
            elif random.random() < 0.01:
                me.jump_input()


# ==================== ФОН ====================

def build_background():
    bg = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = clamp(y / GROUND, 0, 1) ** 1.6
        pygame.draw.line(bg, mixc((12, 14, 36), (128, 72, 100), t), (0, y), (WIDTH, y))
    rnd = random.Random(7)
    for _ in range(110):
        pygame.draw.circle(bg, (230, 230, 255), (rnd.randint(0, WIDTH), rnd.randint(0, 330)), rnd.choice((1, 1, 2)))
    glow = pygame.Surface((300, 300), pygame.SRCALPHA)
    for r in range(150, 70, -10):
        pygame.draw.circle(glow, (255, 235, 200, 6), (150, 150), r)
    bg.blit(glow, (780, 0))
    pygame.draw.circle(bg, (250, 240, 212), (930, 150), 70)
    for cx, cy, cr in ((910, 130, 12), (955, 170, 9), (925, 180, 6)):
        pygame.draw.circle(bg, (232, 220, 190), (cx, cy), cr)
    for layer, (col, base, amp) in enumerate((((40, 30, 64), 430, 90), ((26, 20, 44), 500, 60))):
        pts = [(0, HEIGHT)]
        for x in range(0, WIDTH + 40, 40):
            pts.append((x, base - amp * (0.5 + 0.5 * math.sin(x * 0.006 + layer * 2) * math.cos(x * 0.0023 + layer))))
        pts.append((WIDTH, HEIGHT))
        pygame.draw.polygon(bg, col, pts)
    # пагода
    px, base = 230, GROUND - 10
    for i in range(4):
        w = 230 - 42 * i
        y0 = base - i * 74
        pygame.draw.rect(bg, (22, 16, 36), (px - w // 2 + 20, y0 - 44, w - 40, 44))
        pygame.draw.polygon(bg, (16, 12, 28), [(px - w // 2 - 16, y0 - 40), (px + w // 2 + 16, y0 - 40),
                                               (px + w // 2 - 14, y0 - 62), (px - w // 2 + 14, y0 - 62)])
        pygame.draw.polygon(bg, (16, 12, 28), [(px - w // 2 - 28, y0 - 34), (px - w // 2 - 16, y0 - 40),
                                               (px - w // 2 + 14, y0 - 62), (px - w // 2 - 6, y0 - 38)])
        pygame.draw.polygon(bg, (16, 12, 28), [(px + w // 2 + 28, y0 - 34), (px + w // 2 + 16, y0 - 40),
                                               (px + w // 2 - 14, y0 - 62), (px + w // 2 + 6, y0 - 38)])
    # тории
    tx = 1060
    pygame.draw.rect(bg, (96, 24, 36), (tx - 90, GROUND - 230, 18, 230))
    pygame.draw.rect(bg, (96, 24, 36), (tx + 72, GROUND - 230, 18, 230))
    pygame.draw.rect(bg, (96, 24, 36), (tx - 118, GROUND - 240, 236, 20))
    pygame.draw.rect(bg, (96, 24, 36), (tx - 100, GROUND - 195, 200, 12))
    # пол
    floor_top = GROUND - 14
    for y in range(floor_top, HEIGHT):
        t = (y - floor_top) / (HEIGHT - floor_top)
        pygame.draw.line(bg, mixc((92, 58, 46), (46, 28, 28), t), (0, y), (WIDTH, y))
    pygame.draw.line(bg, (150, 100, 78), (0, floor_top), (WIDTH, floor_top), 3)
    for i in range(-12, 34):
        x0 = i * 80
        pygame.draw.line(bg, (40, 24, 24), (x0, floor_top), (WIDTH / 2 + (x0 - WIDTH / 2) * 1.9, HEIGHT), 2)
    return bg


# ==================== ВВОД ====================

P_KEYS = [
    dict(left=pygame.K_a, right=pygame.K_d, up=pygame.K_w, down=pygame.K_s,
         block=(pygame.K_LSHIFT,), atk={pygame.K_j: "J", pygame.K_k: "K", pygame.K_l: "L"}),
    dict(left=pygame.K_LEFT, right=pygame.K_RIGHT, up=pygame.K_UP, down=pygame.K_DOWN,
         block=(pygame.K_RSHIFT, pygame.K_RCTRL, pygame.K_KP0),
         atk={pygame.K_COMMA: "J", pygame.K_PERIOD: "K", pygame.K_SLASH: "L",
              pygame.K_KP1: "J", pygame.K_KP2: "K", pygame.K_KP3: "L"}),
]


def read_input(fighter, keysets):
    keys = pygame.key.get_pressed()
    d = 0
    crouch = block = False
    for k in keysets:
        d += (1 if keys[k["right"]] else 0) - (1 if keys[k["left"]] else 0)
        crouch = crouch or bool(keys[k["down"]])
        block = block or any(keys[b] for b in k["block"])
    fighter.move_dir = clamp(d, -1, 1)
    fighter.want_crouch = crouch
    fighter.want_block = block


# ==================== МАТЧ ====================

class Match:
    def __init__(self, mode, sel):
        self.mode = mode
        self.sel = sel
        self.wins = [0, 0]
        self.round = 1
        self.over = False
        self.winner_text = ""
        self.start_round()

    def start_round(self):
        s = self.sel
        self.p1 = Fighter(380, s[0]["char"], s[0]["weapon"], 1)
        self.p2 = Fighter(900, s[1]["char"], s[1]["weapon"], -1)
        self.ai = AI(0.62) if self.mode == "1p" else None
        particles.clear()
        rings.clear()
        self.timer = ROUND_TIME * FPS
        self.hitstop = 0
        self.shake = 0.0
        self.intro = 100
        self.ko_t = 0
        self.round_over = False
        self.result = None      # 0/1 — победитель раунда, -1 — ничья

    @property
    def frozen(self):
        return self.intro > 0 or self.round_over or self.over

    def step(self):
        p1, p2 = self.p1, self.p2
        if self.intro > 0:
            self.intro -= 1
        if self.hitstop > 0:
            self.hitstop -= 1
        else:
            if self.ai and not self.frozen:
                self.ai.update(p2, p1)
            p1.update(p2)
            p2.update(p1)

            # бойцы не проходят друг сквозь друга (кроме прыжка над противником)
            if (p1.state in ("normal", "hurt", "attack") and p2.state in ("normal", "hurt", "attack")
                    and p1.air < 50 and p2.air < 50):
                dx = p2.x - p1.x
                if abs(dx) < 46:
                    push = (46 - abs(dx)) / 2
                    sg = 1 if dx >= 0 else -1
                    p1.x -= push * sg
                    p2.x += push * sg
            p1.x = clamp(p1.x, 50, WIDTH - 50)
            p2.x = clamp(p2.x, 50, WIDTH - 50)

            # оба удара определяются до применения — исключаем преимущество игрока 1
            h1, h2 = find_hit(p1, p2), find_hit(p2, p1)
            for a, b, h in ((p1, p2, h1), (p2, p1, h2)):
                if h:
                    hs, sk = apply_hit(a, b, *h)
                    self.hitstop = max(self.hitstop, hs)
                    self.shake = max(self.shake, sk)
            for f in (p1, p2):
                self.shake = max(self.shake, f.shake_req)
                f.shake_req = 0

            if not self.round_over:
                if not self.frozen:
                    self.timer -= 1
                if p1.dead or p2.dead:
                    self.end_round(None if (p1.dead and p2.dead) else (1 if p1.dead else 0))
                elif self.timer <= 0:
                    self.end_round(-1 if abs(p1.hp - p2.hp) < 0.5 else (0 if p1.hp > p2.hp else 1))
        for f in (p1, p2):
            f.shown_hp += (f.hp - f.shown_hp) * 0.08
        if self.round_over:
            self.ko_t += 1
            if self.ko_t == 60 and self.result in (0, 1):
                (p1 if self.result == 0 else p2).victory = True
            if self.ko_t == 150 and not self.over:
                if self.result in (0, 1):
                    self.wins[self.result] += 1
                if max(self.wins) >= ROUNDS_TO_WIN:
                    self.over = True
                    w = self.wins.index(max(self.wins))
                    names = ("PLAYER 1", "PLAYER 2") if self.mode == "2p" else ("PLAYER", "CPU")
                    self.winner_text = names[w] + " WINS"
                else:
                    self.round += 1
                    self.start_round()

    def end_round(self, result):
        self.round_over = True
        self.result = -1 if result is None else result
        self.ko_t = 0
        for f in (self.p1, self.p2):
            f.move_dir = 0
            f.want_crouch = f.want_block = False

    # ----- отрисовка -----
    def draw(self, surf, background):
        surf.blit(background, (0, 0))
        fx_layer.fill((0, 0, 0, 0))
        for f in sorted((self.p1, self.p2), key=lambda q: 1 if q.atk else 0):
            draw_fighter(surf, f)
            draw_trail(f)
        draw_effects(surf)
        surf.blit(fx_layer, (0, 0))
        self.draw_hud(surf)

    def draw_hud(self, surf):
        names = ("P1", "P2") if self.mode == "2p" else ("PLAYER", "CPU")
        draw_health_bar(surf, self.p1, 40, 40, GREEN, names[0], False, self.wins[0])
        draw_health_bar(surf, self.p2, WIDTH - 460, 40, RED, names[1], True, self.wins[1])
        secs = max(0, math.ceil(self.timer / FPS))
        text(surf, MID_FONT, str(secs), WHITE if secs > 10 else RED, (WIDTH // 2, 58))
        text(surf, SMALL_FONT, "ROUND %d" % self.round, (200, 200, 220), (WIDTH // 2, 92))
        for f, x in ((self.p1, 120), (self.p2, WIDTH - 120)):
            if f.combo_show >= 2:
                text(surf, MID_FONT, "%d HITS!" % f.combo_show, GOLD, (x, 190))
        hint1 = ("P1: A/D move  W jump  S crouch  LShift block  J punch  K kick  L heavy"
                 if self.mode == "2p" else
                 "A/D move  W jump  S crouch  Shift block  J punch  K kick  L heavy")
        text(surf, SMALL_FONT, hint1, (185, 190, 205), (WIDTH // 2, HEIGHT - 52))
        if self.mode == "2p":
            text(surf, SMALL_FONT, "P2: Arrows move/jump/crouch  RShift block  , punch  . kick  / heavy",
                 (185, 190, 205), (WIDTH // 2, HEIGHT - 32))
        text(surf, SMALL_FONT,
             "Combos: JJJ | KKK | JKL | S+J Uppercut | S+K Sweep | >+J Lunge | >+K Dash kick | W+back Backflip | W+fwd Flip (+J/K)",
             (150, 156, 175), (WIDTH // 2, HEIGHT - 12))
        # баннеры
        if self.intro > 0:
            if self.intro > 40:
                text(surf, BIG_FONT, "ROUND %d" % self.round, WHITE, (WIDTH // 2, 260))
            else:
                text(surf, BIG_FONT, "FIGHT!", GOLD, (WIDTH // 2, 260))
        elif self.round_over and not self.over:
            msg = "K.O." if (self.p1.dead or self.p2.dead) else ("TIME UP" if self.result != -1 else "DRAW")
            text(surf, BIG_FONT, msg, (255, 230, 120), (WIDTH // 2, 230))
        if self.over:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 175))
            surf.blit(ov, (0, 0))
            text(surf, BIG_FONT, self.winner_text, WHITE, (WIDTH // 2, HEIGHT // 2 - 30))
            text(surf, FONT, "R - rematch   |   ENTER - main menu   |   ESC - exit", WHITE,
                 (WIDTH // 2, HEIGHT // 2 + 50))


def draw_health_bar(surf, f, x, y, color, label, reverse, wins):
    w, h = 420, 26
    pygame.draw.rect(surf, (10, 10, 18), (x - 3, y - 3, w + 6, h + 6), border_radius=6)
    frac = clamp(f.hp / f.max_hp, 0, 1)
    trail = clamp(f.shown_hp / f.max_hp, 0, 1)
    def bar(fr, col):
        bw = int(w * fr)
        rect = (x + (w - bw if reverse else 0), y, bw, h)
        pygame.draw.rect(surf, col, rect, border_radius=4)
    bar(trail, (240, 220, 140))
    bar(frac, color if frac > 0.3 else (255, 150, 60))
    pygame.draw.rect(surf, (200, 200, 220), (x - 3, y - 3, w + 6, h + 6), 2, border_radius=6)
    anchor = "topright" if reverse else "topleft"
    text(surf, SMALL_FONT, "%s - %s  (%s)" % (label, f.name, f.weapon["name"]), WHITE,
         (x + w if reverse else x, y + h + 8), anchor)
    for i in range(ROUNDS_TO_WIN):
        cx = x + w - 10 - i * 22 if reverse else x + 10 + i * 22
        pygame.draw.circle(surf, GOLD if i < wins else (60, 60, 80), (cx, y + h + 38), 7)
        pygame.draw.circle(surf, WHITE, (cx, y + h + 38), 7, 1)


# ==================== ИГРА (меню, выбор, бой) ====================

MENU_ITEMS = ["1 PLAYER  (vs CPU)", "2 PLAYERS  (vs friend)", "MOVES & CONTROLS", "QUIT"]

CONTROLS_TEXT = [
    ("PLAYER 1", "A/D move   W jump   S crouch   LShift block   J punch   K kick   L heavy kick"),
    ("PLAYER 2", "Arrows move/jump/crouch   RShift block   ,  punch   .  kick   /  heavy kick"),
    ("(1P mode)", "Player can use both key sets"),
    ("", ""),
    ("CHAINS", "J J J  (jab, cross, finisher)      K K K  (kick, roundhouse, spin kick)"),
    ("", "J K L, J J K, K J J ... any attack can chain into another while the hit window is open"),
    ("GROUND", "S + J  Uppercut (launcher)      S + K  Sweep (low, must crouch-block)"),
    ("", "Forward + J  Lunge strike      Forward + K  Dash kick      L  Heavy roundhouse"),
    ("AIR", "W  Jump (steer in the air)       J / K  Air punch / kick       L  Dive smash"),
    ("FLIPS", "W + Back  Backflip (dodge, brief invulnerability)"),
    ("", "W + Forward  Forward flip      J or K during the flip  Flip strike (knockdown)"),
    ("", "Hold Block to defend (crouch-block vs low attacks). Crouching dodges high attacks."),
    ("WEAPONS", "Weapons replace punches (J, S+J, >+J, air J, L-air). Kicks stay as kicks."),
    ("", "Each weapon changes damage, reach and attack speed."),
    ("OTHER", "P pause     ESC back to menu     First to 2 rounds wins"),
]


class Game:
    def __init__(self):
        self.background = build_background()
        self.scene = "menu"
        self.menu_i = 0
        self.mode = "1p"
        self.sel = [dict(char=0, weapon=0, ready=False), dict(char=1, weapon=0, ready=False)]
        self.previews = [None, None]
        self.start_t = 0
        self.match = None
        self.paused = False
        self.running = True
        self.menu_fighters = (Fighter(330, 0, 1, 1), Fighter(950, 1, 2, -1))

    # ---------- общий цикл ----------
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.KEYDOWN:
            getattr(self, "key_" + self.scene)(ev.key)

    def update(self):
        getattr(self, "update_" + self.scene)()

    def draw(self):
        getattr(self, "draw_" + self.scene)()

    # ---------- главное меню ----------
    def key_menu(self, key):
        if key in (pygame.K_UP, pygame.K_w):
            self.menu_i = (self.menu_i - 1) % len(MENU_ITEMS)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.menu_i = (self.menu_i + 1) % len(MENU_ITEMS)
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_j):
            if self.menu_i in (0, 1):
                self.mode = "1p" if self.menu_i == 0 else "2p"
                self.open_select()
            elif self.menu_i == 2:
                self.scene = "controls"
            else:
                self.running = False
        elif key == pygame.K_ESCAPE:
            self.running = False

    def update_menu(self):
        for f in self.menu_fighters:
            f.idle_preview()

    def draw_menu(self):
        canvas.blit(self.background, (0, 0))
        for f in self.menu_fighters:
            draw_fighter(canvas, f)
        t = pygame.time.get_ticks() / 1000
        text(canvas, BIG_FONT, "SHADOW FIGHTER", (255, 232, 160), (WIDTH // 2, 140 + int(math.sin(t * 2) * 4)))
        for i, item in enumerate(MENU_ITEMS):
            sel = i == self.menu_i
            col = GOLD if sel else (200, 200, 215)
            text(canvas, MID_FONT, ("> " + item + " <") if sel else item, col, (WIDTH // 2, 300 + i * 70))
        text(canvas, SMALL_FONT, "W/S or Up/Down - choose     ENTER / J - confirm", (170, 175, 195),
             (WIDTH // 2, HEIGHT - 40))

    # ---------- справка по управлению ----------
    def key_controls(self, key):
        if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE, pygame.K_BACKSPACE):
            self.scene = "menu"

    def update_controls(self):
        pass

    def draw_controls(self):
        canvas.blit(self.background, (0, 0))
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 10, 200))
        canvas.blit(ov, (0, 0))
        text(canvas, MID_FONT, "MOVES & CONTROLS", GOLD, (WIDTH // 2, 60))
        y = 120
        for head, line in CONTROLS_TEXT:
            if head:
                text(canvas, SMALL_FONT, head, GOLD, (60, y), "midleft")
            text(canvas, SMALL_FONT, line, (225, 228, 240), (190, y), "midleft")
            y += 34
        text(canvas, SMALL_FONT, "ESC / ENTER - back", (170, 175, 195), (WIDTH // 2, HEIGHT - 30))

    # ---------- выбор бойца и оружия ----------
    def open_select(self):
        self.scene = "select"
        self.sel[0].update(ready=False)
        self.sel[1].update(ready=(self.mode == "1p"))
        if self.mode == "1p":
            self.sel[1]["char"] = random.randrange(len(CHARACTERS))
            self.sel[1]["weapon"] = random.randrange(len(WEAPONS))
        self.start_t = 0
        self.previews = [None, None]

    def key_select(self, key):
        if key == pygame.K_ESCAPE:
            self.scene = "menu"
            return
        n_c, n_w = len(CHARACTERS), len(WEAPONS)
        s1, s2 = self.sel
        p1_confirm = (pygame.K_j, pygame.K_SPACE) + ((pygame.K_RETURN,) if self.mode == "1p" else ())
        if not s1["ready"]:
            if key == pygame.K_a:
                s1["char"] = (s1["char"] - 1) % n_c
            elif key == pygame.K_d:
                s1["char"] = (s1["char"] + 1) % n_c
            elif key == pygame.K_w:
                s1["weapon"] = (s1["weapon"] - 1) % n_w
            elif key == pygame.K_s:
                s1["weapon"] = (s1["weapon"] + 1) % n_w
            elif key in p1_confirm:
                s1["ready"] = True
        elif key in (pygame.K_k, pygame.K_BACKSPACE):
            s1["ready"] = False
        if self.mode == "2p":
            if not s2["ready"]:
                if key == pygame.K_LEFT:
                    s2["char"] = (s2["char"] - 1) % n_c
                elif key == pygame.K_RIGHT:
                    s2["char"] = (s2["char"] + 1) % n_c
                elif key == pygame.K_UP:
                    s2["weapon"] = (s2["weapon"] - 1) % n_w
                elif key == pygame.K_DOWN:
                    s2["weapon"] = (s2["weapon"] + 1) % n_w
                elif key in (pygame.K_COMMA, pygame.K_RETURN, pygame.K_KP1):
                    s2["ready"] = True
            elif key in (pygame.K_PERIOD, pygame.K_KP2):
                s2["ready"] = False
        else:   # в режиме 1P стрелками можно выбрать и противника
            if key == pygame.K_LEFT:
                s2["char"] = (s2["char"] - 1) % n_c
            elif key == pygame.K_RIGHT:
                s2["char"] = (s2["char"] + 1) % n_c
            elif key == pygame.K_UP:
                s2["weapon"] = (s2["weapon"] - 1) % n_w
            elif key == pygame.K_DOWN:
                s2["weapon"] = (s2["weapon"] + 1) % n_w

    def update_select(self):
        for i in (0, 1):
            s = self.sel[i]
            key = (s["char"], s["weapon"])
            if self.previews[i] is None or self.previews[i][0] != key:
                x = 40 + (WIDTH // 2 - 60) // 2 if i == 0 else WIDTH // 2 + 20 + (WIDTH // 2 - 60) // 2
                self.previews[i] = (key, Fighter(x, s["char"], s["weapon"], 1 if i == 0 else -1, 1.3, 400))
            f = self.previews[i][1]
            f.victory = s["ready"] and (self.mode == "2p" or i == 0)
            f.idle_preview()
        if all(s["ready"] for s in self.sel):
            self.start_t += 1
            if self.start_t > 40:
                self.start_match()
        else:
            self.start_t = 0

    def start_match(self):
        self.match = Match(self.mode, [dict(s) for s in self.sel])
        self.paused = False
        self.scene = "fight"

    def draw_select(self):
        canvas.blit(self.background, (0, 0))
        text(canvas, MID_FONT, "CHOOSE YOUR FIGHTER", GOLD, (WIDTH // 2, 44))
        for i in (0, 1):
            x = 40 if i == 0 else WIDTH // 2 + 20
            w = WIDTH // 2 - 60
            rect = pygame.Rect(x, 90, w, 560)
            pan = pygame.Surface(rect.size, pygame.SRCALPHA)
            pan.fill((10, 12, 26, 200))
            canvas.blit(pan, rect)
            s = self.sel[i]
            border = GOLD if s["ready"] else (GREEN if i == 0 else RED)
            pygame.draw.rect(canvas, border, rect, 3, border_radius=8)
            title = ("PLAYER 1" if i == 0 else "PLAYER 2") if self.mode == "2p" else ("PLAYER" if i == 0 else "CPU")
            text(canvas, FONT, title, border, (rect.centerx, rect.y + 28))
            if self.previews[i]:
                draw_fighter(canvas, self.previews[i][1])
            ch, wp = CHARACTERS[s["char"]], WEAPONS[s["weapon"]]
            text(canvas, MID_FONT, "< %s >" % ch["name"], WHITE, (rect.centerx, rect.y + 340))
            text(canvas, SMALL_FONT, ch["desc"], (190, 195, 215), (rect.centerx, rect.y + 372))
            for j, (lab, val, mx) in enumerate((("HP", ch["hp"], 130), ("SPEED", ch["speed"], 5.8),
                                                ("POWER", ch["dmg"], 1.2))):
                by = rect.y + 400 + j * 24
                text(canvas, SMALL_FONT, lab, (200, 200, 215), (rect.x + 40, by), "midleft", False)
                pygame.draw.rect(canvas, (40, 44, 64), (rect.x + 130, by - 8, 240, 16), border_radius=4)
                pygame.draw.rect(canvas, border, (rect.x + 130, by - 8, int(240 * clamp(val / mx, 0, 1)), 16),
                                 border_radius=4)
            text(canvas, FONT, "WEAPON:  < %s >" % wp["name"], GOLD, (rect.centerx, rect.y + 490))
            text(canvas, SMALL_FONT, "%s   dmg x%.2f  reach +%d  speed %s" % (
                wp["desc"], wp["dmg"], wp["reach"], "fast" if wp["spd"] < 1 else "slow" if wp["spd"] > 1.1 else "normal"),
                 (190, 195, 215), (rect.centerx, rect.y + 520))
            if s["ready"]:
                text(canvas, FONT, "READY!", GOLD, (rect.centerx, rect.bottom - 18))
        l1 = "P1: A/D fighter   W/S weapon   J / Space confirm   K cancel"
        l2 = ("P2: Left/Right fighter   Up/Down weapon   , / Enter confirm   . cancel"
              if self.mode == "2p" else "Arrows: change CPU opponent   ENTER / J: ready")
        text(canvas, SMALL_FONT, l1, (180, 185, 205), (WIDTH // 2 - 280, HEIGHT - 36))
        text(canvas, SMALL_FONT, l2, (180, 185, 205), (WIDTH // 2 + 300, HEIGHT - 36))
        if all(s["ready"] for s in self.sel):
            text(canvas, MID_FONT, "FIGHT!", WHITE, (WIDTH // 2, 340))

    # ---------- бой ----------
    def key_fight(self, key):
        m = self.match
        if key == pygame.K_ESCAPE:
            if m.over:
                self.running = False
            else:
                self.scene = "menu"
            return
        if m.over:
            if key == pygame.K_r:
                self.match = Match(m.mode, m.sel)
            elif key in (pygame.K_RETURN, pygame.K_m):
                self.scene = "menu"
            return
        if key == pygame.K_p:
            self.paused = not self.paused
            return
        if self.paused or m.frozen:
            return
        humans = self.humans()
        for fighter, keysets in humans:
            for k in keysets:
                if key == k["up"]:
                    fighter.jump_input()
                elif key in k["atk"]:
                    fighter.attack_input(k["atk"][key])

    def humans(self):
        m = self.match
        if m.mode == "1p":
            return [(m.p1, P_KEYS)]
        return [(m.p1, [P_KEYS[0]]), (m.p2, [P_KEYS[1]])]

    def update_fight(self):
        m = self.match
        if self.paused:
            return
        if not m.frozen:
            for fighter, keysets in self.humans():
                read_input(fighter, keysets)
        else:
            for f in (m.p1, m.p2):
                f.move_dir = 0
                f.want_crouch = f.want_block = False
        m.step()
        update_effects()

    def draw_fight(self):
        m = self.match
        m.draw(canvas, self.background)
        if self.paused:
            text(canvas, BIG_FONT, "PAUSED", WHITE, (WIDTH // 2, HEIGHT // 2))


# ==================== ГЛАВНЫЙ ЦИКЛ ====================

def main(max_frames=None):
    game = Game()
    frames = 0
    shake = 0.0
    while game.running:
        clock.tick(FPS)
        frames += 1
        if max_frames and frames > max_frames:
            break
        for event in pygame.event.get():
            game.handle(event)
        game.update()
        game.draw()

        if game.scene == "fight" and game.match:
            shake = max(shake, game.match.shake)
            game.match.shake = 0.0
        ox = oy = 0
        if shake > 0.3:
            ox = random.uniform(-shake, shake)
            oy = random.uniform(-shake, shake)
        shake *= 0.84
        screen.fill((0, 0, 0))
        screen.blit(canvas, (int(ox), int(oy)))
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
