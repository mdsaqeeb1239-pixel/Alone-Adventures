import pygame
import sys
import math
import random
import json
import os

pygame.init()

WIDTH, HEIGHT = 400, 700
display = pygame.display.set_mode((WIDTH, HEIGHT))
screen = display            # current draw target (switches to the world surface while drawing the map)
pygame.display.set_caption("Alone Adventures")
clock = pygame.time.Clock()

# ---------------- COLORS ----------------
GREEN = (45, 115, 60)
DARK = (20, 75, 40)
BROWN = (120, 75, 35)
WHITE = (255, 255, 255)
BLUE = (45, 100, 180)
SKIN = (220, 170, 125)
BLACK = (30, 30, 30)
RED = (220, 55, 55)
YELLOW = (240, 190, 40)
CYAN = (50, 180, 230)
GREY = (90, 90, 90)
ORANGE = (255, 125, 30)
PURPLE = (120, 70, 170)
STONE_GREY = (135, 135, 145)
DIM = (65, 65, 95)
SAND = (214, 190, 120)
MUD = (62, 80, 48)

font = pygame.font.Font(None, 25)
big_font = pygame.font.Font(None, 34)
small = pygame.font.Font(None, 20)
tiny = pygame.font.Font(None, 16)
title_font = pygame.font.Font(None, 54)

# ---------------- SOUND ----------------
sound_on = True
sounds = {}
music = None


def make_beep(freq_start, freq_end, ms, volume=0.3):
    rate, fmt, channels = pygame.mixer.get_init()
    count = int(rate * ms / 1000)
    data = bytearray()
    phase = 0.0

    for i in range(count):
        t = i / count
        freq = freq_start + (freq_end - freq_start) * t
        phase += 2 * math.pi * freq / rate
        value = int(32767 * volume * (1 - t) * math.sin(phase))
        data += value.to_bytes(2, "little", signed=True) * channels

    return pygame.mixer.Sound(buffer=bytes(data))


def make_music():
    # a calm looping melody made from soft sine notes
    rate, fmt, channels = pygame.mixer.get_init()
    notes = [220.0, 261.6, 329.6, 392.0, 329.6, 261.6, 293.7, 196.0]
    note_ms = 520
    count = int(rate * note_ms / 1000)
    data = bytearray()

    for freq in notes:
        for i in range(count):
            t = i / count
            env = min(1.0, t * 12) * (1 - t) ** 1.5
            value = int(32767 * 0.07 * env * math.sin(2 * math.pi * freq * i / rate))
            data += value.to_bytes(2, "little", signed=True) * channels

    return pygame.mixer.Sound(buffer=bytes(data))


try:
    if pygame.mixer.get_init() is None:
        pygame.mixer.init()

    if pygame.mixer.get_init()[1] == -16:
        sounds = {
            "pickup": make_beep(700, 1000, 90),
            "swing": make_beep(900, 300, 70, 0.15),
            "hit": make_beep(300, 120, 120),
            "kill": make_beep(500, 200, 200),
            "hurt": make_beep(220, 90, 180),
            "win": make_beep(500, 1200, 600),
            "lose": make_beep(400, 80, 700),
            "build": make_beep(250, 550, 160),
            "eat": make_beep(450, 650, 110),
            "levelup": make_beep(500, 1500, 380),
            "ach": make_beep(800, 1400, 260),
            "thunder": make_beep(140, 40, 600, 0.35),
            "splash": make_beep(350, 700, 140, 0.2),
        }
        music = make_music()
except Exception:
    sounds = {}
    music = None

# which message plays which sound
SFX_FOR_MESSAGE = {
    "Food collected": "pickup",
    "Water collected": "pickup",
    "Wood collected": "pickup",
    "Stone collected": "pickup",
    "+2 wood": "hit",
    "+3 wood": "hit",
    "+1 stone": "hit",
    "+2 stone": "hit",
    "Raw food eaten": "eat",
    "Cooked food eaten": "eat",
    "Water used": "eat",
    "Drank pond water": "eat",
    "Campfire built!": "build",
    "Food cooked!": "build",
    "Added fuel +20s": "build",
    "Zombie attack!": "hurt",
    "You are starving!": "hurt",
    "Cave attack!": "hurt",
    "Berries picked! +2 food": "pickup",
}


def play(name):
    if sound_on and name in sounds:
        sounds[name].play()


def start_music():
    if sound_on and music is not None:
        music.play(loops=-1)


def stop_music():
    if music is not None:
        music.stop()


# ---------------- SAVE FILE (best scores + achievements + saved game) ----------------
try:
    SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alone_save.json")
except Exception:
    SAVE_FILE = "alone_save.json"

best = {"days": 0, "kills": 0, "wins": 0}
unlocked = set()        # achievements stay unlocked forever
saved_game = None       # snapshot of the last saved game (or None)

try:
    with open(SAVE_FILE) as f:
        loaded = json.load(f)
    for key in best:
        best[key] = int(loaded.get(key, 0))
    unlocked = set(loaded.get("ach", []))
    if isinstance(loaded.get("game"), dict):
        saved_game = loaded["game"]
except Exception:
    pass


def write_save_file():
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump({
                "days": best["days"], "kills": best["kills"], "wins": best["wins"],
                "ach": sorted(unlocked), "game": saved_game
            }, f)
    except Exception:
        pass


# ---------------- SETTINGS ----------------
PLAY_TOP = 100          # game area starts below the HUD
PLAY_BOTTOM = 520       # controls live below this line
VIEW_W = WIDTH
VIEW_H = PLAY_BOTTOM - PLAY_TOP
WORLD_W = 1000          # the world is bigger than the screen now
WORLD_H = 1000
GOAL_DAYS = 5           # survive this many days and nights to win

world_surf = pygame.Surface((WORLD_W, WORLD_H))
cam_x = 0
cam_y = 0

# ---------------- WORLD (fixed layout, same every game) ----------------
START_POS = (480, 470)
chest = pygame.Rect(560, 490, 42, 35)
table = pygame.Rect(400, 428, 54, 36)

ponds = [
    pygame.Rect(400, 570, 100, 60),
    pygame.Rect(120, 180, 130, 80),
    pygame.Rect(780, 230, 120, 75),
    pygame.Rect(720, 760, 140, 80),
    pygame.Rect(180, 770, 110, 65),
]
pond_blocks = [p.inflate(-10, -10) for p in ponds]

SAND_RECT = pygame.Rect(560, 50, 300, 170)
SWAMP_RECT = pygame.Rect(70, 470, 240, 150)
MEADOW_RECT = pygame.Rect(380, 790, 260, 150)
cave_mouth = pygame.Rect(870, 520, 80, 64)

_rng = random.Random(2024)
_fixed = [chest, table, cave_mouth] + ponds
_start_zone = pygame.Rect(START_POS[0], START_POS[1], 32, 42).inflate(170, 170)


def _scatter(count, w, h, existing, margin, gap, avoid=()):
    placed = []
    attempts = 0

    while len(placed) < count and attempts < 4000:
        attempts += 1
        r = pygame.Rect(_rng.randint(margin, WORLD_W - margin - w),
                        _rng.randint(margin, WORLD_H - margin - h), w, h)

        if r.colliderect(_start_zone):
            continue
        if any(r.colliderect(a) for a in avoid):
            continue
        if any(r.colliderect(o.inflate(gap, gap)) for o in _fixed):
            continue
        if any(r.colliderect(o.inflate(gap, gap)) for o in existing + placed):
            continue

        placed.append(r)

    return placed


_tree_boxes = _scatter(45, 38, 72, [], 25, 12, avoid=[SAND_RECT, SWAMP_RECT])
trees = [(r.x - 2, r.y + 5) for r in _tree_boxes]
TREE_RECTS = [pygame.Rect(x + 2, y - 5, 34, 72) for x, y in trees]
tree_timers = [0 for _ in trees]      # >0 means the tree was chopped and is regrowing

ROCK_RECTS = _scatter(18, 38, 28, TREE_RECTS, 25, 12)
rock_timers = [0 for _ in ROCK_RECTS]

# tree trunks are solid: you can walk around them but not through them
TRUNK_RECTS = [pygame.Rect(x + 12, y + 38, 12, 27) for x, y in trees]

BUSH_RECTS = _scatter(14, 34, 26, TREE_RECTS + ROCK_RECTS, 25, 12, avoid=[SAND_RECT, SWAMP_RECT])
bush_timers = [0 for _ in BUSH_RECTS]

CRATE_RECTS = _scatter(5, 30, 26, TREE_RECTS + ROCK_RECTS + BUSH_RECTS, 25, 15)
crate_opened = [False for _ in CRATE_RECTS]

CACTUS_RECTS = []

for _attempt in range(300):
    if len(CACTUS_RECTS) >= 9:
        break

    _c = pygame.Rect(_rng.randint(SAND_RECT.x + 30, SAND_RECT.right - 50),
                     _rng.randint(SAND_RECT.y + 20, SAND_RECT.bottom - 55), 18, 34)

    if not any(_c.colliderect(o.inflate(16, 16)) for o in CACTUS_RECTS + ponds + CRATE_RECTS):
        CACTUS_RECTS.append(_c)

flowers = []
_flower_colors = [(240, 90, 130), (250, 220, 70), (255, 255, 255), (170, 110, 230), (255, 150, 60)]

for _i in range(120):
    if _i < 70:
        _fx = _rng.randint(MEADOW_RECT.x + 15, MEADOW_RECT.right - 15)
        _fy = _rng.randint(MEADOW_RECT.y + 12, MEADOW_RECT.bottom - 12)
    else:
        _fx = _rng.randint(20, WORLD_W - 20)
        _fy = _rng.randint(20, WORLD_H - 20)

    flowers.append((_fx, _fy, _rng.choice(_flower_colors)))

SOLID_RECTS = (pond_blocks + [table, chest, cave_mouth] + TRUNK_RECTS
               + [r.inflate(-8, -6) for r in ROCK_RECTS] + CRATE_RECTS
               + [c.inflate(-4, -2) for c in CACTUS_RECTS])

# ---------------- CAVE (a separate dark room, entered from the east side) ----------------
CAVE_W = 640
CAVE_H = 520
CAVE_EXIT = pygame.Rect(36, CAVE_H - 84, 64, 52)
CAVE_CHEST = pygame.Rect(CAVE_W - 110, 44, 46, 36)
CAVE_ROCKS = [pygame.Rect(200, 150, 56, 44), pygame.Rect(330, 300, 64, 48), pygame.Rect(150, 330, 48, 42),
              pygame.Rect(450, 190, 54, 52), pygame.Rect(520, 370, 54, 44), pygame.Rect(300, 90, 48, 40)]
CAVE_SPAWN = (70, CAVE_H - 150)
cave_dots = [(_rng.randint(10, CAVE_W - 10), _rng.randint(10, CAVE_H - 10)) for _ in range(140)]

grass = [(_rng.randint(5, WORLD_W - 5), _rng.randint(10, WORLD_H - 10)) for _ in range(320)]

# ---------------- PLAYER ----------------
player = pygame.Rect(START_POS[0], START_POS[1], 32, 42)
speed = 3
facing = 1              # 1 = right, -1 = left

health = 100
max_health = 100
hunger = 100
thirst = 100

hunger_timer = 0
starve_timer = 0
regen_timer = 0
zombie_damage_timer = 0

kills = 0
attack_timer = 0
slash_timer = 0
drink_timer = 0
animal_timer = 0

# gear the player owns
gear = {"spear": False, "stone_spear": False, "axe": False,
        "pickaxe": False, "armor": False, "lantern": False}

# progress
level = 1
xp = 0
quest_index = 0


def new_stats():
    return {"wood": 0, "stone": 0, "chopped": 0, "mined": 0, "cooked": 0,
            "hunted": 0, "crafted": 0, "fires": 0, "rain": 0, "boss": 0,
            "berries": 0, "crates": 0, "cave": 0, "treasure": 0, "guardian": 0,
            "fished": 0}


stats = new_stats()

ach_banner = ""
ach_timer = 0

in_cave = False
cave_return = (0, 0)
cave_enemies = []
cave_looted = False
cave_hit_timer = 0
in_swamp = False

# ---------------- INVENTORY ----------------
inventory = {"food": 0, "cooked": 0, "water": 0, "wood": 0, "stone": 0}
storage = {"food": 0, "water": 0, "wood": 0, "stone": 0}

apples = []
water_bottles = []
wood_items = []
zombies = []
animals = []

# ---------------- PET DOG ----------------
dog = {"x": 700.0, "y": 400.0, "tamed": False, "hit": 0, "side": 1, "timer": 0, "vx": 0.0, "vy": 0.0}

# ---------------- WEATHER ----------------
raining = False
rain_left = 0
weather_timer = 40000
rain_thirst_timer = 0
rain_drops = [[random.randint(0, VIEW_W), random.randint(0, VIEW_H), random.randint(9, 14)] for _ in range(70)]

# ---------------- DAY AND NIGHT ----------------
day_time = 0
day_duration = 55000
night_duration = 35000

is_night = False
day_count = 1
night_spawn_timer = 0

# ---------------- CAMPFIRE ----------------
campfire = None
campfire_radius = 115
campfire_timer = 0
campfire_duration = 60000

# ---------------- GAME STATE ----------------
started = False
inventory_open = False
chest_open = False
craft_open = False
ach_open = False
game_over = False
won = False
paused = False

move_buttons = {
    "up": pygame.Rect(75, 550, 65, 45),
    "down": pygame.Rect(75, 630, 65, 45),
    "left": pygame.Rect(5, 590, 65, 45),
    "right": pygame.Rect(145, 590, 65, 45)
}

pressed = {key: False for key in move_buttons}

inventory_btn = pygame.Rect(10, 26, 105, 28)
pause_btn = pygame.Rect(285, 26, 105, 28)
fire_btn = pygame.Rect(270, 535, 120, 45)
action_btn = pygame.Rect(270, 590, 120, 45)
attack_btn = pygame.Rect(270, 645, 120, 45)

START_BTN = pygame.Rect(100, 480, 200, 55)
CONTINUE_BTN = pygame.Rect(100, 545, 200, 50)
END_BTN = pygame.Rect(100, 420, 200, 50)
RESUME_BTN = pygame.Rect(100, 290, 200, 50)
SAVE_BTN = pygame.Rect(100, 350, 200, 50)
ACH_BTN = pygame.Rect(100, 410, 200, 50)
RESTART_BTN = pygame.Rect(100, 470, 200, 50)
SOUND_BTN = pygame.Rect(100, 530, 200, 50)
ACH_CLOSE = pygame.Rect(160, 490, 80, 36)

INV_CLOSE = pygame.Rect(280, 190, 80, 40)
INV_FOOD = pygame.Rect(35, 310, 145, 40)
INV_WATER = pygame.Rect(215, 310, 145, 40)
INV_COOKED = pygame.Rect(35, 360, 145, 40)
INV_SPEAR = pygame.Rect(215, 360, 145, 40)

CHEST_BTNS = [
    ("STORE FOOD", pygame.Rect(25, 290, 160, 40), "store", "food"),
    ("STORE WATER", pygame.Rect(215, 290, 160, 40), "store", "water"),
    ("TAKE FOOD", pygame.Rect(25, 345, 160, 40), "take", "food"),
    ("TAKE WATER", pygame.Rect(215, 345, 160, 40), "take", "water"),
    ("STORE WOOD", pygame.Rect(25, 400, 160, 40), "store", "wood"),
    ("TAKE WOOD", pygame.Rect(215, 400, 160, 40), "take", "wood"),
    ("STORE STONE", pygame.Rect(25, 455, 160, 40), "store", "stone"),
    ("TAKE STONE", pygame.Rect(215, 455, 160, 40), "take", "stone"),
]

# crafting table recipes: key -> (name, cost, button position)
RECIPES = {
    "spear": ("SPEAR", {"wood": 2}),
    "stone_spear": ("STONE SPEAR", {"wood": 2, "stone": 3}),
    "axe": ("AXE", {"wood": 3, "stone": 2}),
    "pickaxe": ("PICKAXE", {"wood": 3, "stone": 2}),
    "armor": ("ARMOR", {"wood": 5, "stone": 5}),
    "lantern": ("LANTERN", {"wood": 3, "stone": 3}),
}
CRAFT_ORDER = ["spear", "stone_spear", "axe", "pickaxe", "armor", "lantern"]
CRAFT_BTNS = []

for i, key in enumerate(CRAFT_ORDER):
    CRAFT_BTNS.append((key, pygame.Rect(25 + (i % 2) * 190, 235 + (i // 2) * 60, 170, 50)))

CRAFT_CLOSE = pygame.Rect(160, 450, 80, 36)

message = ""
message_timer = 0

darkness = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
darkness.fill((5, 8, 30, 145))
cave_darkness = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
cave_darkness.fill((3, 3, 12, 205))
rain_tint = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
rain_tint.fill((20, 30, 60, 55))
strip_surf = pygame.Surface((WIDTH, 18), pygame.SRCALPHA)
strip_surf.fill((0, 0, 0, 150))


def make_light(radius):
    # soft circle used to "cut" light out of the night darkness
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    surf.fill((255, 255, 255, 255))

    for r, a in ((radius, 95), (int(radius * 0.75), 55), (int(radius * 0.5), 20)):
        pygame.draw.circle(surf, (255, 255, 255, a), (radius, radius), r)

    return surf


player_light = make_light(120)
lantern_light = make_light(180)
fire_light = make_light(campfire_radius)

# ---------------- NEW: EFFECTS (particles, floating text, fireflies, shake...) ----------------
particles = []          # [x, y, vx, vy, life, maxlife, color, size, gravity]
float_texts = []        # [x, y, text, color, life]
shake = 0
lightning = 0
banner_text = ""
banner_timer = 0
walk_anim = 0.0
walk_moving = False
bg_cache = None

fireflies = [(random.randint(0, WORLD_W), random.randint(0, WORLD_H), random.random() * 6.28)
             for _ in range(70)]
_ff_glow = pygame.Surface((18, 18), pygame.SRCALPHA)

for _r, _a in ((9, 25), (6, 55), (3, 110)):
    pygame.draw.circle(_ff_glow, (255, 255, 150, _a), (9, 9), _r)

# soft dark edges around the game view
vignette = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)

for _i in range(46):
    pygame.draw.rect(vignette, (0, 0, 0, int(85 * (1 - _i / 46.0) ** 2)),
                     (_i, _i, VIEW_W - 2 * _i, VIEW_H - 2 * _i), 1)

# gradient HUD background
hud_bg = pygame.Surface((WIDTH, PLAY_TOP))

for _y in range(PLAY_TOP):
    _t = _y / float(PLAY_TOP)
    pygame.draw.line(hud_bg, (int(16 + 14 * _t), int(58 + 30 * _t), int(34 + 18 * _t)), (0, _y), (WIDTH, _y))

pygame.draw.line(hud_bg, (10, 40, 22), (0, PLAY_TOP - 1), (WIDTH, PLAY_TOP - 1), 2)

_shadow_cache = {}


def draw_shadow(cx, cy, w, h, alpha=70):
    key = (w, h, alpha)
    s = _shadow_cache.get(key)

    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, alpha), (0, 0, w, h))
        _shadow_cache[key] = s

    screen.blit(s, (int(cx - w // 2), int(cy - h // 2)))


def burst(x, y, color, n=8, spd=2.0, life=500, size=3, grav=0.05):
    for _ in range(n):
        if len(particles) > 350:
            return

        a = random.uniform(0, 2 * math.pi)
        s = random.uniform(0.3, 1.0) * spd
        particles.append([x, y, math.cos(a) * s, math.sin(a) * s - 0.5,
                          life * random.uniform(0.6, 1.0), life, color, size, grav])


def float_text(x, y, msg, color=WHITE):
    float_texts.append([x, y, str(msg), color, 900])


def update_fx(dt):
    for p in particles[:]:
        p[0] += p[2]
        p[1] += p[3]
        p[3] += p[8]
        p[4] -= dt

        if p[4] <= 0:
            particles.remove(p)

    for f in float_texts[:]:
        f[1] -= 0.5
        f[4] -= dt

        if f[4] <= 0:
            float_texts.remove(f)


def draw_fx():
    for p in particles:
        s = max(1, int(p[7] * (p[4] / p[5]) + 0.5))
        pygame.draw.circle(screen, p[6], (int(p[0]), int(p[1])), s)

    for f in float_texts:
        img = small.render(f[2], True, f[3])
        sh = small.render(f[2], True, BLACK)
        pos = img.get_rect(center=(int(f[0]), int(f[1])))
        screen.blit(sh, pos.move(1, 1))
        screen.blit(img, pos)


def dark_amount():
    # 0 = bright day, 1 = full night. Dusk and dawn fade smoothly.
    if in_cave:
        return 0.0

    if is_night:
        left = night_duration - day_time
        return 1.0 if left > 5000 else max(0.0, left / 5000.0)

    left = day_duration - day_time

    if left < 9000:
        return 1.0 - left / 9000.0

    return 0.0


def draw_fireflies(amount):
    t = pygame.time.get_ticks()

    for bx, by, ph in fireflies:
        x = bx + math.sin(t / 900.0 + ph) * 20
        y = by + math.cos(t / 1100.0 + ph * 1.3) * 15
        sx = int(x - cam_x)
        sy = int(y - cam_y) + PLAY_TOP

        if -10 < sx < VIEW_W + 10 and PLAY_TOP < sy < PLAY_BOTTOM:
            b = (math.sin(t / 350.0 + ph * 3) + 1) / 2
            _ff_glow.set_alpha(int(255 * b * amount))
            screen.blit(_ff_glow, (sx - 9, sy - 9))

            if b > 0.35:
                pygame.draw.circle(screen, (255, 255, 170), (sx, sy), 2)


# ---------------- HELPERS ----------------
def show_message(msg):
    global message, message_timer
    message = msg
    message_timer = 2200

    if msg in SFX_FOR_MESSAGE:
        play(SFX_FOR_MESSAGE[msg])


def text(msg, x, y, color=WHITE, font_type=font):
    image = font_type.render(str(msg), True, color)
    screen.blit(image, (x, y))


def text_center(msg, y, color=WHITE, font_type=font):
    image = font_type.render(str(msg), True, color)
    screen.blit(image, image.get_rect(center=(WIDTH // 2, y)))


def draw_bar(x, y, value, color, name, maxv=100):
    ratio = max(0.0, min(1.0, value / float(maxv)))
    low = ratio < 0.25 and (pygame.time.get_ticks() // 350) % 2 == 0
    pygame.draw.rect(screen, (12, 14, 16), (x - 1, y - 1, 112, 15), border_radius=7)
    w = int(ratio * 108)

    if w > 0:
        pygame.draw.rect(screen, color, (x, y, w, 13), border_radius=6)
        light = tuple(min(255, c + 70) for c in color)
        pygame.draw.rect(screen, light, (x + 3, y + 2, max(1, w - 6), 3), border_radius=2)

    pygame.draw.rect(screen, (255, 90, 90) if low else (225, 225, 225), (x - 1, y - 1, 112, 15), 1, border_radius=7)
    text(name, x, y - 16, WHITE, small)
    val = tiny.render(str(int(value)), True, (230, 230, 230))
    screen.blit(val, (x + 110 - val.get_width(), y - 13))


def draw_button(rect, label, color=BLUE):
    shade = tuple(max(0, c - 50) for c in color)
    light = tuple(min(255, c + 45) for c in color)
    pygame.draw.rect(screen, shade, rect.move(0, 3), border_radius=8)
    pygame.draw.rect(screen, color, rect, border_radius=8)
    pygame.draw.line(screen, light, (rect.x + 8, rect.y + 2), (rect.right - 8, rect.y + 2), 2)
    image = small.render(label, True, WHITE)
    screen.blit(image, image.get_rect(center=rect.center))


def static_blocks():
    return ([chest, table, cave_mouth] + ponds + TREE_RECTS + ROCK_RECTS
            + CRATE_RECTS + CACTUS_RECTS + BUSH_RECTS)


def ref_pos():
    # where zombies should think the player is (outside, even when hiding in the cave)
    if in_cave:
        return cave_return[0] + 16, cave_return[1] + 21

    return player.center


def zrect(z):
    return pygame.Rect(int(z["x"]), int(z["y"]), z["w"], z["h"])


def clamp_world(x, y, w, h):
    return max(0, min(WORLD_W - w, x)), max(0, min(WORLD_H - h, y))


# ---------------- XP, QUESTS, ACHIEVEMENTS ----------------
def xp_needed():
    return 40 + 30 * level


def gain_xp(amount):
    global xp, level, max_health, health

    xp += amount

    while xp >= xp_needed():
        xp -= xp_needed()
        level += 1
        max_health += 10
        health = min(max_health, health + 30)
        show_message("LEVEL UP! Level " + str(level))
        play("levelup")
        burst(player.centerx, player.centery, (255, 230, 90), 24, 3.0, 800, 3, -0.02)
        float_text(player.centerx, player.y - 12, "LEVEL UP!", (255, 230, 90))


def add_item(name, amount=1):
    inventory[name] += amount

    if name == "wood":
        stats["wood"] += amount
    elif name == "stone":
        stats["stone"] += amount


QUESTS = [
    ("Collect 5 wood", lambda: stats["wood"] >= 5, 20),
    ("Build a campfire", lambda: stats["fires"] >= 1, 25),
    ("Craft a spear", lambda: gear["spear"] or gear["stone_spear"], 30),
    ("Mine 4 stones", lambda: stats["mined"] >= 4, 25),
    ("Craft an axe at the table", lambda: gear["axe"], 40),
    ("Kill 3 zombies", lambda: kills >= 3, 40),
    ("Tame the stray dog (1 food)", lambda: dog["tamed"], 50),
    ("Reach day 3", lambda: day_count >= 3, 60),
    ("Craft armor", lambda: gear["armor"], 60),
    ("Open a supply crate", lambda: stats["crates"] >= 1, 35),
    ("Find and enter the cave (east)", lambda: stats["cave"] >= 1, 45),
    ("Loot the cave treasure", lambda: stats["treasure"] >= 1, 90),
    ("Catch a fish at a pond", lambda: stats["fished"] >= 1, 30),
    ("Survive all 5 days!", lambda: False, 0),
]

ACHIEVEMENTS = [
    ("first_blood", "First Blood", lambda: kills >= 1),
    ("slayer", "Zombie Slayer (20 kills)", lambda: kills >= 20),
    ("lumber", "Lumberjack (chop 10 trees)", lambda: stats["chopped"] >= 10),
    ("miner", "Miner (mine 10 rocks)", lambda: stats["mined"] >= 10),
    ("chef", "Chef (cook 5 foods)", lambda: stats["cooked"] >= 5),
    ("hunter", "Hunter (hunt 5 rabbits)", lambda: stats["hunted"] >= 5),
    ("friend", "Best Friend (tame the dog)", lambda: dog["tamed"]),
    ("crafty", "Crafty (craft 3 items)", lambda: stats["crafted"] >= 3),
    ("survivor", "Survivor (reach day 3)", lambda: day_count >= 3),
    ("boss", "Boss Slayer", lambda: stats["boss"] >= 1),
    ("lvl5", "Veteran (reach level 5)", lambda: level >= 5),
    ("storm", "Stormy (get caught in rain)", lambda: stats["rain"] >= 1),
    ("forager", "Forager (pick 10 berry bushes)", lambda: stats["berries"] >= 10),
    ("looter", "Looter (open 3 crates)", lambda: stats["crates"] >= 3),
    ("spelunker", "Spelunker (enter the cave)", lambda: stats["cave"] >= 1),
    ("treasure", "Treasure Hunter (loot the cave)", lambda: stats["treasure"] >= 1),
    ("golem", "Golem Slayer (cave guardian)", lambda: stats["guardian"] >= 1),
    ("angler", "Angler (catch 5 fish)", lambda: stats["fished"] >= 5),
]


def check_progress():
    global quest_index, ach_banner, ach_timer

    if quest_index < len(QUESTS):
        name, done, reward = QUESTS[quest_index]

        if done():
            quest_index += 1
            show_message("Quest done: " + name)
            play("ach")
            gain_xp(reward)

    for key, title, done in ACHIEVEMENTS:
        if key not in unlocked and done():
            unlocked.add(key)
            ach_banner = "Achievement: " + title
            ach_timer = 3500
            play("ach")
            write_save_file()
            gain_xp(20)


# ---------------- RANDOM SPAWNING ----------------
def spawn_item(size, existing):
    for attempt in range(100):
        x = random.randint(25, WORLD_W - size - 25)
        y = random.randint(25, WORLD_H - size - 25)

        item = pygame.Rect(x, y, size, size)

        if item.colliderect(player.inflate(50, 50)):
            continue

        if any(item.colliderect(r.inflate(30, 30)) for r in static_blocks()):
            continue

        if any(item.colliderect(old.inflate(25, 25)) for old in existing):
            continue

        return item

    return pygame.Rect(60, 60, size, size)


def create_items():
    global apples, water_bottles, wood_items

    apples = []
    water_bottles = []
    wood_items = []

    for i in range(6):
        apples.append(spawn_item(20, apples))

    for i in range(6):
        water_bottles.append(spawn_item(18, apples + water_bottles))

    for i in range(6):
        wood_items.append(spawn_item(20, apples + water_bottles + wood_items))


def new_dog():
    for attempt in range(200):
        x = random.randint(40, WORLD_W - 80)
        y = random.randint(40, WORLD_H - 80)
        r = pygame.Rect(x, y, 28, 20)

        if math.hypot(x - START_POS[0], y - START_POS[1]) < 280:
            continue

        if any(r.colliderect(b.inflate(20, 20)) for b in static_blocks()):
            continue

        return {"x": float(x), "y": float(y), "tamed": False, "hit": 0,
                "side": 1, "timer": 0, "vx": 0.0, "vy": 0.0}

    return {"x": 800.0, "y": 400.0, "tamed": False, "hit": 0,
            "side": 1, "timer": 0, "vx": 0.0, "vy": 0.0}


def drect():
    return pygame.Rect(int(dog["x"]), int(dog["y"]), 28, 20)


# ---------------- DRAW WORLD ----------------
def draw_player():
    cx = player.centerx
    sw = math.sin(walk_anim) * 4 if walk_moving else 0
    bob = abs(math.sin(walk_anim)) * 2 if walk_moving else 0
    x = player.x
    y = int(player.y - bob)

    draw_shadow(cx, player.y + 40, 30, 10, 80)

    # legs and boots
    l1 = int(13 + sw)
    l2 = int(13 - sw)
    pygame.draw.rect(screen, (40, 42, 58), (x + 6, y + 28, 9, l1))
    pygame.draw.rect(screen, (40, 42, 58), (x + 17, y + 28, 9, l2))
    pygame.draw.rect(screen, (75, 48, 25), (x + 5, y + 24 + l1, 11, 5), border_radius=2)
    pygame.draw.rect(screen, (75, 48, 25), (x + 16, y + 24 + l2, 11, 5), border_radius=2)

    # back arm
    ba = int(-sw / 2)
    pygame.draw.rect(screen, (30, 75, 140), (x - 1, y + 16 + ba, 7, 11), border_radius=3)
    pygame.draw.rect(screen, SKIN, (x - 1, y + 26 + ba, 7, 4), border_radius=2)

    # torso
    pygame.draw.rect(screen, (40, 95, 180), (x + 4, y + 14, 24, 17), border_radius=5)
    pygame.draw.rect(screen, (75, 135, 220), (x + 6, y + 15, 20, 4), border_radius=3)
    pygame.draw.rect(screen, (85, 55, 28), (x + 4, y + 27, 24, 3))
    pygame.draw.rect(screen, YELLOW, (x + 14, y + 27, 4, 3))

    if gear["armor"]:
        pygame.draw.rect(screen, STONE_GREY, (x + 5, y + 15, 22, 13), border_radius=4)
        pygame.draw.rect(screen, (190, 190, 200), (x + 7, y + 16, 18, 4), border_radius=2)
        pygame.draw.rect(screen, WHITE, (x + 5, y + 15, 22, 13), 1, border_radius=4)
        pygame.draw.circle(screen, (200, 200, 210), (x + 6, y + 15), 4)
        pygame.draw.circle(screen, (200, 200, 210), (x + 26, y + 15), 4)

    # front arm
    fa = int(sw / 2)
    pygame.draw.rect(screen, (40, 95, 180), (x + 26, y + 16 + fa, 6, 11), border_radius=3)
    pygame.draw.rect(screen, SKIN, (x + 26, y + 26 + fa, 6, 4), border_radius=2)

    # head
    pygame.draw.circle(screen, SKIN, (x + 16, y + 9), 9)
    pygame.draw.ellipse(screen, (55, 38, 26), (x + 6, y - 1, 20, 11))
    pygame.draw.circle(screen, BLACK, (x + 16 + facing * 3, y + 11), 1)
    pygame.draw.circle(screen, BLACK, (x + 16 + facing * 7, y + 11), 1)
    pygame.draw.line(screen, (180, 110, 90), (x + 16 + facing * 3, y + 15), (x + 16 + facing * 6, y + 15), 1)

    # Spear in hand
    if gear["spear"] or gear["stone_spear"]:
        hx, hy = cx + facing * 12, y + 24
        tip = (200, 200, 215) if gear["stone_spear"] else WHITE
        pygame.draw.line(screen, BROWN, (hx, hy), (hx + facing * 20, hy - 22), 3)
        pygame.draw.circle(screen, tip, (hx + facing * 20, hy - 22), 4 if gear["stone_spear"] else 3)

    # Lantern on the back (glows)
    if gear["lantern"]:
        lx = cx - facing * 17
        flick = 1 + int(math.sin(pygame.time.get_ticks() / 120.0))
        pygame.draw.circle(screen, (255, 200, 90), (lx, y + 22), 8 + flick, 1)
        pygame.draw.circle(screen, (255, 220, 120), (lx, y + 22), 5)
        pygame.draw.circle(screen, YELLOW, (lx, y + 22), 5, 1)

    # Slash effect
    if slash_timer > 0:
        if facing > 0:
            arc_rect = (cx + 6, player.centery - 28, 50, 56)
            pygame.draw.arc(screen, WHITE, arc_rect, -1.0, 1.0, 4)
            pygame.draw.arc(screen, (180, 220, 255), (cx + 2, player.centery - 24, 44, 48), -0.9, 0.9, 2)
        else:
            arc_rect = (cx - 56, player.centery - 28, 50, 56)
            pygame.draw.arc(screen, WHITE, arc_rect, math.pi - 1.0, math.pi + 1.0, 4)
            pygame.draw.arc(screen, (180, 220, 255), (cx - 46, player.centery - 24, 44, 48), math.pi - 0.9, math.pi + 0.9, 2)


def draw_tree(x, y, chopped):
    if chopped:
        draw_shadow(x + 18, y + 62, 26, 8, 50)
        pygame.draw.rect(screen, BROWN, (x + 11, y + 50, 14, 15), border_radius=3)
        pygame.draw.ellipse(screen, (170, 125, 75), (x + 11, y + 46, 14, 8))
        pygame.draw.ellipse(screen, (130, 90, 50), (x + 14, y + 48, 8, 4), 1)
        return

    sway = int(math.sin(pygame.time.get_ticks() / 800.0 + x * 0.05) * 2)
    draw_shadow(x + 20, y + 64, 46, 14, 75)

    # trunk
    pygame.draw.rect(screen, (92, 58, 28), (x + 12, y + 30, 12, 35))
    pygame.draw.rect(screen, (135, 90, 45), (x + 12, y + 30, 5, 35))
    pygame.draw.line(screen, (65, 40, 18), (x + 21, y + 38), (x + 21, y + 60), 2)

    # canopy
    cx = x + 18 + sway
    pygame.draw.circle(screen, (16, 62, 34), (cx, y + 22), 25)
    pygame.draw.circle(screen, (26, 90, 48), (cx - 9, y + 17), 17)
    pygame.draw.circle(screen, (26, 90, 48), (cx + 10, y + 21), 15)
    pygame.draw.circle(screen, (44, 125, 64), (cx - 6, y + 10), 12)
    pygame.draw.circle(screen, (74, 160, 88), (cx - 9, y + 6), 6)
    pygame.draw.circle(screen, (60, 140, 76), (cx + 9, y + 12), 5)


def draw_rock(r, mined):
    if mined:
        pygame.draw.ellipse(screen, (85, 85, 92), (r.x + 10, r.y + 14, 18, 10))
        pygame.draw.ellipse(screen, (110, 110, 118), (r.x + 13, r.y + 15, 8, 4))
        return

    draw_shadow(r.centerx + 2, r.bottom - 1, r.w + 8, 10, 65)
    pygame.draw.ellipse(screen, (78, 78, 92), (r.x, r.y + 4, r.w, r.h - 2))
    pygame.draw.ellipse(screen, STONE_GREY, (r.x + 3, r.y, r.w - 8, r.h - 6))
    pygame.draw.ellipse(screen, (168, 168, 180), (r.x + 8, r.y + 3, 14, 8))
    pygame.draw.ellipse(screen, (200, 200, 210), (r.x + 10, r.y + 4, 7, 4))
    pygame.draw.line(screen, (98, 98, 110), (r.x + 20, r.y + 10), (r.x + 26, r.y + 18), 1)


def build_bg():
    # draws the ground once and keeps it (much faster than redrawing every frame)
    global screen, bg_cache
    old = screen
    surf = pygame.Surface((WORLD_W, WORLD_H))
    screen = surf
    r = random.Random(77)

    surf.fill((46, 118, 62))

    # soft patches of lighter / darker grass
    patch = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)

    for _ in range(90):
        w = r.randint(90, 240)
        h = r.randint(60, 160)
        col = (74, 156, 84, 26) if r.random() < 0.5 else (22, 82, 44, 32)
        pygame.draw.ellipse(patch, col, (r.randint(-40, WORLD_W), r.randint(-40, WORLD_H), w, h))

    surf.blit(patch, (0, 0))

    # worn dirt around the camp (table, chest, start point)
    pygame.draw.ellipse(surf, (112, 88, 56), (360, 400, 290, 170))
    pygame.draw.ellipse(surf, (128, 100, 64), (385, 415, 240, 140))

    # soft edges around the biomes
    for rect, col in ((SAND_RECT, (226, 206, 142)), (SWAMP_RECT, (50, 82, 52)), (MEADOW_RECT, (80, 170, 92))):
        halo = pygame.Surface((rect.w + 60, rect.h + 60), pygame.SRCALPHA)

        for k in range(3):
            pygame.draw.ellipse(halo, col + (25 + k * 24,), halo.get_rect().inflate(-k * 14, -k * 10))

        surf.blit(halo, (rect.x - 30, rect.y - 30))

    draw_biomes()

    # dunes in the desert
    for k in range(7):
        dx = SAND_RECT.x + 40 + (k * 41) % (SAND_RECT.w - 100)
        dy = SAND_RECT.y + 30 + (k * 27) % (SAND_RECT.h - 70)
        pygame.draw.arc(surf, (196, 170, 100), (dx, dy, 50, 18), 0.2, 2.9, 2)

    # grass tufts
    for gx, gy in grass:
        c = (38, 100, 52) if r.random() < 0.6 else (62, 140, 72)
        pygame.draw.line(surf, c, (gx, gy), (gx - 2, gy - 6), 2)
        pygame.draw.line(surf, c, (gx, gy), (gx + 2, gy - 5), 2)
        pygame.draw.line(surf, c, (gx, gy), (gx + 5, gy - 4), 1)

    # pebbles and tiny mushrooms
    for _ in range(70):
        px, py = r.randint(20, WORLD_W - 20), r.randint(20, WORLD_H - 20)
        pygame.draw.ellipse(surf, (120, 120, 128), (px, py, 6, 4))

    for _ in range(18):
        px, py = r.randint(20, WORLD_W - 20), r.randint(20, WORLD_H - 20)
        pygame.draw.line(surf, (235, 225, 205), (px, py), (px, py + 4), 2)
        pygame.draw.ellipse(surf, (210, 60, 60), (px - 4, py - 3, 9, 6))

    pygame.draw.rect(surf, DARK, (0, 0, WORLD_W, WORLD_H), 8)
    pygame.draw.rect(surf, (30, 92, 52), (8, 8, WORLD_W - 16, WORLD_H - 16), 4)

    screen = old
    bg_cache = surf


def draw_biomes():
    pygame.draw.ellipse(screen, SAND, SAND_RECT)
    pygame.draw.ellipse(screen, (226, 206, 142), SAND_RECT.inflate(-70, -45))
    pygame.draw.ellipse(screen, MUD, SWAMP_RECT)
    pygame.draw.ellipse(screen, (48, 92, 70), SWAMP_RECT.inflate(-70, -50))
    pygame.draw.ellipse(screen, (62, 142, 78), MEADOW_RECT)

    for i in range(14):
        x = SWAMP_RECT.x + 30 + (i * 37) % (SWAMP_RECT.w - 60)
        y = SWAMP_RECT.y + 30 + (i * 53) % (SWAMP_RECT.h - 55)
        pygame.draw.line(screen, (95, 135, 60), (x, y), (x, y - 13), 2)
        pygame.draw.circle(screen, (110, 80, 45), (x, y - 14), 2)

    for fx, fy, color in flowers:
        pygame.draw.line(screen, (40, 110, 55), (fx, fy), (fx, fy + 6), 1)

        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            pygame.draw.circle(screen, color, (fx + ox, fy + oy), 2)

        pygame.draw.circle(screen, YELLOW, (fx, fy), 1)


def draw_cactus(r):
    draw_shadow(r.centerx + 3, r.bottom, r.w + 10, 8, 55)
    pygame.draw.rect(screen, (34, 118, 62), (r.x + 5, r.y, 9, r.h), border_radius=4)
    pygame.draw.rect(screen, (56, 150, 84), (r.x + 6, r.y + 2, 3, r.h - 4), border_radius=2)
    pygame.draw.rect(screen, (34, 118, 62), (r.x, r.y + 10, 5, 12), border_radius=2)
    pygame.draw.rect(screen, (34, 118, 62), (r.x + 14, r.y + 6, 5, 12), border_radius=2)
    pygame.draw.circle(screen, (240, 120, 160), (r.x + 9, r.y), 3)


def draw_bush(r, empty):
    draw_shadow(r.centerx, r.bottom, r.w + 6, 10, 60)
    pygame.draw.ellipse(screen, (24, 86, 44), r)
    pygame.draw.ellipse(screen, (38, 115, 58), r.inflate(-8, -6).move(-2, -2))
    pygame.draw.ellipse(screen, (62, 152, 80), (r.x + 6, r.y + 3, 14, 8))

    if not empty:
        for ox, oy in ((9, 8), (18, 6), (24, 13), (13, 15)):
            pygame.draw.circle(screen, (170, 25, 40), (r.x + ox, r.y + oy), 4)
            pygame.draw.circle(screen, RED, (r.x + ox, r.y + oy), 3)
            pygame.draw.circle(screen, (255, 170, 170), (r.x + ox - 1, r.y + oy - 1), 1)


def draw_crate(r, opened):
    draw_shadow(r.centerx, r.bottom, r.w + 6, 9, 60)
    pygame.draw.rect(screen, (150, 105, 55), r, border_radius=3)
    pygame.draw.rect(screen, (175, 128, 72), (r.x + 2, r.y + 2, r.w - 4, 4))
    pygame.draw.rect(screen, (90, 60, 25), r, 2, border_radius=3)

    if opened:
        pygame.draw.rect(screen, (40, 28, 15), (r.x + 4, r.y + 4, r.w - 8, 8))
    else:
        pygame.draw.line(screen, (90, 60, 25), (r.x, r.y), (r.right, r.bottom), 2)
        pygame.draw.line(screen, (90, 60, 25), (r.right, r.y), (r.x, r.bottom), 2)
        # little sparkle so crates are easy to spot
        if (pygame.time.get_ticks() // 400 + r.x) % 3 == 0:
            pygame.draw.circle(screen, (255, 255, 200), (r.right - 4, r.y + 4), 2)


def draw_cave_mouth():
    m = cave_mouth
    pygame.draw.ellipse(screen, (85, 82, 92), (m.x - 12, m.y - 18, m.w + 24, m.h + 22))
    pygame.draw.ellipse(screen, (110, 106, 118), (m.x - 4, m.y - 12, m.w + 8, 30))
    pygame.draw.ellipse(screen, (130, 126, 138), (m.x + 6, m.y - 8, m.w - 12, 12))
    pygame.draw.ellipse(screen, (10, 8, 14), (m.x + 14, m.y + 8, m.w - 28, m.h - 8))
    pygame.draw.ellipse(screen, (60, 40, 90), (m.x + 20, m.y + 22, m.w - 40, m.h - 28))
    text("CAVE", m.x + 18, m.y - 30, YELLOW, small)


def draw_overworld():
    if bg_cache is None:
        build_bg()

    screen.blit(bg_cache, (0, 0))

    for p in ponds:
        draw_pond(p)

    draw_cave_mouth()

    for i, r in enumerate(ROCK_RECTS):
        draw_rock(r, rock_timers[i] > 0)

    for i, r in enumerate(BUSH_RECTS):
        draw_bush(r, bush_timers[i] > 0)

    for r in CACTUS_RECTS:
        draw_cactus(r)

    for i, r in enumerate(CRATE_RECTS):
        draw_crate(r, crate_opened[i])

    draw_table()
    draw_chest()

    for i, (x, y) in enumerate(trees):
        draw_tree(x, y, tree_timers[i] > 0)

    draw_items()

    for a in animals:
        draw_animal(a)

    draw_dog()
    draw_player()

    for z in zombies:
        draw_zombie(z)

    draw_fx()


def draw_chest():
    draw_shadow(chest.centerx, chest.bottom, chest.w + 8, 10, 65)
    pygame.draw.rect(screen, BROWN, chest, border_radius=5)
    pygame.draw.rect(screen, (80, 45, 20), (chest.x, chest.y, chest.width, 10), border_radius=3)
    pygame.draw.rect(screen, (150, 100, 55), (chest.x + 3, chest.y + 12, chest.w - 6, 3))
    pygame.draw.rect(screen, YELLOW, (chest.centerx - 4, chest.y + 13, 8, 10))
    pygame.draw.rect(screen, (40, 25, 10), chest, 2, border_radius=5)


def draw_table():
    draw_shadow(table.centerx, table.bottom + 2, table.w + 10, 10, 65)
    pygame.draw.rect(screen, (150, 100, 55), (table.x, table.y, table.w, 22), border_radius=4)
    pygame.draw.rect(screen, (180, 130, 75), (table.x + 3, table.y + 2, table.w - 6, 5), border_radius=2)
    pygame.draw.rect(screen, (90, 55, 25), (table.x, table.y, table.w, 22), 2, border_radius=4)
    pygame.draw.rect(screen, (90, 55, 25), (table.x + 5, table.y + 22, 8, 14))
    pygame.draw.rect(screen, (90, 55, 25), (table.right - 13, table.y + 22, 8, 14))
    # little hammer on top
    pygame.draw.line(screen, STONE_GREY, (table.x + 12, table.y + 10), (table.x + 30, table.y + 6), 4)
    pygame.draw.line(screen, BROWN, (table.x + 30, table.y + 6), (table.x + 42, table.y + 14), 3)


def draw_pond(p):
    t = pygame.time.get_ticks() / 1000.0
    pygame.draw.ellipse(screen, (92, 78, 52), p.inflate(10, 8))
    pygame.draw.ellipse(screen, (28, 78, 150), p)
    pygame.draw.ellipse(screen, (52, 120, 195), p.inflate(-14, -14))
    pygame.draw.ellipse(screen, (80, 150, 215), p.inflate(-38, -30))

    # ripples that grow and fade
    for k in range(2):
        ph = (t * 0.5 + k * 0.5) % 1.0
        rw = int((p.w - 30) * ph) + 8
        rh = int((p.h - 24) * ph) + 5
        rr = pygame.Rect(0, 0, rw, rh)
        rr.center = (p.centerx + k * 16 - 8, p.centery + k * 6 - 3)
        col = (int(170 - 90 * ph), int(215 - 65 * ph), int(245 - 30 * ph))
        pygame.draw.ellipse(screen, col, rr, 1)

    pygame.draw.arc(screen, (190, 228, 250), p.inflate(-40, -30), 0.3, 2.2, 2)
    pygame.draw.circle(screen, (40, 130, 60), (p.x + p.w // 4, p.centery + 6), 6)
    pygame.draw.circle(screen, (255, 170, 200), (p.x + p.w // 4 + 1, p.centery + 4), 2)


def draw_items():
    t = pygame.time.get_ticks() / 300.0

    for apple in apples:
        b = int(math.sin(t + apple.x) * 2)
        draw_shadow(apple.centerx, apple.bottom + 2, 16, 6, 60)
        c = (apple.centerx, apple.centery + b)
        pygame.draw.circle(screen, (180, 28, 40), c, 10)
        pygame.draw.circle(screen, RED, (c[0] - 1, c[1] - 1), 8)
        pygame.draw.circle(screen, (255, 160, 160), (c[0] - 4, c[1] - 4), 2)
        pygame.draw.line(screen, (90, 60, 25), (c[0], c[1] - 8), (c[0] + 2, c[1] - 13), 2)
        pygame.draw.ellipse(screen, (60, 170, 70), (c[0] + 2, c[1] - 13, 7, 4))

    for bottle in water_bottles:
        b = int(math.sin(t + bottle.x) * 2)
        r = bottle.move(0, b)
        draw_shadow(bottle.centerx, bottle.bottom + 2, 16, 6, 60)
        pygame.draw.rect(screen, (30, 140, 190), r, border_radius=5)
        pygame.draw.rect(screen, CYAN, r.inflate(-4, -4), border_radius=4)
        pygame.draw.rect(screen, (230, 230, 240), (r.x + 5, r.y - 4, 8, 5), border_radius=2)
        pygame.draw.line(screen, WHITE, (r.x + 4, r.y + 4), (r.x + 4, r.y + 11), 2)

    for wood in wood_items:
        b = int(math.sin(t + wood.x) * 2)
        r = wood.move(0, b)
        draw_shadow(wood.centerx, wood.bottom + 2, 20, 6, 60)
        pygame.draw.rect(screen, (88, 54, 24), r, border_radius=5)
        pygame.draw.rect(screen, BROWN, r.inflate(-4, -4), border_radius=4)
        pygame.draw.ellipse(screen, (195, 150, 90), (r.right - 8, r.y + 3, 7, r.h - 6))
        pygame.draw.line(screen, (80, 48, 22), (r.x + 4, r.y + 7), (r.x + 13, r.y + 7), 1)


def draw_controls():
    pygame.draw.rect(screen, (28, 80, 45), (0, PLAY_BOTTOM, WIDTH, HEIGHT - PLAY_BOTTOM))
    pygame.draw.line(screen, DARK, (0, PLAY_BOTTOM), (WIDTH, PLAY_BOTTOM), 3)
    pygame.draw.line(screen, (60, 130, 80), (0, PLAY_BOTTOM + 3), (WIDTH, PLAY_BOTTOM + 3), 1)

    for name, button in move_buttons.items():
        held = pressed.get(name, False)
        pygame.draw.rect(screen, (170, 170, 180), button.move(0, 3), border_radius=10)
        pygame.draw.rect(screen, (210, 225, 255) if held else WHITE, button, border_radius=10)
        pygame.draw.rect(screen, GREY, button, 2, border_radius=10)

    text("^", 98, 560, BLUE)
    text("v", 98, 640, BLUE)
    text("<", 28, 600, BLUE)
    text(">", 168, 600, BLUE)


def draw_campfire(ox, oy):
    # drawn on the real screen, so it needs the camera offset
    if campfire is None:
        return

    x = int(campfire[0] - ox)
    y = int(campfire[1] - oy + PLAY_TOP)
    t = pygame.time.get_ticks()
    f1 = int(math.sin(t / 70.0) * 2)
    f2 = int(math.cos(t / 55.0) * 2)
    rad = campfire_radius + int(math.sin(t / 130.0) * 4)

    glow = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 150, 30, 28), (rad, rad), rad)
    pygame.draw.circle(glow, (255, 170, 50, 30), (rad, rad), int(rad * 0.6))
    pygame.draw.circle(glow, (255, 210, 90, 34), (rad, rad), int(rad * 0.28))
    screen.blit(glow, (x - rad, y - rad))

    pygame.draw.ellipse(screen, (60, 35, 15), (x - 16, y + 4, 32, 12))
    pygame.draw.line(screen, BROWN, (x - 13, y + 11), (x + 13, y - 3), 6)
    pygame.draw.line(screen, (95, 58, 28), (x - 13, y - 3), (x + 13, y + 11), 6)
    pygame.draw.polygon(screen, (225, 70, 20), [(x - 11, y + 4), (x + f1 - 5, y - 16 + f2), (x, y - 6),
                                                 (x + f2 + 5, y - 21 + f1), (x + 11, y + 4)])
    pygame.draw.polygon(screen, ORANGE, [(x - 7, y + 4), (x + f2 - 1, y - 12), (x + 7, y + 4)])
    pygame.draw.polygon(screen, YELLOW, [(x - 4, y + 4), (x + f1, y - 7), (x + 4, y + 4)])


def draw_zombie(z):
    zombie = zrect(z)
    info = ZOMBIE_KINDS[z["kind"]]
    base = info["color"]
    dark = tuple(max(0, c - 40) for c in base)
    light = tuple(min(255, c + 35) for c in base)
    t = pygame.time.get_ticks() / 150.0 + z["x"] * 0.1
    step = int(math.sin(t) * 3)
    cx = zombie.centerx
    radius = zombie.width // 2 + 1
    eye_gap = zombie.width // 5
    eye_size = max(3, zombie.width // 10)
    leg_w = zombie.width // 4
    toward = 1 if player.centerx >= cx else -1

    draw_shadow(cx, zombie.bottom, zombie.width + 8, 10, 75)

    # legs (they shuffle)
    pygame.draw.rect(screen, (45, 50, 70), (zombie.x + 4, zombie.bottom - 19, leg_w, 12 + step))
    pygame.draw.rect(screen, (45, 50, 70), (zombie.right - 4 - leg_w, zombie.bottom - 19, leg_w, 12 - step))

    # torn shirt
    pygame.draw.rect(screen, (90, 55, 55), (zombie.x + 3, zombie.centery + 2, zombie.width - 6, 15), border_radius=4)
    pygame.draw.line(screen, (60, 35, 35), (zombie.x + 8, zombie.centery + 17), (zombie.x + 11, zombie.centery + 12), 2)

    # arms stretched toward the player
    ay = zombie.centery + 6
    pygame.draw.line(screen, dark, (cx, ay), (cx + toward * (radius + 8), ay - 2 + step), 5)
    pygame.draw.line(screen, base, (cx, ay + 4), (cx + toward * (radius + 5), ay + 4 - step), 5)

    # head
    pygame.draw.circle(screen, base, (cx, zombie.centery - 2), radius)
    pygame.draw.circle(screen, light, (cx - 3, zombie.centery - 7), max(3, radius // 3))
    pygame.draw.circle(screen, (255, 90, 90), (cx - eye_gap, zombie.centery - 6), eye_size + 1, 1)
    pygame.draw.circle(screen, RED, (cx - eye_gap, zombie.centery - 6), eye_size)
    pygame.draw.circle(screen, RED, (cx + eye_gap, zombie.centery - 6), eye_size)
    pygame.draw.line(screen, (30, 20, 20), (cx - eye_gap, zombie.centery + 4), (cx + eye_gap, zombie.centery + 4), 2)

    if z["kind"] == "boss":
        pygame.draw.polygon(screen, (230, 220, 200), [(cx - radius + 2, zombie.centery - 12), (cx - radius - 4, zombie.centery - radius - 10), (cx - radius + 10, zombie.centery - 18)])
        pygame.draw.polygon(screen, (230, 220, 200), [(cx + radius - 2, zombie.centery - 12), (cx + radius + 4, zombie.centery - radius - 10), (cx + radius - 10, zombie.centery - 18)])

    # health bar
    pygame.draw.rect(screen, BLACK, (zombie.x, zombie.y - 8, zombie.width, 5))
    pygame.draw.rect(
        screen, RED,
        (zombie.x, zombie.y - 8, int(zombie.width * max(0, z["hp"]) / z["max"]), 5)
    )

    if z["kind"] == "boss":
        text("BOSS", zombie.x + 8, zombie.y - 24, RED, small)


def draw_animal(a):
    r = arect(a)
    moving_now = a["vx"] != 0 or a["vy"] != 0
    hop = int(abs(math.sin(pygame.time.get_ticks() / 120 + a["x"])) * 3) if moving_now else 0
    cx, cy = r.centerx, r.centery - hop
    side = 1 if a["vx"] >= 0 else -1
    fur = (235, 230, 220)

    draw_shadow(r.centerx, r.bottom, 24, 7, 55)
    pygame.draw.ellipse(screen, fur, (cx - 12, cy - 6, 24, 15))
    pygame.draw.circle(screen, fur, (cx + side * 10, cy - 4), 6)
    pygame.draw.rect(screen, fur, (cx + side * 10 - 4, cy - 16, 3, 9), border_radius=2)
    pygame.draw.rect(screen, fur, (cx + side * 10 + 1, cy - 16, 3, 9), border_radius=2)
    pygame.draw.line(screen, (240, 170, 180), (cx + side * 10 - 3, cy - 14), (cx + side * 10 - 3, cy - 10), 1)
    pygame.draw.circle(screen, BLACK, (cx + side * 12, cy - 5), 1)
    pygame.draw.circle(screen, WHITE, (cx - side * 12, cy), 3)


def draw_dog():
    r = drect()
    side = dog["side"]
    cx, cy = r.centerx, r.centery
    fur = (170, 115, 65)
    dark_fur = (110, 70, 35)
    wag = int(math.sin(pygame.time.get_ticks() / 90) * 4)

    draw_shadow(cx, cy + 9, 30, 9, 70)
    pygame.draw.ellipse(screen, fur, (cx - 13, cy - 7, 26, 15))
    pygame.draw.ellipse(screen, (205, 155, 100), (cx - 8, cy - 2, 16, 8))
    pygame.draw.line(screen, dark_fur, (cx - side * 12, cy - 3), (cx - side * 19, cy - 9 + wag), 3)
    pygame.draw.circle(screen, fur, (cx + side * 12, cy - 6), 7)
    pygame.draw.circle(screen, dark_fur, (cx + side * 9, cy - 12), 3)
    pygame.draw.circle(screen, BLACK, (cx + side * 14, cy - 7), 1)
    pygame.draw.circle(screen, BLACK, (cx + side * 18, cy - 4), 2)
    pygame.draw.rect(screen, dark_fur, (cx - 9, cy + 4, 4, 6))
    pygame.draw.rect(screen, dark_fur, (cx + 5, cy + 4, 4, 6))

    if dog["tamed"]:
        pygame.draw.line(screen, RED, (cx + side * 6, cy - 3), (cx + side * 8, cy + 2), 3)
        pygame.draw.circle(screen, YELLOW, (cx + side * 8, cy + 3), 2)
    elif near(r, 160):
        text("?", cx - 3, cy - 30, YELLOW, small)


# ---------------- ZOMBIES ----------------
ZOMBIE_KINDS = {
    "walker": {"w": 32, "h": 38, "mult": 1.0, "bonus": 0, "color": (65, 115, 65)},
    "runner": {"w": 28, "h": 34, "mult": 1.8, "bonus": 0, "color": (160, 115, 40)},
    "boss": {"w": 50, "h": 58, "mult": 0.7, "bonus": 6, "color": (120, 40, 60)},
}


def spawn_zombie(kind=None):
    # runners show up from day 3, the boss comes on the final night
    if kind is None:
        kind = "runner" if (day_count >= 3 and random.random() < 0.3) else "walker"

    info = ZOMBIE_KINDS[kind]
    w, h = info["w"], info["h"]

    if kind == "boss":
        hp = 14
    elif kind == "runner":
        hp = 2
    else:
        hp = 3 + day_count // 3

    for attempt in range(40):
        # zombies appear in a ring around the player, just outside the screen
        angle = random.uniform(0, 2 * math.pi)
        dist = random.randint(240, 340)
        rx, ry = ref_pos()
        x = rx + math.cos(angle) * dist - w / 2
        y = ry + math.sin(angle) * dist - h / 2
        x, y = clamp_world(x, y, w, h)

        z = {
            "x": float(x), "y": float(y), "hp": hp, "max": hp,
            "kind": kind, "w": w, "h": h,
            "mult": info["mult"], "bonus": info["bonus"]
        }

        # last few attempts accept any spot so the boss never fails to spawn
        if attempt < 35 and zrect(z).colliderect(pygame.Rect(rx - 150, ry - 150, 300, 300)):
            continue

        zombies.append(z)
        return


# ---------------- ANIMALS (rabbits) ----------------
def arect(a):
    return pygame.Rect(int(a["x"]), int(a["y"]), 26, 20)


def spawn_animal():
    for attempt in range(40):
        x = random.randint(30, WORLD_W - 60)
        y = random.randint(30, WORLD_H - 60)
        r = pygame.Rect(x, y, 26, 20)

        if r.colliderect(player.inflate(120, 120)):
            continue

        if any(r.colliderect(b.inflate(10, 10)) for b in static_blocks()):
            continue

        animals.append({"x": float(x), "y": float(y), "vx": 0.0, "vy": 0.0, "timer": 0, "hp": 2})
        return


def update_animals(dt):
    blocks = static_blocks()

    for a in animals:
        r = arect(a)
        dx = r.centerx - player.centerx
        dy = r.centery - player.centery
        dist = math.hypot(dx, dy)

        if 0 < dist < 90:
            # run away from the player
            a["vx"] = dx / dist * 1.7
            a["vy"] = dy / dist * 1.7
            a["timer"] = 300
        else:
            a["timer"] -= dt

            if a["timer"] <= 0:
                if random.random() < 0.5:
                    a["vx"] = 0.0
                    a["vy"] = 0.0
                else:
                    angle = random.uniform(0, 2 * math.pi)
                    a["vx"] = math.cos(angle) * 0.7
                    a["vy"] = math.sin(angle) * 0.7

                a["timer"] = random.randint(800, 2000)

        nx = a["x"] + a["vx"]
        ny = a["y"] + a["vy"]
        test = pygame.Rect(int(nx), int(ny), 26, 20)

        if any(test.colliderect(b.inflate(-8, -8)) for b in blocks):
            a["vx"] *= -1
            a["vy"] *= -1
        else:
            a["x"] = nx
            a["y"] = ny

        a["x"] = max(0, min(WORLD_W - 26, a["x"]))
        a["y"] = max(0, min(WORLD_H - 20, a["y"]))


def update_zombies(dt):
    global zombie_damage_timer, health, shake

    touching = False
    hit_bonus = 0
    spd = 1.0 + 0.15 * day_count

    for z in zombies:
        zr = zrect(z)
        dx = player.centerx - zr.centerx
        dy = player.centery - zr.centery
        distance = math.hypot(dx, dy)

        # Campfire protects nearby area and pushes zombies away
        protected = False

        if campfire is not None:
            fx = zr.centerx - campfire[0]
            fy = zr.centery - campfire[1]
            fire_distance = math.hypot(fx, fy)

            if fire_distance < campfire_radius:
                protected = True
                if fire_distance > 0:
                    z["x"] += fx / fire_distance * 0.8
                    z["y"] += fy / fire_distance * 0.8

        if distance > 0 and not protected:
            z["x"] += dx / distance * spd * z["mult"]
            z["y"] += dy / distance * spd * z["mult"]

        z["x"], z["y"] = clamp_world(z["x"], z["y"], z["w"], z["h"])

        if player.colliderect(zrect(z)) and not protected:
            touching = True
            hit_bonus = max(hit_bonus, z["bonus"])

    if touching:
        zombie_damage_timer += dt

        if zombie_damage_timer >= 1200:
            damage = 4 + day_count + hit_bonus

            if gear["armor"]:
                damage = int(damage * 0.7)

            health = max(0, health - damage)
            zombie_damage_timer = 0
            show_message("Zombie attack!")
            shake = 240
            burst(player.centerx, player.centery, (200, 40, 40), 10, 2.5, 500, 3, 0.05)
            float_text(player.centerx, player.y - 8, "-" + str(damage), (255, 110, 110))
    else:
        zombie_damage_timer = 0


def kill_zombie(z, by_dog=False):
    global kills

    zombies.remove(z)
    kills += 1
    play("kill")
    burst(z["x"] + z["w"] / 2, z["y"] + z["h"] / 2, ZOMBIE_KINDS[z["kind"]]["color"], 18, 3.0, 700, 3, 0.04)

    if z["kind"] == "boss":
        stats["boss"] += 1
        inventory["food"] += 3
        gain_xp(100)
        show_message("BOSS DEFEATED! +3 food")
    else:
        gain_xp(20 if z["kind"] == "runner" else 15)

        if by_dog:
            show_message("Your dog killed a zombie!")
        elif random.random() < 0.4:
            inventory["food"] += 1
            show_message("Zombie dropped food!")
        else:
            show_message("Zombie killed!")


def update_dog(dt):
    dr = drect()

    if dog["tamed"]:
        dx = player.centerx - dr.centerx
        dy = player.centery - dr.centery
        dist = math.hypot(dx, dy)

        if dist > 600:
            # too far away: it catches up
            dog["x"] = player.x - 40.0
            dog["y"] = player.y + 10.0
        elif dist > 55:
            step = 2.4 if dist > 120 else 1.8
            dog["x"] += dx / dist * step
            dog["y"] += dy / dist * step

        if abs(dx) > 4:
            dog["side"] = 1 if dx > 0 else -1

        dog["hit"] = max(0, dog["hit"] - dt)

        # attack zombies that come close
        if dog["hit"] <= 0:
            for z in zombies[:]:
                zr = zrect(z)

                if math.hypot(zr.centerx - dr.centerx, zr.centery - dr.centery) <= 40:
                    z["hp"] -= 1
                    play("hit")
                    burst(zr.centerx, zr.centery, (200, 60, 60), 6, 2.0, 400, 2, 0.05)
                    dog["hit"] = 800

                    if z["hp"] <= 0:
                        kill_zombie(z, by_dog=True)

                    break
    else:
        # a stray dog wanders slowly
        dog["timer"] -= dt

        if dog["timer"] <= 0:
            if random.random() < 0.5:
                dog["vx"] = 0.0
                dog["vy"] = 0.0
            else:
                angle = random.uniform(0, 2 * math.pi)
                dog["vx"] = math.cos(angle) * 0.5
                dog["vy"] = math.sin(angle) * 0.5
                dog["side"] = 1 if dog["vx"] >= 0 else -1

            dog["timer"] = random.randint(1000, 2500)

        test = pygame.Rect(int(dog["x"] + dog["vx"]), int(dog["y"] + dog["vy"]), 28, 20)

        if not any(test.colliderect(b) for b in static_blocks()):
            dog["x"] += dog["vx"]
            dog["y"] += dog["vy"]

    dog["x"] = max(0, min(WORLD_W - 28, dog["x"]))
    dog["y"] = max(0, min(WORLD_H - 20, dog["y"]))


# ---------------- CAVE ----------------
def erect(e):
    return pygame.Rect(int(e["x"]), int(e["y"]), e["w"], e["h"])


def spawn_cave_enemies():
    global cave_enemies
    cave_enemies = []

    for i in range(6):
        for attempt in range(60):
            x = random.randint(40, CAVE_W - 70)
            y = random.randint(40, CAVE_H - 70)
            r = pygame.Rect(x, y, 24, 18)

            if math.hypot(x - CAVE_SPAWN[0], y - CAVE_SPAWN[1]) < 220:
                continue

            if any(r.colliderect(b.inflate(10, 10)) for b in CAVE_ROCKS + [CAVE_CHEST]):
                continue

            cave_enemies.append({"kind": "bat", "x": float(x), "y": float(y), "w": 24, "h": 18,
                                 "hp": 2, "max": 2, "vx": 0.0, "vy": 0.0, "timer": 0})
            break

    cave_enemies.append({"kind": "golem", "x": float(CAVE_W - 200), "y": 120.0, "w": 46, "h": 52,
                         "hp": 12, "max": 12, "vx": 0.0, "vy": 0.0, "timer": 0})


def update_cave(dt):
    global cave_hit_timer, health, shake

    touching = False
    bonus = 0

    for e in cave_enemies:
        er = erect(e)
        dx = player.centerx - er.centerx
        dy = player.centery - er.centery
        dist = math.hypot(dx, dy)

        if e["kind"] == "bat":
            if 0 < dist < 260:
                e["vx"] = dx / dist * 1.9 + random.uniform(-0.6, 0.6)
                e["vy"] = dy / dist * 1.9 + random.uniform(-0.6, 0.6)
            else:
                e["timer"] -= dt

                if e["timer"] <= 0:
                    angle = random.uniform(0, 2 * math.pi)
                    e["vx"] = math.cos(angle) * 0.9
                    e["vy"] = math.sin(angle) * 0.9
                    e["timer"] = random.randint(600, 1500)
        else:
            if 0 < dist < 320:
                e["vx"] = dx / dist * 0.95
                e["vy"] = dy / dist * 0.95
            else:
                e["vx"] = 0.0
                e["vy"] = 0.0

        test = pygame.Rect(int(e["x"] + e["vx"]), int(e["y"] + e["vy"]), e["w"], e["h"])

        if not any(test.colliderect(b) for b in CAVE_ROCKS):
            e["x"] += e["vx"]
            e["y"] += e["vy"]

        e["x"] = max(0, min(CAVE_W - e["w"], e["x"]))
        e["y"] = max(0, min(CAVE_H - e["h"], e["y"]))

        if player.colliderect(erect(e)):
            touching = True

            if e["kind"] == "golem":
                bonus = 6

    if touching:
        cave_hit_timer += dt

        if cave_hit_timer >= 900:
            damage = 3 + bonus

            if gear["armor"]:
                damage = int(damage * 0.7)

            health = max(0, health - damage)
            cave_hit_timer = 0
            show_message("Cave attack!")
            shake = 200
            burst(player.centerx, player.centery, (200, 40, 40), 8, 2.5, 500, 3, 0.05)
            float_text(player.centerx, player.y - 8, "-" + str(damage), (255, 110, 110))
    else:
        cave_hit_timer = 0


def draw_cave_enemy(e):
    r = erect(e)

    if e["kind"] == "bat":
        flap = int(math.sin(pygame.time.get_ticks() / 70 + e["x"]) * 5)
        pygame.draw.ellipse(screen, (70, 50, 90), (r.x + 6, r.y + 3, 12, 12))
        pygame.draw.polygon(screen, (50, 35, 70), [(r.x + 8, r.y + 8), (r.x - 6, r.y + 2 + flap), (r.x + 4, r.y + 13)])
        pygame.draw.polygon(screen, (50, 35, 70), [(r.x + 16, r.y + 8), (r.x + 30, r.y + 2 + flap), (r.x + 20, r.y + 13)])
        pygame.draw.polygon(screen, (90, 65, 115), [(r.x + 8, r.y + 4), (r.x + 9, r.y - 3), (r.x + 12, r.y + 3)])
        pygame.draw.polygon(screen, (90, 65, 115), [(r.x + 16, r.y + 4), (r.x + 15, r.y - 3), (r.x + 12, r.y + 3)])
        pygame.draw.circle(screen, RED, (r.x + 9, r.y + 7), 2)
        pygame.draw.circle(screen, RED, (r.x + 15, r.y + 7), 2)
    else:
        pygame.draw.rect(screen, (105, 100, 115), r, border_radius=8)
        pygame.draw.rect(screen, (70, 66, 80), r, 3, border_radius=8)
        pygame.draw.rect(screen, (130, 125, 140), (r.x + 6, r.y + 6, r.w - 12, 14), border_radius=4)
        pulse = 4 + int(math.sin(pygame.time.get_ticks() / 200.0) * 1.5)
        pygame.draw.circle(screen, (255, 120, 60), (r.x + 14, r.y + 15), pulse)
        pygame.draw.circle(screen, (255, 120, 60), (r.right - 14, r.y + 15), pulse)
        pygame.draw.circle(screen, RED, (r.x + 14, r.y + 15), 3)
        pygame.draw.circle(screen, RED, (r.right - 14, r.y + 15), 3)
        text("GUARDIAN", r.x - 4, r.y - 28, RED, small)

    pygame.draw.rect(screen, BLACK, (r.x, r.y - 8, r.w, 5))
    pygame.draw.rect(screen, RED, (r.x, r.y - 8, int(r.w * max(0, e["hp"]) / e["max"]), 5))


def draw_cave():
    screen.fill((46, 42, 54))

    for x, y in cave_dots:
        pygame.draw.circle(screen, (60, 56, 70), (x, y), 3)

    # glowing crystals
    for i in range(0, len(cave_dots), 9):
        x, y = cave_dots[i]
        c = (110, 200, 230) if i % 18 == 0 else (190, 120, 230)
        pygame.draw.polygon(screen, c, [(x, y), (x + 4, y - 12), (x + 8, y)])
        pygame.draw.polygon(screen, (230, 240, 255), [(x + 3, y - 2), (x + 4, y - 9), (x + 5, y - 2)])

    pygame.draw.rect(screen, (25, 22, 30), (0, 0, CAVE_W, CAVE_H), 10)

    pygame.draw.rect(screen, (30, 25, 20), CAVE_EXIT, border_radius=6)
    pygame.draw.rect(screen, (190, 150, 70), CAVE_EXIT, 3, border_radius=6)
    text("EXIT", CAVE_EXIT.x + 16, CAVE_EXIT.y + 18, YELLOW, small)

    body = (90, 70, 30) if cave_looted else (200, 150, 40)
    pygame.draw.rect(screen, body, CAVE_CHEST, border_radius=5)
    pygame.draw.rect(screen, (120, 80, 20), (CAVE_CHEST.x, CAVE_CHEST.y, CAVE_CHEST.w, 12), border_radius=3)

    if not cave_looted:
        pygame.draw.rect(screen, WHITE, (CAVE_CHEST.centerx - 4, CAVE_CHEST.y + 14, 8, 10))
        if (pygame.time.get_ticks() // 300) % 2 == 0:
            pygame.draw.circle(screen, (255, 255, 200), (CAVE_CHEST.right - 6, CAVE_CHEST.y + 6), 3)

    for r in CAVE_ROCKS:
        draw_shadow(r.centerx, r.bottom, r.w + 6, 9, 70)
        pygame.draw.ellipse(screen, (78, 74, 88), r)
        pygame.draw.ellipse(screen, (105, 100, 118), r.inflate(-14, -14))

    for e in cave_enemies:
        draw_cave_enemy(e)

    draw_player()
    draw_fx()


# ---------------- ACTIONS ----------------
def near(rect, pad=65):
    return player.colliderect(rect.inflate(pad, pad))


def nearest_tree():
    for i, r in enumerate(TREE_RECTS):
        if tree_timers[i] <= 0 and player.colliderect(r.inflate(30, 30)):
            return i
    return None


def nearest_rock():
    for i, r in enumerate(ROCK_RECTS):
        if rock_timers[i] <= 0 and player.colliderect(r.inflate(30, 30)):
            return i
    return None


def nearest_bush():
    for i, r in enumerate(BUSH_RECTS):
        if bush_timers[i] <= 0 and player.colliderect(r.inflate(30, 30)):
            return i
    return None


def nearest_crate():
    for i, r in enumerate(CRATE_RECTS):
        if not crate_opened[i] and player.colliderect(r.inflate(30, 30)):
            return i
    return None


def enter_cave():
    global in_cave, cave_return, pressed
    cave_return = (player.x, player.y)
    in_cave = True
    player.x, player.y = CAVE_SPAWN
    pressed = {key: False for key in move_buttons}
    stats["cave"] += 1
    gain_xp(15)
    show_message("You entered the dark cave...")


def exit_cave():
    global in_cave, pressed
    in_cave = False
    player.x = cave_mouth.x + 24
    player.y = cave_mouth.bottom + 8
    pressed = {key: False for key in move_buttons}

    if dog["tamed"]:
        dog["x"] = player.x - 40.0
        dog["y"] = player.y + 10.0

    show_message("Back outside")


def loot_cave():
    global cave_looted
    cave_looted = True
    stats["treasure"] += 1
    add_item("stone", 6)
    add_item("wood", 5)
    inventory["food"] += 3
    inventory["cooked"] += 2
    inventory["water"] += 2
    gain_xp(80)
    play("win")
    burst(CAVE_CHEST.centerx, CAVE_CHEST.centery, (255, 220, 80), 30, 3.5, 900, 3, 0.03)
    show_message("Treasure! Loot found in the chest")


def open_crate(i):
    crate_opened[i] = True
    stats["crates"] += 1
    wood = random.randint(2, 4)
    stone = random.randint(1, 3)
    food = random.randint(1, 2)
    add_item("wood", wood)
    add_item("stone", stone)
    inventory["food"] += food

    if random.random() < 0.3:
        inventory["water"] += 1

    burst(CRATE_RECTS[i].centerx, CRATE_RECTS[i].centery, (255, 220, 80), 14, 2.5, 700, 3, 0.04)
    gain_xp(15)
    show_message("Crate: +" + str(wood) + " wood +" + str(stone) + " stone +" + str(food) + " food")


def near_pond():
    return any(near(p, 40) for p in ponds)


def near_campfire():
    if campfire is None:
        return False
    return math.hypot(player.centerx - campfire[0], player.centery - campfire[1]) < 85


def get_action():
    if in_cave:
        if near(CAVE_EXIT, 40):
            return "EXIT CAVE"
        if not cave_looted and near(CAVE_CHEST, 50):
            return "LOOT TREASURE"
        return None

    if near(chest):
        return "OPEN CHEST"
    if near(table, 50):
        return "CRAFT"
    if not dog["tamed"] and near(drect(), 50):
        return "TAME DOG"
    if near(cave_mouth, 50):
        return "ENTER CAVE"
    if nearest_crate() is not None:
        return "OPEN CRATE"
    if near_campfire() and inventory["food"] > 0:
        return "COOK FOOD"
    if near_pond():
        # thirsty: drink. Not thirsty: go fishing!
        return "DRINK" if thirst < 85 else "FISH"
    if nearest_bush() is not None:
        return "PICK BERRIES"
    if nearest_rock() is not None:
        return "MINE STONE"
    if nearest_tree() is not None:
        return "CHOP WOOD"
    return None


def do_action():
    global chest_open, craft_open, thirst, drink_timer

    action = get_action()

    if action == "EXIT CAVE":
        exit_cave()

    elif action == "LOOT TREASURE":
        loot_cave()

    elif action == "ENTER CAVE":
        enter_cave()

    elif action == "OPEN CRATE":
        open_crate(nearest_crate())

    elif action == "PICK BERRIES":
        i = nearest_bush()
        add_item("food", 2)
        stats["berries"] += 1
        bush_timers[i] = 30000
        burst(BUSH_RECTS[i].centerx, BUSH_RECTS[i].centery, (210, 40, 60), 10, 2.0, 500, 3, 0.05)
        float_text(BUSH_RECTS[i].centerx, BUSH_RECTS[i].y - 6, "+2 food", (255, 150, 150))
        gain_xp(3)
        show_message("Berries picked! +2 food")

    elif action == "OPEN CHEST":
        chest_open = True

    elif action == "CRAFT":
        craft_open = True

    elif action == "TAME DOG":
        if inventory["food"] >= 1:
            inventory["food"] -= 1
            dog["tamed"] = True
            gain_xp(40)
            burst(dog["x"] + 14, dog["y"], (255, 120, 160), 14, 2.0, 800, 3, -0.03)
            show_message("Dog tamed! It will fight for you")
            play("ach")
        else:
            show_message("Need 1 raw food to tame")

    elif action == "COOK FOOD":
        inventory["food"] -= 1
        inventory["cooked"] += 1
        stats["cooked"] += 1
        gain_xp(3)
        burst(campfire[0], campfire[1] - 10, ORANGE, 10, 2.0, 600, 3, -0.03)
        show_message("Food cooked!")

    elif action == "DRINK":
        if drink_timer > 0:
            show_message("Wait a bit...")
        elif thirst >= 100:
            show_message("Not thirsty")
        else:
            thirst = min(100, thirst + 25)
            drink_timer = 2500
            burst(player.centerx, player.centery - 12, (170, 215, 245), 8, 2.0, 500, 2, 0.08)
            show_message("Drank pond water")

    elif action == "FISH":
        if drink_timer > 0:
            show_message("Wait a bit...")
        else:
            drink_timer = 2500
            burst(player.centerx, player.centery - 12, (170, 215, 245), 10, 2.2, 600, 2, 0.08)
            play("splash")

            if random.random() < 0.6:
                n = 2 if (gear["spear"] or gear["stone_spear"]) else 1
                inventory["food"] += n
                stats["fished"] += 1
                gain_xp(6)
                float_text(player.centerx, player.y - 8, "+" + str(n) + " fish", (170, 215, 245))
                show_message("Caught a fish! +" + str(n) + " food")
            else:
                show_message("The fish got away...")

    elif action == "MINE STONE":
        i = nearest_rock()
        amount = 2 if gear["pickaxe"] else 1
        add_item("stone", amount)
        stats["mined"] += 1
        rock_timers[i] = 40000
        burst(ROCK_RECTS[i].centerx, ROCK_RECTS[i].centery, (190, 190, 205), 10, 2.5, 450, 2, 0.1)
        float_text(ROCK_RECTS[i].centerx, ROCK_RECTS[i].y - 6, "+" + str(amount) + " stone", (210, 210, 225))
        gain_xp(5)
        show_message("+" + str(amount) + " stone")

    elif action == "CHOP WOOD":
        i = nearest_tree()
        amount = 3 if gear["axe"] else 2
        add_item("wood", amount)
        stats["chopped"] += 1
        tree_timers[i] = 18000 if gear["axe"] else 25000
        burst(TREE_RECTS[i].centerx, TREE_RECTS[i].centery, (60, 150, 70), 10, 2.5, 600, 3, 0.07)
        burst(TREE_RECTS[i].centerx, TREE_RECTS[i].bottom - 10, (150, 100, 50), 6, 2.0, 500, 2, 0.08)
        float_text(TREE_RECTS[i].centerx, TREE_RECTS[i].y, "+" + str(amount) + " wood", (230, 190, 120))
        gain_xp(4)
        show_message("+" + str(amount) + " wood")


def weapon_stats():
    if gear["stone_spear"]:
        dmg, reach = 3, 80
    elif gear["spear"]:
        dmg, reach = 2, 70
    else:
        dmg, reach = 1, 55

    return dmg + (level - 1) // 4, reach


def attack():
    global attack_timer, slash_timer

    if attack_timer > 0:
        return

    attack_timer = 450
    slash_timer = 150
    play("swing")

    dmg, reach = weapon_stats()

    if in_cave:
        for e in cave_enemies[:]:
            er = erect(e)
            dx = er.centerx - player.centerx
            dy = er.centery - player.centery
            dist = math.hypot(dx, dy)

            if dist <= reach + 8:
                e["hp"] -= dmg
                play("hit")
                burst(er.centerx, er.centery, (190, 190, 210), 7, 2.2, 400, 2, 0.05)
                float_text(er.centerx, er.y - 10, "-" + str(dmg), WHITE)

                if dist > 0:
                    push = 6 if e["kind"] == "golem" else 24
                    e["x"] = max(0, min(CAVE_W - e["w"], e["x"] + dx / dist * push))
                    e["y"] = max(0, min(CAVE_H - e["h"], e["y"] + dy / dist * push))

                if e["hp"] <= 0:
                    cave_enemies.remove(e)
                    play("kill")
                    burst(er.centerx, er.centery, (140, 100, 190), 18, 3.0, 700, 3, 0.04)

                    if e["kind"] == "golem":
                        stats["guardian"] += 1
                        gain_xp(70)
                        show_message("Guardian defeated!")
                    else:
                        gain_xp(10)
                        show_message("Bat killed!")

        return

    # hunting rabbits
    for a in animals[:]:
        ar = arect(a)
        if math.hypot(ar.centerx - player.centerx, ar.centery - player.centery) <= reach:
            a["hp"] -= dmg
            play("hit")
            burst(ar.centerx, ar.centery, (240, 235, 225), 6, 2.0, 400, 2, 0.05)

            if a["hp"] <= 0:
                animals.remove(a)
                inventory["food"] += 2
                stats["hunted"] += 1
                gain_xp(8)
                play("kill")
                show_message("Hunted a rabbit! +2 food")

    # fighting zombies
    for z in zombies[:]:
        zr = zrect(z)
        dx = zr.centerx - player.centerx
        dy = zr.centery - player.centery
        dist = math.hypot(dx, dy)

        if dist <= reach:
            z["hp"] -= dmg
            play("hit")
            burst(zr.centerx, zr.centery, (170, 40, 40), 8, 2.5, 450, 2, 0.06)
            float_text(zr.centerx, zr.y - 12, "-" + str(dmg), WHITE)

            # knockback (the boss is too heavy to be pushed far)
            if dist > 0:
                push = 8 if z["kind"] == "boss" else 28
                z["x"] += dx / dist * push
                z["y"] += dy / dist * push
                z["x"], z["y"] = clamp_world(z["x"], z["y"], z["w"], z["h"])

            if z["hp"] <= 0:
                kill_zombie(z)


def craft(key):
    name, cost = RECIPES[key]

    if gear[key]:
        show_message("You already have: " + name.lower())
        return

    if all(inventory[item] >= amount for item, amount in cost.items()):
        for item, amount in cost.items():
            inventory[item] -= amount

        gear[key] = True
        stats["crafted"] += 1
        gain_xp(10)
        play("build")
        burst(table.centerx, table.y, (255, 220, 120), 14, 2.5, 600, 2, 0.03)
        show_message("Crafted: " + name.lower() + "!")
    else:
        need = ", ".join(str(a) + " " + i for i, a in cost.items())
        show_message("Need " + need)


def craft_spear():
    craft("spear")


def build_fire():
    global campfire, campfire_timer

    if in_cave:
        show_message("No fire in the cave")
        return

    if campfire is not None:
        # feed the fire to keep it burning longer
        if inventory["wood"] >= 1:
            inventory["wood"] -= 1
            campfire_timer = min(120000, campfire_timer + 20000)
            show_message("Added fuel +20s")
        else:
            show_message("Need 1 wood for fuel")
    elif inventory["wood"] >= 3:
        inventory["wood"] -= 3
        campfire = player.center
        campfire_timer = campfire_duration
        stats["fires"] += 1
        gain_xp(10)
        burst(campfire[0], campfire[1], ORANGE, 14, 2.5, 600, 3, -0.02)
        show_message("Campfire built!")
    else:
        show_message("Need 3 wood")


# ---------------- SAVE / LOAD GAME ----------------
def snapshot():
    return {
        "px": cave_return[0] if in_cave else player.x, "py": cave_return[1] if in_cave else player.y,
        "health": health, "max_health": max_health, "hunger": hunger, "thirst": thirst,
        "inventory": dict(inventory), "storage": dict(storage), "gear": dict(gear),
        "kills": kills, "day_time": day_time, "is_night": is_night, "day_count": day_count,
        "level": level, "xp": xp, "quest": quest_index, "stats": dict(stats),
        "dog_tamed": dog["tamed"], "dog_x": dog["x"], "dog_y": dog["y"],
        "campfire": list(campfire) if campfire is not None else None,
        "campfire_timer": campfire_timer,
        "tree_timers": list(tree_timers), "rock_timers": list(rock_timers),
        "bush_timers": list(bush_timers), "crate_opened": list(crate_opened), "cave_looted": cave_looted,
    }


def save_game(note=True):
    global saved_game
    saved_game = snapshot()
    write_save_file()

    if note:
        show_message("Game saved!")


def load_game():
    global health, max_health, hunger, thirst, kills, day_time, is_night, day_count
    global level, xp, quest_index, campfire, campfire_timer, night_spawn_timer
    global inventory, storage, gear, stats, tree_timers, rock_timers, cave_looted

    d = saved_game
    reset_game()

    try:
        player.x, player.y = int(d["px"]), int(d["py"])
        health, max_health = d["health"], d["max_health"]
        hunger, thirst = d["hunger"], d["thirst"]

        for key in inventory:
            inventory[key] = int(d["inventory"].get(key, 0))

        for key in storage:
            storage[key] = int(d["storage"].get(key, 0))

        for key in gear:
            gear[key] = bool(d["gear"].get(key, False))

        for key in stats:
            stats[key] = int(d["stats"].get(key, 0))

        kills = d["kills"]
        day_time, is_night, day_count = d["day_time"], d["is_night"], d["day_count"]
        level, xp, quest_index = d["level"], d["xp"], d["quest"]

        dog["tamed"] = d["dog_tamed"]
        dog["x"], dog["y"] = d["dog_x"], d["dog_y"]

        if d["campfire"] is not None:
            campfire = (d["campfire"][0], d["campfire"][1])
            campfire_timer = d["campfire_timer"]

        for i in range(min(len(tree_timers), len(d["tree_timers"]))):
            tree_timers[i] = d["tree_timers"][i]

        for i in range(min(len(rock_timers), len(d["rock_timers"]))):
            rock_timers[i] = d["rock_timers"][i]

        for i in range(min(len(bush_timers), len(d.get("bush_timers", [])))):
            bush_timers[i] = d["bush_timers"][i]

        for i in range(min(len(crate_opened), len(d.get("crate_opened", [])))):
            crate_opened[i] = d["crate_opened"][i]

        cave_looted = d.get("cave_looted", False)

        if is_night:
            animals.clear()
            night_spawn_timer = 0

            for i in range(2 + day_count):
                spawn_zombie()

            if day_count == GOAL_DAYS:
                spawn_zombie("boss")

        show_message("Game loaded - welcome back!")
    except Exception:
        reset_game()


# ---------------- RESET GAME ----------------
def reset_game():
    global shake, lightning, banner_text, banner_timer, walk_anim, walk_moving
    global player, health, max_health, hunger, thirst, facing
    global hunger_timer, starve_timer, regen_timer, zombie_damage_timer
    global day_time, is_night, day_count, night_spawn_timer
    global campfire, campfire_timer
    global inventory_open, chest_open, craft_open, ach_open, game_over, won, paused
    global storage, inventory, zombies, pressed, tree_timers, rock_timers
    global gear, kills, attack_timer, slash_timer, drink_timer
    global message, message_timer
    global animals, animal_timer
    global level, xp, quest_index, stats, ach_banner, ach_timer
    global dog, raining, rain_left, weather_timer, rain_thirst_timer
    global in_cave, cave_looted, bush_timers, crate_opened, cave_hit_timer, in_swamp

    particles.clear()
    float_texts.clear()
    shake = 0
    lightning = 0
    banner_text = ""
    banner_timer = 0
    walk_anim = 0.0
    walk_moving = False

    player = pygame.Rect(START_POS[0], START_POS[1], 32, 42)
    facing = 1
    animals = []
    animal_timer = 0

    health = 100
    max_health = 100
    hunger = 100
    thirst = 100

    hunger_timer = 0
    starve_timer = 0
    regen_timer = 0
    zombie_damage_timer = 0

    gear = {"spear": False, "stone_spear": False, "axe": False,
            "pickaxe": False, "armor": False, "lantern": False}
    kills = 0
    attack_timer = 0
    slash_timer = 0
    drink_timer = 0

    level = 1
    xp = 0
    quest_index = 0
    stats = new_stats()
    ach_banner = ""
    ach_timer = 0

    inventory = {"food": 0, "cooked": 0, "water": 0, "wood": 0, "stone": 0}
    storage = {"food": 0, "water": 0, "wood": 0, "stone": 0}
    tree_timers = [0 for _ in trees]
    rock_timers = [0 for _ in ROCK_RECTS]
    bush_timers = [0 for _ in BUSH_RECTS]
    crate_opened = [False for _ in CRATE_RECTS]
    in_cave = False
    cave_looted = False
    cave_hit_timer = 0
    in_swamp = False
    spawn_cave_enemies()

    day_time = 0
    is_night = False
    day_count = 1
    night_spawn_timer = 0

    campfire = None
    campfire_timer = 0

    raining = False
    rain_left = 0
    weather_timer = random.randint(30000, 60000)
    rain_thirst_timer = 0

    inventory_open = False
    chest_open = False
    craft_open = False
    ach_open = False
    game_over = False
    won = False
    paused = False

    zombies = []
    pressed = {key: False for key in move_buttons}

    message = ""
    message_timer = 0

    dog = new_dog()
    create_items()

    for i in range(8):
        spawn_animal()

    show_message("Collect food, water and wood")


# ---------------- BEST SCORES ----------------
def record_result():
    global saved_game

    best["days"] = max(best["days"], day_count)
    best["kills"] = max(best["kills"], kills)

    if won:
        best["wins"] += 1

    saved_game = None       # a finished game cannot be continued
    write_save_file()


def best_text():
    return (
        "Best: Day " + str(best["days"])
        + " | Kills " + str(best["kills"])
        + " | Wins " + str(best["wins"])
    )


# ---------------- MINI-MAP ----------------
def draw_minimap():
    size = 84
    sc = size / float(WORLD_W)
    mm = pygame.Surface((size, size), pygame.SRCALPHA)
    mm.fill((10, 30, 15, 190))
    pygame.draw.rect(mm, (110, 100, 60), (int(SAND_RECT.x * sc), int(SAND_RECT.y * sc), int(SAND_RECT.w * sc), int(SAND_RECT.h * sc)))
    pygame.draw.rect(mm, (40, 60, 35), (int(SWAMP_RECT.x * sc), int(SWAMP_RECT.y * sc), int(SWAMP_RECT.w * sc), int(SWAMP_RECT.h * sc)))
    pygame.draw.rect(mm, (170, 80, 220), (int(cave_mouth.x * sc), int(cave_mouth.y * sc), 5, 4))

    for p in ponds:
        pygame.draw.rect(mm, (60, 130, 200), (int(p.x * sc), int(p.y * sc), max(3, int(p.w * sc)), max(2, int(p.h * sc))))

    for r in ROCK_RECTS:
        pygame.draw.rect(mm, STONE_GREY, (int(r.x * sc), int(r.y * sc), 2, 2))

    for r in TREE_RECTS:
        pygame.draw.rect(mm, (30, 150, 70), (int(r.x * sc), int(r.y * sc), 2, 2))

    pygame.draw.rect(mm, (150, 100, 55), (int(table.x * sc), int(table.y * sc), 4, 3))
    pygame.draw.rect(mm, YELLOW, (int(chest.x * sc), int(chest.y * sc), 3, 3))

    if campfire is not None:
        pygame.draw.circle(mm, ORANGE, (int(campfire[0] * sc), int(campfire[1] * sc)), 3)

    pygame.draw.circle(mm, CYAN if dog["tamed"] else (230, 170, 90), (int(dog["x"] * sc), int(dog["y"] * sc)), 2)

    for z in zombies:
        pygame.draw.circle(mm, RED, (int(z["x"] * sc), int(z["y"] * sc)), 2)

    pygame.draw.rect(mm, (255, 255, 255), (int(cam_x * sc), int(cam_y * sc), int(VIEW_W * sc), int(VIEW_H * sc)), 1)
    pygame.draw.circle(mm, WHITE, (int(player.centerx * sc), int(player.centery * sc)), 2)
    pygame.draw.rect(mm, WHITE, (0, 0, size, size), 1)

    screen.blit(mm, (WIDTH - size - 6, PLAY_BOTTOM - size - 6))


def draw_panel(rect):
    r = pygame.Rect(rect)
    pygame.draw.rect(screen, (0, 0, 0), r.move(4, 5), border_radius=14)
    pygame.draw.rect(screen, (22, 26, 34), r, border_radius=14)
    pygame.draw.rect(screen, (200, 170, 90), r, 2, border_radius=14)
    pygame.draw.rect(screen, (70, 60, 40), r.inflate(-10, -10), 1, border_radius=10)


# ---------------- INITIAL STATE ----------------
reset_game()


# ---------------- MAIN LOOP ----------------
running = True

while running:
    dt = clock.tick(60)

    playing = started and not game_over and not won and not paused
    panel_open = inventory_open or chest_open or craft_open

    # ---------------- EVENTS ----------------
    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN and playing and not panel_open:
            if event.key == pygame.K_SPACE:
                attack()
            elif event.key == pygame.K_e:
                do_action()
            elif event.key == pygame.K_f:
                build_fire()
            elif event.key == pygame.K_i:
                inventory_open = True
            elif event.key == pygame.K_p:
                paused = True

        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos

            if not started:
                if START_BTN.collidepoint(pos):
                    reset_game()
                    started = True
                    start_music()
                    show_message("Collect food, water and wood")
                elif saved_game is not None and CONTINUE_BTN.collidepoint(pos):
                    load_game()
                    started = True
                    start_music()
                continue

            if game_over or won:
                if END_BTN.collidepoint(pos):
                    reset_game()
                continue

            if paused:
                if ach_open:
                    if ACH_CLOSE.collidepoint(pos):
                        ach_open = False
                elif RESUME_BTN.collidepoint(pos):
                    paused = False
                elif SAVE_BTN.collidepoint(pos):
                    save_game()
                elif ACH_BTN.collidepoint(pos):
                    ach_open = True
                elif RESTART_BTN.collidepoint(pos):
                    reset_game()
                elif SOUND_BTN.collidepoint(pos):
                    sound_on = not sound_on

                    if sound_on:
                        start_music()
                    else:
                        stop_music()
                continue

            if inventory_open:
                if INV_CLOSE.collidepoint(pos):
                    inventory_open = False

                elif INV_FOOD.collidepoint(pos):
                    if inventory["food"] > 0:
                        inventory["food"] -= 1
                        hunger = min(100, hunger + 20)
                        show_message("Raw food eaten")

                elif INV_WATER.collidepoint(pos):
                    if inventory["water"] > 0:
                        inventory["water"] -= 1
                        thirst = min(100, thirst + 30)
                        show_message("Water used")

                elif INV_COOKED.collidepoint(pos):
                    if inventory["cooked"] > 0:
                        inventory["cooked"] -= 1
                        hunger = min(100, hunger + 45)
                        health = min(max_health, health + 5)
                        show_message("Cooked food eaten")

                elif INV_SPEAR.collidepoint(pos):
                    craft_spear()

            elif chest_open:
                if INV_CLOSE.collidepoint(pos):
                    chest_open = False
                else:
                    for label, rect, mode, item in CHEST_BTNS:
                        if rect.collidepoint(pos):
                            if mode == "store":
                                storage[item] += inventory[item]
                                inventory[item] = 0
                            else:
                                inventory[item] += storage[item]
                                storage[item] = 0

            elif craft_open:
                if CRAFT_CLOSE.collidepoint(pos):
                    craft_open = False
                else:
                    for key, rect in CRAFT_BTNS:
                        if rect.collidepoint(pos):
                            craft(key)

            else:
                if inventory_btn.collidepoint(pos):
                    inventory_open = True

                elif pause_btn.collidepoint(pos):
                    paused = True
                    pressed = {key: False for key in pressed}

                elif fire_btn.collidepoint(pos):
                    build_fire()

                elif attack_btn.collidepoint(pos):
                    attack()

                elif action_btn.collidepoint(pos):
                    do_action()

                else:
                    for name, button in move_buttons.items():
                        if button.collidepoint(pos):
                            pressed[name] = True

        if event.type == pygame.MOUSEBUTTONUP:
            pressed = {key: False for key in pressed}

    # ---------------- GAME UPDATE ----------------
    if started and not game_over and not won and not paused:

        keys = pygame.key.get_pressed()

        dx = 0
        dy = 0

        if not panel_open:
            if keys[pygame.K_LEFT] or keys[pygame.K_a] or pressed["left"]:
                dx -= 1

            if keys[pygame.K_RIGHT] or keys[pygame.K_d] or pressed["right"]:
                dx += 1

            if keys[pygame.K_UP] or keys[pygame.K_w] or pressed["up"]:
                dy -= 1

            if keys[pygame.K_DOWN] or keys[pygame.K_s] or pressed["down"]:
                dy += 1

        moving = dx != 0 or dy != 0

        if dx and dy:
            dx *= 0.707
            dy *= 0.707

        if dx > 0:
            facing = 1
        elif dx < 0:
            facing = -1

        # move one axis at a time so solid things (ponds, trunks, rocks...) block the player
        if in_cave:
            blockers = CAVE_ROCKS + [CAVE_CHEST]
            limit_w, limit_h = CAVE_W, CAVE_H
            cur_speed = speed
        else:
            blockers = SOLID_RECTS
            limit_w, limit_h = WORLD_W, WORLD_H
            in_swamp_now = player.colliderect(SWAMP_RECT.inflate(-40, -30))
            cur_speed = 2 if in_swamp_now else speed

            if in_swamp_now and not in_swamp:
                show_message("The swamp slows you down")

            in_swamp = in_swamp_now

        old_x = player.x
        player.x += int(round(dx * cur_speed))
        if any(player.colliderect(b) for b in blockers):
            player.x = old_x

        old_y = player.y
        player.y += int(round(dy * cur_speed))
        if any(player.colliderect(b) for b in blockers):
            player.y = old_y

        player.x = max(0, min(limit_w - 32, player.x))
        player.y = max(0, min(limit_h - 42, player.y))

        # walking animation + dust / splashes under the feet
        walk_moving = moving

        if moving:
            walk_anim += dt * 0.014

            if random.random() < 0.2:
                if in_swamp and not in_cave:
                    dust_color = (70, 100, 60)
                else:
                    dust_color = (150, 125, 85)

                burst(player.centerx, player.bottom - 2, dust_color, 1, 0.8, 350, 2, -0.01)

        # Cooldown timers
        attack_timer = max(0, attack_timer - dt)
        slash_timer = max(0, slash_timer - dt)
        drink_timer = max(0, drink_timer - dt)

        for i in range(len(tree_timers)):
            if tree_timers[i] > 0:
                tree_timers[i] = max(0, tree_timers[i] - dt)

        for i in range(len(rock_timers)):
            if rock_timers[i] > 0:
                rock_timers[i] = max(0, rock_timers[i] - dt)

        for i in range(len(bush_timers)):
            if bush_timers[i] > 0:
                bush_timers[i] = max(0, bush_timers[i] - dt)

        # Rabbits wander around during the day
        if not is_night and not in_cave:
            update_animals(dt)

            if len(animals) < 8:
                animal_timer += dt

                if animal_timer >= 10000:
                    spawn_animal()
                    animal_timer = 0

        # The dog (stray or tamed) / the creatures of the cave
        if in_cave:
            update_cave(dt)
        else:
            update_dog(dt)

        # Weather
        if raining:
            rain_left -= dt
            rain_thirst_timer += dt

            if rain_thirst_timer >= 3500:
                thirst = min(100, thirst + 1)
                rain_thirst_timer = 0

            if lightning <= 0 and random.random() < 0.0012:
                lightning = 260
                shake = max(shake, 120)
                play("thunder")

            if rain_left <= 0:
                raining = False
                weather_timer = random.randint(40000, 80000)
                show_message("The rain stopped")
        else:
            weather_timer -= dt

            if weather_timer <= 0:
                raining = True
                rain_left = random.randint(15000, 28000)
                stats["rain"] += 1
                show_message("It started raining!")

        # Day and night
        day_time += dt

        if not is_night and day_time >= day_duration:
            is_night = True
            day_time = 0
            night_spawn_timer = 0

            animals.clear()

            for i in range(2 + day_count):
                spawn_zombie()

            if day_count == GOAL_DAYS:
                spawn_zombie("boss")
                show_message("BOSS ZOMBIE has arrived!")
                banner_text = "FINAL NIGHT"
                banner_timer = 2600
            else:
                show_message("Night is coming!")
                banner_text = "NIGHT " + str(day_count)
                banner_timer = 2600

        elif is_night and day_time >= night_duration:
            is_night = False
            day_time = 0
            zombies.clear()

            if day_count >= GOAL_DAYS:
                won = True
                record_result()
                play("win")
            else:
                day_count += 1

                for i in range(5):
                    spawn_animal()

                # supply crates and the cave treasure refill every day
                for i in range(len(crate_opened)):
                    crate_opened[i] = False

                cave_looted = False
                spawn_cave_enemies()

                save_game(note=False)
                show_message("Day " + str(day_count) + " begins - game saved")
                banner_text = "DAY " + str(day_count)
                banner_timer = 2600

        # Zombie spawning
        if is_night:
            night_spawn_timer += dt

            spawn_gap = max(4000, 10000 - 1200 * day_count)

            if night_spawn_timer >= spawn_gap:
                if len(zombies) < 4 + day_count:
                    spawn_zombie()

                night_spawn_timer = 0

            if not panel_open and not in_cave:
                update_zombies(dt)

        # Campfire timer (rain makes it burn faster)
        if campfire is not None:
            campfire_timer -= dt * (2 if raining else 1)

            # sparks and smoke
            if random.random() < 0.3:
                particles.append([campfire[0] + random.uniform(-5, 5), campfire[1] - 12,
                                  random.uniform(-0.3, 0.3), random.uniform(-1.4, -0.6),
                                  700, 700, random.choice([ORANGE, YELLOW, (255, 90, 30)]), 2, -0.01])

            if random.random() < 0.08:
                particles.append([campfire[0] + random.uniform(-4, 4), campfire[1] - 18,
                                  random.uniform(-0.2, 0.2), -0.5, 1300, 1300, (110, 110, 118), 4, -0.005])

            if campfire_timer <= 0:
                campfire = None
                campfire_timer = 0
                show_message("Campfire went out")

        # Hunger and thirst (faster while moving)
        hunger_timer += dt
        interval = 3000 if moving else 9000

        if hunger_timer >= interval:
            hunger = max(0, hunger - 1)
            thirst = max(0, thirst - 1)
            hunger_timer = 0

        # Starving hurts
        if hunger <= 0 or thirst <= 0:
            starve_timer += dt

            if starve_timer >= 1500:
                health = max(0, health - 2)
                starve_timer = 0
                show_message("You are starving!")
        else:
            starve_timer = 0

        # Slow healing when well fed (twice as fast next to a campfire)
        if hunger > 50 and thirst > 50 and health < max_health:
            regen_timer += dt

            if regen_timer >= (2000 if near_campfire() else 4000):
                health = min(max_health, health + 1)
                regen_timer = 0

                if near_campfire() and random.random() < 0.5:
                    float_text(player.centerx, player.y - 6, "+1", (150, 240, 150))
        else:
            regen_timer = 0

        # Collect apples
        for apple in (apples[:] if not in_cave else []):
            if player.colliderect(apple):
                add_item("food")
                burst(apple.centerx, apple.centery, (255, 120, 120), 6, 1.8, 400, 2, 0.04)
                apples.remove(apple)
                apples.append(spawn_item(20, apples + water_bottles + wood_items))
                show_message("Food collected")

        # Collect water
        for bottle in (water_bottles[:] if not in_cave else []):
            if player.colliderect(bottle):
                add_item("water")
                burst(bottle.centerx, bottle.centery, (150, 220, 250), 6, 1.8, 400, 2, 0.04)
                water_bottles.remove(bottle)
                water_bottles.append(spawn_item(18, apples + water_bottles + wood_items))
                show_message("Water collected")

        # Collect wood
        for wood in (wood_items[:] if not in_cave else []):
            if player.colliderect(wood):
                add_item("wood")
                burst(wood.centerx, wood.centery, (200, 150, 90), 6, 1.8, 400, 2, 0.04)
                wood_items.remove(wood)
                wood_items.append(spawn_item(20, apples + water_bottles + wood_items))
                show_message("Wood collected")

        # Quests and achievements
        check_progress()

        if ach_timer > 0:
            ach_timer = max(0, ach_timer - dt)

        # effects
        update_fx(dt)
        banner_timer = max(0, banner_timer - dt)
        lightning = max(0, lightning - dt)
        shake = max(0, shake - dt)

        # Game over
        if health <= 0:
            game_over = True
            record_result()
            play("lose")

    # ---------------- CAMERA ----------------
    cur_w, cur_h = (CAVE_W, CAVE_H) if in_cave else (WORLD_W, WORLD_H)
    cam_x = max(0, min(cur_w - VIEW_W, player.centerx - VIEW_W // 2))
    cam_y = max(0, min(cur_h - VIEW_H, player.centery - VIEW_H // 2))
    view_rect = pygame.Rect(cam_x, cam_y, VIEW_W, VIEW_H)

    # ---------------- DRAW WORLD (onto the big world surface, only the visible part) ----------------
    screen = world_surf
    world_surf.set_clip(view_rect)

    if in_cave:
        draw_cave()
    else:
        draw_overworld()

    world_surf.set_clip(None)
    screen = display

    # screen shake when you get hurt
    amp = int(min(4, shake // 60)) if playing else 0
    shake_x = random.randint(-amp, amp) if amp else 0
    shake_y = random.randint(-amp, amp) if amp else 0
    screen.set_clip(pygame.Rect(0, PLAY_TOP, WIDTH, VIEW_H))
    screen.blit(world_surf, (shake_x, PLAY_TOP + shake_y), view_rect)
    screen.set_clip(None)

    # Rain
    if raining and not in_cave:
        screen.blit(rain_tint, (0, PLAY_TOP))

        for drop in rain_drops:
            if playing:
                drop[1] += drop[2]
                drop[0] -= 2

                if drop[1] > VIEW_H or drop[0] < 0:
                    drop[0] = random.randint(0, VIEW_W + 20)
                    drop[1] = random.randint(-20, 0)

            pygame.draw.line(screen, (160, 195, 235),
                             (drop[0], PLAY_TOP + drop[1]), (drop[0] - 3, PLAY_TOP + drop[1] + 10), 1)

    # lightning flash
    if lightning > 0 and not in_cave:
        flash = pygame.Surface((VIEW_W, VIEW_H))
        flash.fill((255, 255, 255))
        flash.set_alpha(int(150 * lightning / 260.0))
        screen.blit(flash, (0, PLAY_TOP))

    # Night overlay (game area only) with light around the player and the campfire
    dark_amt = dark_amount()

    if in_cave:
        shade = cave_darkness.copy()
        light = lantern_light if gear["lantern"] else player_light
        lr = 180 if gear["lantern"] else 120
        shade.blit(
            light,
            (player.centerx - cam_x - lr, player.centery - cam_y - lr),
            special_flags=pygame.BLEND_RGBA_MIN
        )
        screen.blit(shade, (0, PLAY_TOP))

    elif dark_amt > 0.01:
        # smooth dusk (purple-ish) fading into deep night blue
        shade = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        shade.fill((int(70 - 65 * dark_amt), int(30 - 22 * dark_amt), int(60 - 30 * dark_amt), int(145 * dark_amt)))

        if campfire is not None:
            shade.blit(
                fire_light,
                (campfire[0] - cam_x - campfire_radius, campfire[1] - cam_y - campfire_radius),
                special_flags=pygame.BLEND_RGBA_MIN
            )

        light = lantern_light if gear["lantern"] else player_light
        lr = 180 if gear["lantern"] else 120

        shade.blit(
            light,
            (player.centerx - cam_x - lr, player.centery - cam_y - lr),
            special_flags=pygame.BLEND_RGBA_MIN
        )

        screen.blit(shade, (0, PLAY_TOP))

    screen.blit(vignette, (0, PLAY_TOP))

    if not in_cave:
        if dark_amt > 0.5:
            draw_fireflies(dark_amt)

        draw_campfire(cam_x, cam_y)
        draw_minimap()

    # HUD
    screen.blit(hud_bg, (0, 0))

    title_img = big_font.render("ALONE ADVENTURES", True, WHITE)
    screen.blit(big_font.render("ALONE ADVENTURES", True, (10, 40, 22)), title_img.get_rect(center=(WIDTH // 2 + 1, 15)))
    screen.blit(title_img, title_img.get_rect(center=(WIDTH // 2, 14)))

    draw_bar(10, 78, health, RED, "HEALTH", max_health)
    draw_bar(145, 78, hunger, YELLOW, "HUNGER")
    draw_bar(280, 78, thirst, CYAN, "THIRST")

    draw_button(inventory_btn, "INVENTORY")
    draw_button(pause_btn, "PAUSE")

    # Day / night info in the middle of the HUD
    text_center("Day " + str(day_count) + "/" + str(GOAL_DAYS), 40, WHITE, small)
    state_text = "NIGHT" if is_night else "DAY"

    if in_cave:
        state_text = "IN THE CAVE"
    elif raining:
        state_text += " - RAIN"

    text_center(state_text, 56, YELLOW if is_night else WHITE, small)

    # XP bar under the HUD
    pygame.draw.rect(screen, BLACK, (0, 96, WIDTH, 4))
    pygame.draw.rect(screen, (120, 220, 120), (0, 96, int(WIDTH * xp / float(xp_needed())), 4))

    # Quest strip
    screen.blit(strip_surf, (0, PLAY_TOP))

    if quest_index < len(QUESTS):
        quest_text = "Quest: " + QUESTS[quest_index][0]
    else:
        quest_text = "All quests done!"

    text(quest_text, 6, PLAY_TOP + 3, YELLOW, small)
    level_image = small.render("LV " + str(level), True, (150, 240, 150))
    screen.blit(level_image, (WIDTH - level_image.get_width() - 6, PLAY_TOP + 3))

    draw_controls()

    # Right side buttons
    if campfire is not None:
        seconds = max(0, campfire_timer // 1000)
        draw_button(fire_btn, str(seconds) + "s  +FUEL", ORANGE)
    elif inventory["wood"] >= 3:
        draw_button(fire_btn, "BUILD FIRE", ORANGE)
    else:
        draw_button(fire_btn, "FIRE (3 wood)", GREY)

    current_action = get_action()

    if current_action is not None and not panel_open:
        draw_button(action_btn, current_action, PURPLE)

    draw_button(attack_btn, "ATTACK", RED if attack_timer <= 0 else GREY)

    # Inventory panel
    if inventory_open:
        draw_panel((15, 170, 370, 300))

        text("INVENTORY", 40, 195, YELLOW, big_font)

        text("Food: " + str(inventory["food"]), 45, 240)
        text("Water: " + str(inventory["water"]), 225, 240)
        text("Cooked: " + str(inventory["cooked"]), 45, 264)
        text("Wood: " + str(inventory["wood"]), 225, 264)
        text("Stone: " + str(inventory["stone"]), 45, 288)
        text("Level " + str(level) + "  XP " + str(xp) + "/" + str(xp_needed()), 225, 290, (150, 240, 150), small)

        draw_button(INV_FOOD, "EAT RAW FOOD")
        draw_button(INV_WATER, "DRINK WATER")
        draw_button(INV_COOKED, "EAT COOKED")
        draw_button(INV_SPEAR, "CRAFT SPEAR (2 wood)", PURPLE if not gear["spear"] else GREY)
        draw_button(INV_CLOSE, "CLOSE")

        owned = [RECIPES[k][0].lower() for k in CRAFT_ORDER if gear[k]]
        text("Gear: " + (", ".join(owned) if owned else "none yet"), 45, 410, YELLOW, small)
        text("Tip: cook food near a campfire", 45, 430, WHITE, small)
        text("Fish at a pond when you are not thirsty", 45, 448, WHITE, small)

    # Storage panel
    if chest_open:
        draw_panel((15, 170, 370, 340))

        text("STORAGE BOX", 40, 195, YELLOW, big_font)

        text("Food: " + str(storage["food"]), 45, 245)
        text("Water: " + str(storage["water"]), 225, 245)
        text("Wood: " + str(storage["wood"]), 45, 268)
        text("Stone: " + str(storage["stone"]), 225, 268)

        for label, rect, mode, item in CHEST_BTNS:
            draw_button(rect, label)

        draw_button(INV_CLOSE, "CLOSE")

    # Crafting panel
    if craft_open:
        draw_panel((15, 150, 370, 345))

        text("CRAFTING TABLE", 40, 168, YELLOW, big_font)
        text("Wood: " + str(inventory["wood"]) + "     Stone: " + str(inventory["stone"]), 45, 205, WHITE, small)

        for key, rect in CRAFT_BTNS:
            name, cost = RECIPES[key]
            cost_text = " ".join(str(a) + item[0] for item, a in cost.items())
            can = all(inventory[item] >= a for item, a in cost.items())

            if gear[key]:
                color, line2 = GREY, "OWNED"
            elif can:
                color, line2 = PURPLE, cost_text
            else:
                color, line2 = DIM, cost_text

            pygame.draw.rect(screen, tuple(max(0, c - 45) for c in color), rect.move(0, 3), border_radius=7)
            pygame.draw.rect(screen, color, rect, border_radius=7)
            name_img = small.render(name, True, WHITE)
            cost_img = small.render(line2, True, YELLOW if color == PURPLE else (200, 200, 200))
            screen.blit(name_img, name_img.get_rect(center=(rect.centerx, rect.y + 16)))
            screen.blit(cost_img, cost_img.get_rect(center=(rect.centerx, rect.y + 35)))

        text("Axe: more wood  Pickaxe: more stone", 40, 418, WHITE, small)
        text("Armor: -30% damage  Lantern: light", 40, 434, WHITE, small)
        draw_button(CRAFT_CLOSE, "CLOSE")

    # Message
    if message_timer > 0 and not paused and started:
        image = font.render(message, True, YELLOW)
        box = image.get_rect(center=(WIDTH // 2, 146)).inflate(16, 8)
        pygame.draw.rect(screen, (0, 0, 0), box, border_radius=8)
        pygame.draw.rect(screen, (90, 80, 40), box, 1, border_radius=8)
        screen.blit(image, image.get_rect(center=box.center))
        message_timer = max(0, message_timer - dt)

    # Achievement banner
    if ach_timer > 0 and not paused and started:
        image = small.render(ach_banner, True, BLACK)
        box = image.get_rect(center=(WIDTH // 2, 176)).inflate(18, 10)
        pygame.draw.rect(screen, YELLOW, box, border_radius=8)
        screen.blit(image, image.get_rect(center=box.center))

    # Big DAY / NIGHT banner that fades in and out
    if banner_timer > 0 and not paused and started and not game_over and not won:
        a = min(1.0, banner_timer / 600.0, (2600 - banner_timer) / 400.0)
        color = (170, 190, 255) if "NIGHT" in banner_text else (255, 230, 120)
        banner_shadow = title_font.render(banner_text, True, (0, 0, 0))
        banner_img = title_font.render(banner_text, True, color)
        banner_shadow.set_alpha(int(200 * max(0.0, a)))
        banner_img.set_alpha(int(255 * max(0.0, a)))
        screen.blit(banner_shadow, banner_shadow.get_rect(center=(WIDTH // 2 + 3, PLAY_TOP + 123)))
        screen.blit(banner_img, banner_img.get_rect(center=(WIDTH // 2, PLAY_TOP + 120)))

    # Start screen
    if not started:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 205))
        screen.blit(overlay, (0, 0))

        ty = 150 + int(math.sin(pygame.time.get_ticks() / 500.0) * 4)
        title_shadow = title_font.render("ALONE ADVENTURES", True, (120, 60, 10))
        title_main = title_font.render("ALONE ADVENTURES", True, YELLOW)
        screen.blit(title_shadow, title_shadow.get_rect(center=(WIDTH // 2 + 3, ty + 3)))
        screen.blit(title_main, title_main.get_rect(center=(WIDTH // 2, ty)))
        text_center("Survive " + str(GOAL_DAYS) + " days and nights!", 195)

        lines = [
            ("Explore: desert, swamp, meadow and a cave", WHITE),
            ("Collect food, berries, wood, stone, crates", WHITE),
            ("Build a campfire to stay safe at night", WHITE),
            ("Craft gear at the table: spear, axe, armor", WHITE),
            ("Tame the stray dog - it fights for you", WHITE),
            ("Loot the cave - but beware its guardian", WHITE),
            ("Fish at ponds, rest by the fire to heal fast", WHITE),
            ("Level up, finish quests, get achievements", WHITE),
            ("Watch out for storms and zombies", WHITE),
            ("Beware the BOSS on the final night!", RED),
        ]

        for i, (line, color) in enumerate(lines):
            text_center(line, 240 + i * 23, color, small)

        draw_button(START_BTN, "NEW GAME", GREEN)

        if saved_game is not None:
            draw_button(CONTINUE_BTN, "CONTINUE", BLUE)

        text_center(best_text(), 625, YELLOW, small)
        text_center("Achievements: " + str(len(unlocked)) + "/" + str(len(ACHIEVEMENTS)), 650, WHITE, small)

    # Pause screen
    if paused and not game_over and not won:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        if ach_open:
            draw_panel((15, 55, 370, 480))
            text("ACHIEVEMENTS  " + str(len(unlocked)) + "/" + str(len(ACHIEVEMENTS)), 40, 68, YELLOW, big_font)

            for i, (key, title, done) in enumerate(ACHIEVEMENTS):
                got = key in unlocked
                text(("[x] " if got else "[ ] ") + title, 40, 108 + i * 21,
                     (150, 240, 150) if got else (150, 150, 150), font)

            draw_button(ACH_CLOSE, "CLOSE")
        else:
            text("PAUSED", 145, 245, YELLOW, big_font)

            draw_button(RESUME_BTN, "RESUME", GREEN)
            draw_button(SAVE_BTN, "SAVE GAME", BLUE)
            draw_button(ACH_BTN, "ACHIEVEMENTS", PURPLE)
            draw_button(RESTART_BTN, "RESTART", RED)
            draw_button(SOUND_BTN, "SOUND: ON" if sound_on else "SOUND: OFF", BLUE)

    # Game over screen
    if game_over:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))

        text_center("GAME OVER", 270, RED, big_font)
        text_center("Survival ended on day " + str(day_count), 320)
        text_center("Zombies killed: " + str(kills) + "   Level: " + str(level), 355)
        text_center(best_text(), 385, YELLOW, small)

        draw_button(END_BTN, "RESTART", GREEN)

    # Win screen
    if won:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))

        text_center("YOU SURVIVED!", 270, YELLOW, big_font)
        text_center("You lasted " + str(GOAL_DAYS) + " days and nights", 320)
        text_center("Zombies killed: " + str(kills) + "   Level: " + str(level), 355)
        text_center(best_text(), 385, YELLOW, small)

        draw_button(END_BTN, "PLAY AGAIN", GREEN)

    pygame.display.update()

pygame.quit()
sys.exit()

