"""
Mahjong_Game.py  —  STM32 Mahjong  (Pygame edition, v5.0)
══════════════════════════════════════════════════════════════════════════════
File structure expected alongside this script:
  PC/
    Mahjong_Game.py          ← this file
    handling.py              ← UARTHandler
    assets/
      tiles/
        tile_bamboo_1..6.png     (597×1037 native)
        tile_dots_1..4.png
        tile_dragon.png
        tile_flower_1..4.png
      UI/
        scroll_player.png        (1008×370 native)
        scroll_port.png
        btn_play.png
        btn_exit.png             (689×374 native)
        btn_reset.png
        btn_shuffle.png
        btn_hint.png
        btn_giveup.png
      backgrounds/
        bg_menu.png
        bg_game.png
        bg_win.png
        bg_lose.png

Asset scaling (proportional, pygame.transform.smoothscale):
  Tiles          597×1037  → H=150, W=86
  Action btns    689×374   → W=140, H=76
  Scrolls/play   1008×370  → W=280, H=103
  Backgrounds    any       → exactly 1280×720

Pyramid geometry (translated 1-to-1 from command_list.c):
  Square  (layout_id=0)
    Layer 0: 5×5  idx  0-24
    Layer 1: 4×4  idx 25-40  (offset +0.5 tile col/row)
    Layer 2: 3×3  idx 41-49  (offset +1.0 tile col/row)

  Triangle (layout_id=1)
    Layer 0: 7 rows, row R has R+1 tiles, base=0  → idx 0-27
    Layer 1: 5 rows, row R has R+1 tiles, base=28 → idx 28-42
    Layer 2: 3 rows, row R has R+1 tiles, base=43 → idx 43-48
    Layer 3: 1 tile,                      base=49 → idx 49

    idx = base + R*(R+1)//2 + C   (matches C get_index exactly)
    Each row is horizontally centred on screen-centre (BOARD_CX).
    Vertical step = ROW_STEP = 128 px (compressed to fit 920-px board area).
    Layer offset = −6 px on both X and Y per layer above 0.
"""

import os, sys, time, struct, threading, queue
import pygame
from pygame.locals import *
from UART_handler import UARTHandler

# ══════════════════════════════════════════════════════ PROTOCOL CONSTANTS ════
CMD_START       = 0x01
CMD_RESET       = 0x02
CMD_SHUFFLE     = 0x03
CMD_SELECT      = 0x04
CMD_MATCH       = 0x05
CMD_GIVE_UP     = 0x07
CMD_HINT        = 0x08
CMD_SET_NAME    = 0x09
CMD_GET_TIME    = 0x0B
CMD_GET_LEADERS = 0x0C

WIRE_BOARD  = 52    # bytes on the wire for CMD_START / CMD_SHUFFLE / CMD_GET_TIME
TILE_COUNT  = 50    # board_state[] size

# ══════════════════════════════════════════════════════ SCREEN LAYOUT ═════════
SW, SH = 1024, 576
FPS    = 60

# ── UI bars: compact heights to maximise board area ───────────────────────────
INFO_H    = 40
TOOLBAR_H = 76

# ── Board geometry: perfectly centred between the two bars ────────────────────
BOARD_TOP = INFO_H                     
BOARD_BOT = SH - TOOLBAR_H             
BOARD_H   = BOARD_BOT - BOARD_TOP      
BOARD_CX  = SW // 2                    
BOARD_CY  = BOARD_TOP + BOARD_H // 2   

# ══════════════════════════════════════════════════════ ASSET DIMENSIONS ══════
# Square layout tile render size.  TILE_STEP_Y=80 keeps all 5 rows inside
# BOARD_H without squashing (bottom of base layer = 495 px, BOARD_BOT = 500).
TILE_W      = 55    # render width  (square layout)
TILE_H      = 85   # render height (square layout)
TILE_STEP_X = 55    # horizontal grid step = TILE_W (no gap)
TILE_STEP_Y = 84    # vertical   grid step — Fix 2: tiles clearly visible

# Triangle layout uses smaller tiles so the full 7-row pyramid fits on screen.
# Math: bottom_edge = BOARD_CY + 4*TH = 270 + 4*57 = 498 ≤ BOARD_BOT=500 ✓
# (Tile ratio 758×1051 preserved: round(758/1051*57) = 41)
TRI_TILE_W = 41
TRI_TILE_H = 57

BTN_H = TOOLBAR_H - 20                 # 56
BTN_W = round(689 / 374 * BTN_H)       # ≈ 103

SCROLL_W = round(SW * 0.215)           # 220
SCROLL_H = round(370 / 1008 * SCROLL_W)  # ≈ 81

# Layout-selection icon size (native 310×394)
LAYOUT_ICON_W = 90
LAYOUT_ICON_H = round(394 / 310 * LAYOUT_ICON_W)   # ≈ 114

# HUD assets
HUD_ICON_SZ   = INFO_H - 8     # 32 px — sandclock fits inside top bar
RESET_ICON_SZ = 50              # reset.png target size

# ══════════════════════════════════════════════════════ PYRAMID GEOMETRY ══════
LAYER_DX = -5   # px shift left  per layer above 0
LAYER_DY = -5   # px shift up    per layer above 0

# ── Square pyramid ─────────────────────────────────────────────────────────────
# Origin: top-left of 5×5 base layer, centred on (BOARD_CX, BOARD_CY).
# Uses TILE_STEP_X/Y for grid spacing; TILE_W/H for the rendered rectangle.
SQ_OX = (BOARD_CX - (5 * TILE_STEP_X) // 2) + 20
SQ_OY = (BOARD_CY - (5 * TILE_STEP_Y) // 2)  + 20

SQ_LAYER_SPECS = [
    (5, 5, 0.0, 0.0,  0),
    (4, 4, 0.5, 0.5, 25),
    (3, 3, 1.0, 1.0, 41),
]

# ── Triangle pyramid ───────────────────────────────────────────────────────────
# Uses TRI_TILE_W/H so the pyramid fits within BOARD_H.
# Formula mirrors _hitboxes_tri exactly (unchanged):
#   py = TRI_OY + (L + R) * TRI_TILE_H
# TRI_H = 6 * TRI_TILE_H;  bottom = 270 + 4*57 = 498 ≤ 500 ✓
TRI_H  = (7 * TRI_TILE_H)
TRI_OY = (BOARD_TOP + (BOARD_H - TRI_H) // 2) - 20

TRI_LAYERS = [
    (7,  0),   # layer 0: rows 0-6, idx 0-27
    (5, 28),   # layer 1: rows 0-4, idx 28-42
    (3, 43),   # layer 2: rows 0-2, idx 43-48
    (1, 49),   # layer 3: row  0,   idx 49
]

# ══════════════════════════════════════════════════════ TOOLBAR POSITIONS ═════
_BTN_KEYS    = ["exit", "reset", "shuffle", "hint", "giveup"]
_BTN_SPACING = (SW - len(_BTN_KEYS) * BTN_W) // (len(_BTN_KEYS) + 1)
_BTN_Y       = BOARD_BOT + (TOOLBAR_H - BTN_H) // 2   

def _btn_rect(i: int) -> pygame.Rect:
    bx = _BTN_SPACING * (i + 1) + i * BTN_W
    return pygame.Rect(bx, _BTN_Y, BTN_W, BTN_H)

# ══════════════════════════════════════════════════════ COLOURS ═══════════════
C_DARK   = ( 10,  12,  20)
C_PANEL  = ( 28,  36,  54)
C_TEXT   = (220, 228, 245)
C_GREY   = (100, 115, 135)
C_WHITE  = (245, 248, 255)
C_ACCENT = ( 72, 199, 142)
C_RED    = (220,  50,  50)
C_BLUE   = ( 66, 165, 245)
C_YELLOW = (255, 213,  79)
C_GOLD   = (255, 193,   7)
C_SEL    = (  0, 230, 255)
C_ERR    = (230,  50,  50)
C_HNT    = (255, 225,   0)
C_WOOD      = (200, 200, 00)       # warm parchment — text & accents
C_PLATE     = ( 40,  30,  20)       # deep brown — HUD plate fill
C_SEL_FRAME = (255, 230, 150)       # bright parchment — layout selection border

TILE_GROUPS = {
    0: ("Bam", ( 80, 175,  90)),
    1: ("Chr", (220,  70,  70)),
    2: ("Cir", ( 66, 165, 245)),
    3: ("Wnd", (170, 170, 170)),
    4: ("Dra", (255, 220,  50)),
    5: ("Flw", (180,  80, 210)),
    6: ("Ssn", (255, 160,  40)),
}

# ══════════════════════════════════════════════════════ FILE PATHS ════════════
_HERE  = os.path.dirname(os.path.abspath(__file__))
_ASSET = os.path.join(_HERE, "assets")
_TILES = os.path.join(_ASSET, "tiles")
_UI    = os.path.join(_ASSET, "UI")
_BG    = os.path.join(_ASSET, "backgrounds")


# ══════════════════════════════════════════════════════ LOGGING ═══════════════
def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ══════════════════════════════════════════════════════ ASSET CACHE ═══════════
class Assets:
    def __init__(self):
        self._cache: dict = {}

    def _load(self, path: str, size: tuple) -> pygame.Surface:
        key = (path, size)
        if key in self._cache:
            return self._cache[key]
        try:
            raw = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(raw, size)
        except Exception:
            w, h = size
            img = pygame.Surface((w, h), pygame.SRCALPHA)
            img.fill((160, 30, 90, 220))
            fnt = pygame.font.SysFont("", 13)
            lbl = fnt.render(os.path.basename(path), True, (255, 255, 255))
            img.blit(lbl, (4, h // 2 - 6))
        self._cache[key] = img
        return img

    def bg(self, name: str) -> pygame.Surface:
        return self._load(os.path.join(_BG, name), (SW, SH))

    def ui(self, name: str, size: tuple) -> pygame.Surface:
        return self._load(os.path.join(_UI, name), size)

    def tile(self, raw_byte: int, tw: int = TILE_W, th: int = TILE_H):
        if not raw_byte:
            return None
        g = (raw_byte >> 5) & 0x07
        v =  raw_byte & 0x1F
        if   g == 0 and 1 <= v <= 6: fname = f"tile_bamboo_{v}.png"
        elif g == 2 and 1 <= v <= 4: fname = f"tile_dots_{v}.png"
        elif g == 4 and v == 1:      fname = "tile_dragon.png"
        elif g == 5 and 1 <= v <= 4: fname = f"tile_flower_{v}.png"
        else:
            return None
        try:
            return self._load(os.path.join(_TILES, fname), (tw, th))
        except Exception:
            return None


# ══════════════════════════════════════════════════════ FONT HELPERS ══════════

def _mk_fonts() -> dict:
    # Отримуємо шлях до папки зі скриптом, щоб шлях до assets завжди був правильним
    base_dir = os.path.dirname(__file__)
    fpath = os.path.join(base_dir, "assets", "fonts", "japanese.ttf")

    def _f(sz, bold=False):
        # Перевіряємо, чи фізично існує файл за вказаним шляхом
        if os.path.exists(fpath):
            try:
                return pygame.font.Font(fpath, sz)
            except Exception as e:
                print(f"DEBUG: Font file found but error loading: {e}")
        else:
            print(f"DEBUG: Font file NOT found at {fpath}")
        
        # Якщо файлу немає або помилка — повертаємо системний Arial
        return pygame.font.SysFont("arial", sz, bold=bold)

    return {
        "title" : _f(58, True),
        "head"  : _f(32, True),
        "body"  : _f(24),
        "small" : _f(20),
        "tiny"  : _f(15),
        "mono"  : _f(20), 
        "tlbl"  : _f(13),
        "tv"    : _f(18, True),
    }

def _blit_c(surf, txt, font, color, cx, cy):
    img = _sr(font, str(txt), color)
    surf.blit(img, img.get_rect(center=(cx, cy)))

def _blit_a(surf, txt, font, color, x, y, anchor="topleft"):
    img = _sr(font, str(txt), color)
    r = img.get_rect()
    setattr(r, anchor, (x, y))
    surf.blit(img, r)

def _sr(font, txt, color):
    # Додаємо перевірку на порожній текст, щоб гра не падала
    if not txt: txt = ""
    try:
        return font.render(str(txt), True, color)
    except Exception:
        safe = "".join(c if ord(c) < 256 else "?" for c in str(txt))
        return font.render(safe, True, color)

def _rrect(surf, color, rect, r=10, bw=0, bc=None):
    if bw and bc:
        pygame.draw.rect(surf, bc, rect, bw, border_radius=r)
    pygame.draw.rect(surf, color, rect, border_radius=r)

# ══════════════════════════════════════════════════════ WIDGETS ═══════════════
class InputBox:
    def __init__(self, rect, font, init="Player1", maxlen=10):
        self.rect   = pygame.Rect(rect)
        self.font   = font
        self.text   = init
        self.maxlen = maxlen
        self.active = False
        self._blink = 0.0

    def handle_event(self, ev):
        if ev.type == MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(ev.pos)
        if ev.type == KEYDOWN and self.active:
            if ev.key == K_BACKSPACE:
                self.text = self.text[:-1]
            elif ev.key not in (K_RETURN, K_TAB, K_ESCAPE):
                if len(self.text) < self.maxlen and ev.unicode.isprintable():
                    self.text += ev.unicode

    def update(self, dt):
        if self.active:
            self._blink = (self._blink + dt) % 1.2

    def draw(self, surf):
        bc = C_DARK if self.active else C_DARK
        img = _sr(self.font, self.text, C_DARK)
        surf.blit(img, (self.rect.x + 10, self.rect.centery - img.get_height() // 2))
        if self.active and self._blink < 0.6:
            cx = self.rect.x + 10 + img.get_width() + 2
            pygame.draw.line(surf, C_WOOD,
                             (cx, self.rect.centery - 10),
                             (cx, self.rect.centery + 10), 2)


class Dropdown:
    def __init__(self, x, y, width, height, options, font, default_index=0):
        self.rect = pygame.Rect(x, y, width, height)
        self.options = options
        self.selected_index = default_index if options else -1
        self.font = font
        self.is_open = False

        self.color_base = (230, 230, 230)
        self.color_hover = (210, 210, 210)
        self.color_list_bg = (245, 245, 245)
        self.color_item_hover = (180, 210, 250) 
        self.color_text = (30, 30, 30)
        self.color_border = (120, 120, 120)

        self.item_height = height
        self._calculate_expanded_rect()

    def _calculate_expanded_rect(self):
        max_height = min(self.item_height * len(self.options), 200)  # Limit to 200px max
        self.expanded_rect = pygame.Rect(
            self.rect.x, 
            self.rect.bottom, 
            self.rect.width, 
            max_height
        )

    def update_options(self, new_options):
        self.options = new_options
        self.selected_index = 0 if new_options else -1
        self._calculate_expanded_rect()
        if not self.options:
            self.is_open = False

    def get_value(self):
        if self.options and 0 <= self.selected_index < len(self.options):
            return self.options[self.selected_index]
        return ""

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_open:
                # 1. Did they click inside the expanded list?
                if self.expanded_rect.collidepoint(event.pos):
                    relative_y = event.pos[1] - self.expanded_rect.y
                    clicked_idx = int(relative_y / self.item_height)
                    
                    if 0 <= clicked_idx < len(self.options):
                        self.selected_index = clicked_idx
                        
                    self.is_open = False
                    return True # Event consumed
                
                # 2. Did they click the base box to toggle it closed?
                elif self.rect.collidepoint(event.pos):
                    self.is_open = False
                    return True
                
                # 3. Did they click outside? Close and consume click to prevent accidental triggers!
                else:
                    self.is_open = False
                    return True 

            else:
                # Menu is closed; did they click the base box to open it?
                if self.rect.collidepoint(event.pos) and self.options:
                    self.is_open = True
                    return True

        return False

    @property
    def selected(self):
        return self.get_value()

    def set_options(self, new_options):
        self.update_options(new_options)

    def draw(self, surface):
        """PASS 1: Draws only the main button"""
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = self.rect.collidepoint(mouse_pos)

        bg_color = self.color_hover if (is_hovered and not self.is_open) else self.color_base

        text_surf = self.font.render(self.get_value(), True, self.color_text)
        text_rect = text_surf.get_rect(midleft=(self.rect.x + 10, self.rect.centery))
        surface.blit(text_surf, text_rect)

# 1. Визначаємо символ стрілки
        arrow_char = "▲" if self.is_open else "▼"
        
        # 2. Створюємо системний шрифт (швидко, без import os)
        # Він точно підтримує Юнікод-стрілки
        sys_f = pygame.font.SysFont("arial", 18) 
        
        # 3. Рендеримо стрілку системним шрифтом, а колір беремо наш "дерев'яний"
        arrow_surf = sys_f.render(arrow_char, True, self.color_text)
        
        # 4. Розміщуємо та малюємо
        arrow_rect = arrow_surf.get_rect(midright=(self.rect.right - 10, self.rect.centery))
        surface.blit(arrow_surf, arrow_rect)

    def draw_overlay(self, surface):
        """PASS 2: Draws the expanded list on top of everything else"""
        if not self.is_open or not self.options:
            return

        mouse_pos = pygame.mouse.get_pos()

        pygame.draw.rect(surface, self.color_list_bg, self.expanded_rect)
        pygame.draw.rect(surface, self.color_border, self.expanded_rect, 2)

        for i, option in enumerate(self.options):
            item_rect = pygame.Rect(
                self.expanded_rect.x, 
                self.expanded_rect.y + (i * self.item_height), 
                self.rect.width, 
                self.item_height
            )

            if item_rect.collidepoint(mouse_pos):
                pygame.draw.rect(surface, self.color_item_hover, item_rect)

            opt_surf = self.font.render(option, True, self.color_text)
            opt_rect = opt_surf.get_rect(midleft=(item_rect.x + 10, item_rect.centery))
            surface.blit(opt_surf, opt_rect)


class Toast:
    def __init__(self):
        self._msg = ""
        self._t   = 0.0
        self._dur = 2.5
        self._c   = C_WOOD

    def show(self, msg, color=None, dur=2.5):
        self._msg = msg
        self._t   = dur
        self._dur = dur
        self._c   = color or C_WOOD

    def update(self, dt):
        self._t = max(0.0, self._t - dt)

    def draw(self, surf, font):
        if self._t <= 0:
            return
        alpha = min(255, int(255 * min(1.0, self._t / self._dur) * 2))
        img   = _sr(font, self._msg, C_WOOD)
        pad   = 18
        tw, th = img.get_size()
        ox = SW // 2 - (tw + pad * 2) // 2
        oy = SH - 125
        s  = pygame.Surface((tw + pad * 2, th + pad), pygame.SRCALPHA)
        s.fill((*self._c[:3], min(alpha, 200)))
        surf.blit(s, (ox, oy))
        surf.blit(img, (ox + pad, oy + pad // 2))


# ══════════════════════════════════════════════════════ TILE RENDERER ═════════
def _draw_tile(surf, ax: Assets, px, py, raw, state, fonts, glow,
               tw: int = TILE_W, th: int = TILE_H):
    if not raw:
        return
    img = ax.tile(raw, tw, th)
    if img is not None:
        surf.blit(img, (px, py))
    else:
        g, v    = (raw >> 5) & 0x07, raw & 0x1F
        lbl, fc = TILE_GROUPS.get(g, ("?", (200, 200, 200)))
        pygame.draw.rect(surf, C_DARK,      (px+5, py+5, tw, th),        border_radius=6)
        pygame.draw.rect(surf, (245,248,255),(px,   py,   tw, th),        border_radius=6)
        pygame.draw.rect(surf, fc,           (px+6, py+6, tw-12, th-12), border_radius=5)
        _blit_c(surf, str(v), fonts["tv"],   (30, 30, 30), px+tw//2, py+th//2-8)
        _blit_c(surf, lbl[:3], fonts["tlbl"], (60, 60, 60), px+tw//2, py+th-14)

    if state != "normal":
        gc = {"selected": C_SEL, "error": C_ERR, "hint": C_HNT}[state]
        fr = pygame.Rect(px, py, tw, th)
        halo = pygame.Surface((tw+14, th+14), pygame.SRCALPHA)
        pygame.draw.rect(halo, (*gc, 45), halo.get_rect(), border_radius=9)
        glow.blit(halo, (px-7, py-7))
        pygame.draw.rect(surf, gc, fr, 3, border_radius=6)


# ══════════════════════════════════════════════════════ PYGAME MODALS ═════════
def modal_ask_retry(screen, fonts, msg: str) -> bool:
    W2, H2   = 580, 230
    rx, ry   = SW//2 - W2//2, SH//2 - H2//2
    retry_r  = pygame.Rect(rx + 70,        ry + H2 - 82, 190, 54)
    cancel_r = pygame.Rect(rx + W2 - 260,  ry + H2 - 82, 190, 54)
    overlay  = pygame.Surface((SW, SH), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    clk      = pygame.time.Clock()
    while True:
        for ev in pygame.event.get():
            if ev.type == QUIT:                                return False
            if ev.type == MOUSEBUTTONDOWN and ev.button == 1:
                if retry_r.collidepoint(ev.pos):               return True
                if cancel_r.collidepoint(ev.pos):              return False
            if ev.type == KEYDOWN:
                if ev.key in (K_RETURN, K_r):                  return True
                if ev.key == K_ESCAPE:                         return False
        screen.blit(overlay, (0, 0))
        _rrect(screen, C_PANEL,  (rx, ry, W2, H2), r=18, bw=2, bc=C_RED)
        _blit_c(screen, "Connection Lost",              fonts["head"],  C_RED,   SW//2, ry+42)
        _blit_c(screen, msg,                            fonts["small"], C_TEXT,  SW//2, ry+98)
        _blit_c(screen, "Enter / R = Retry    Esc = Cancel",
                fonts["tiny"], C_GREY, SW//2, ry+144)
        _rrect(screen, (40, 155, 80),  retry_r,  r=10)
        _rrect(screen, (155, 40,  40), cancel_r, r=10)
        _blit_c(screen, "Retry",  fonts["body"], C_WHITE, retry_r.centerx,  retry_r.centery)
        _blit_c(screen, "Cancel", fonts["body"], C_WHITE, cancel_r.centerx, cancel_r.centery)
        pygame.display.flip()
        clk.tick(30)


def modal_info(screen, fonts, title: str, msg: str, color=None):
    color  = color or C_WOOD
    W2, H2 = 520, 200
    rx, ry = SW//2 - W2//2, SH//2 - H2//2
    ok_r   = pygame.Rect(SW//2 - 95, ry + H2 - 74, 190, 52)
    overlay = pygame.Surface((SW, SH), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    clk     = pygame.time.Clock()
    while True:
        for ev in pygame.event.get():
            if ev.type == QUIT:                              return
            if ev.type == MOUSEBUTTONDOWN and ev.button == 1:
                if ok_r.collidepoint(ev.pos):                return
            if ev.type == KEYDOWN:
                if ev.key in (K_RETURN, K_ESCAPE, K_SPACE): return
        screen.blit(overlay, (0, 0))
        _rrect(screen, C_PANEL, (rx, ry, W2, H2), r=18, bw=2, bc=color)
        _blit_c(screen, title, fonts["head"],  color,  SW//2, ry+42)
        _blit_c(screen, msg,   fonts["body"],  C_TEXT, SW//2, ry+100)
        _rrect(screen, C_WOOD, ok_r, r=10)
        _blit_c(screen, "OK", fonts["body"], C_WHITE, ok_r.centerx, ok_r.centery)
        pygame.display.flip()
        clk.tick(30)


# ══════════════════════════════════════════════════════ MENU SCREEN ═══════════
class MenuScreen:
    def __init__(self, screen, ax: Assets, fonts: dict, uart: UARTHandler):
        self.screen = screen
        self.ax     = ax
        self.fonts  = fonts
        self.uart   = uart
        self._q     = queue.Queue()
        self._busy  = False
        self.status = ""

        # Fix 3: layout selected via icon buttons (0 = Square, 1 = Triangle)
        self.layout_id = 0

        self._bg        = ax.bg("bg_menu.png")
        self._scr_name  = ax.ui("scroll_player.png", (SCROLL_W, SCROLL_H))
        self._scr_port  = ax.ui("scroll_port.png",   (SCROLL_W, SCROLL_H))
        self._btn_play  = ax.ui("btn_play.png",       (SCROLL_W, SCROLL_H))

        # Layout selection icons (native 310×394)
        _isz = (LAYOUT_ICON_W, LAYOUT_ICON_H)
        self._img_square   = ax.ui("square.png",   _isz)
        self._img_triangle = ax.ui("triangle.png", _isz)

        cx = SW // 2

        WIDGET_TOP = 20
        WIDGET_BOT = 576
        N_ITEMS    = 4

        total_h = N_ITEMS * SCROLL_H
        avail   = WIDGET_BOT - WIDGET_TOP - total_h
        gap     = max(4, avail // (N_ITEMS + 1))

        def _row_y(n):
            return WIDGET_TOP + gap * (n + 1) + SCROLL_H * n

        sx = cx - SCROLL_W // 2
        self._r_scr_name = pygame.Rect(sx, _row_y(0), SCROLL_W, SCROLL_H)
        self._r_scr_port = pygame.Rect(sx, _row_y(1), SCROLL_W, SCROLL_H)
        self._r_scr_lay  = pygame.Rect(sx, _row_y(2), SCROLL_W, SCROLL_H)
        self._r_btn_play = pygame.Rect(sx, _row_y(3), SCROLL_W, SCROLL_H)

        # Two icons side-by-side, centred in the layout row
        _igap   = 20
        _itot_w = 2 * LAYOUT_ICON_W + _igap
        _iy     = self._r_scr_lay.centery - LAYOUT_ICON_H // 2
        self._r_icon_sq  = pygame.Rect(cx - _itot_w // 2,
                                       _iy, LAYOUT_ICON_W, LAYOUT_ICON_H)
        self._r_icon_tri = pygame.Rect(self._r_icon_sq.right + _igap,
                                       _iy, LAYOUT_ICON_W, LAYOUT_ICON_H)

        box_w    = min(240, SCROLL_W - 20)
        widget_h = 36

        self.name_box = InputBox(
            (cx - box_w // 2, self._r_scr_name.centery - widget_h // 2, box_w, widget_h),
            fonts["body"], init="Player1")

        self.dd_port = Dropdown(
            cx - box_w // 2, self._r_scr_port.centery - widget_h // 2, box_w, widget_h,
            [], self.fonts["body"]
        )

        self._r_refresh = pygame.Rect(
            self._r_scr_port.right + 8,
            self._r_scr_port.centery - 18, 40, 36)

        self._do_refresh()

    def _do_refresh(self):
        ports = UARTHandler.list_available_ports()
        self.dd_port.set_options(ports if ports else ["No ports found"])

    # ── events ────────────────────────────────────────────────────────────────
    def handle_event(self, ev):
        self.name_box.handle_event(ev)

        if self.dd_port.handle_event(ev):
            return

        if ev.type == MOUSEBUTTONDOWN and ev.button == 1:
            if self._r_icon_sq.collidepoint(ev.pos):
                self.layout_id = 0; return
            if self._r_icon_tri.collidepoint(ev.pos):
                self.layout_id = 1; return
            if self._r_refresh.collidepoint(ev.pos):
                self._do_refresh()
            elif self._r_btn_play.collidepoint(ev.pos) and not self._busy:
                self._connect()

    # ── connect ───────────────────────────────────────────────────────────────
    def _connect(self):
        name   = self.name_box.text.strip()
        port   = self.dd_port.selected
        layout = self.layout_id

        if not name:
            self.status = "! Enter a player name."
            return
        if not port or port == "No ports found":
            self.status = "! Select a COM port."
            return

        self._busy  = True
        self.status = f"Connecting to {port}…"

        def _worker():
            self.uart.port_name = port
            if not self.uart.open_port():
                self._q.put({"ok": False, "msg": "Could not open port."})
                return
            self.uart.dtr_reset()
            log("Menu: DTR pulsed — waiting 2 s for boot")
            time.sleep(2.0)
            self.uart.reset_buffer()
            if self.uart.send_name_packet(CMD_SET_NAME, name):
                resp = self.uart.read_packet_strictly(3, timeout_sec=1.5)
                if resp and resp[0] == CMD_SET_NAME and resp[1] == 0x00:
                    log(f"Menu: name '{name}' ACK")
                else:
                    log("Menu: name ACK missing (continuing)")
            log("Menu: 500 ms post-name settle")
            time.sleep(0.5)
            if hasattr(self.uart, "clear_intentional_dtr"):
                self.uart.clear_intentional_dtr()
            self._q.put({"ok": True, "name": name, "layout": layout})

        threading.Thread(target=_worker, daemon=True).start()

    # ── update ────────────────────────────────────────────────────────────────
    def update(self, dt):
        self.name_box.update(dt)
        try:
            msg = self._q.get_nowait()
            self._busy = False
            if msg["ok"]:
                return {"action": "goto_game",
                        "name":   msg["name"],
                        "layout": msg["layout"]}
            else:
                self.status = f"ERR {msg.get('msg', '')}"
        except queue.Empty:
            pass
        return None

    # ── draw ──────────────────────────────────────────────────────────────────
    def draw(self):
        cx = SW // 2

        # 1. Background
        self.screen.blit(self._bg, (0, 0))

        # 2. Name row
        self.screen.blit(self._scr_name, self._r_scr_name.topleft)
        self.name_box.draw(self.screen)

        # 3. Port row
        self.screen.blit(self._scr_port, self._r_scr_port.topleft)
        self.dd_port.draw(self.screen)
        
        # Explicitly request fonts known to support the ↺ (U+21BA) Unicode glyph
        _fnt_ref = pygame.font.SysFont("segoeuisymbol, segoeui, dejavusans, arial", 24, bold=True)
        _blit_c(self.screen, "↺", _fnt_ref, C_WOOD,
                self._r_refresh.centerx, self._r_refresh.centery)

        # 4. Layout row — icon buttons replacing the dropdown
        _lay_bg = pygame.Surface((SCROLL_W, SCROLL_H), pygame.SRCALPHA)
        _lay_bg.fill((*C_PLATE, 70))
        self.screen.blit(_lay_bg, self._r_scr_lay.topleft)

        self.screen.blit(self._img_square,   self._r_icon_sq.topleft)
        self.screen.blit(self._img_triangle, self._r_icon_tri.topleft)

        _sel_r = self._r_icon_sq if self.layout_id == 0 else self._r_icon_tri

        glow_pad = 8
        glow_rect = _sel_r.inflate(glow_pad, glow_pad)

        glow = pygame.Surface((glow_rect.w, glow_rect.h), pygame.SRCALPHA)

        # layered soft glow
        pygame.draw.rect(glow, (*C_SEL_FRAME, 40), glow.get_rect(), border_radius=1)


        self.screen.blit(glow, glow_rect.topleft)

        # Fix 3: Arial for icon labels — guaranteed legible
        _fnt_lbl = pygame.font.SysFont("japanese.ttf", 20)
        for _lbl, _ir in (("Square", self._r_icon_sq), ("Triangle", self._r_icon_tri)):
            _active = (_lbl == "Square") == (self.layout_id == 0)
            _col = C_SEL_FRAME if _active else C_GREY
            _limg = _fnt_lbl.render(_lbl, True, _col)
            self.screen.blit(_limg, _limg.get_rect(centerx=_ir.centerx,
                                                    top=_ir.bottom + 4))

        # 5. Play button
        self.screen.blit(self._btn_play, self._r_btn_play.topleft)
        _blit_c(self.screen, "", self.fonts["small"], C_WHITE,
                cx, self._r_btn_play.centery)

        # 6. Status
        status_y = min(self._r_btn_play.bottom + 10, SH - 36)
        if self.status:
            _sc = C_WOOD  if "Connecting" in self.status else \
                  C_RED   if "ERR"        in self.status else C_YELLOW
            _blit_c(self.screen, self.status, self.fonts["small"], _sc, cx, status_y)

        if self._busy:
            dots = "." * (int(time.time() * 2) % 4)
            _blit_c(self.screen, f"Connecting{dots}",
                    self.fonts["body"], C_WOOD, cx, status_y + 26)

        # 7. Port dropdown overlay (always on top)
        self.dd_port.draw_overlay(self.screen)


# ══════════════════════════════════════════════════════ GAME SCREEN ═══════════
class GameScreen:
    def __init__(self, screen, ax: Assets, fonts: dict, uart: UARTHandler):
        self.screen = screen
        self.ax     = ax
        self.fonts  = fonts
        self.uart   = uart
        self._q     = queue.Queue()
        self._glow  = pygame.Surface((SW, SH), pygame.SRCALPHA)
        self.toast  = Toast()

        self.player_name   = "Player"
        self.layout_id     = 0
        self.board_data    = None
        self.hitboxes      = []
        self.sel_idx       = None
        self._sel_pend     = None
        self._mat_pend     = None
        self.shuffles_left = 5
        self.err_tiles     = []
        self._err_t        = 0.0
        self.hint_tiles    = []
        self._hint_t       = 0.0
        self._elapsed      = 0
        self._tick         = 0.0
        self._clk_on       = False
        self._end_state    = None       
        self._bg_name      = "bg_game.png"
        self._busy         = False

        _sz = (BTN_W, BTN_H)
        self._btn_imgs = {
            k: ax.ui(f"btn_{k}.png", _sz) for k in _BTN_KEYS
        }
        # Fix 4: reset sprite — dedicated square image, no background rect
        self._btn_imgs["reset"] = ax.ui("reset.png", (RESET_ICON_SZ, RESET_ICON_SZ))
        self._btn_en = {k: True for k in _BTN_KEYS}

        # HUD icon
        self._img_sandclock = ax.ui("sandclock.png", (HUD_ICON_SZ, HUD_ICON_SZ))

    def on_enter(self):
        log("GameScreen.on_enter: resetting state")
        while True:
            try:    self._q.get_nowait()
            except queue.Empty: break

        self.board_data    = None
        self.hitboxes      = []
        self.sel_idx       = None
        self._sel_pend     = None
        self._mat_pend     = None
        self.shuffles_left = 5
        self.err_tiles     = []
        self._err_t        = 0.0
        self.hint_tiles    = []
        self._hint_t       = 0.0
        self._elapsed      = 0
        self._tick         = 0.0
        self._clk_on       = False
        self._end_state    = None
        self._bg_name      = "bg_game.png"
        self._busy         = True   

        threading.Thread(target=self._boot_thread, daemon=True).start()

    def _boot_thread(self):
        uart = self.uart
        log("boot: sleeping 1 s")
        time.sleep(1.0)

        for attempt in range(2):
            log(f"boot: double-flush + CMD_RESET (attempt {attempt+1})")
            uart.reset_buffer()
            time.sleep(0.08)
            uart.reset_buffer()
            if not uart.send_packet(CMD_RESET, 0x00):
                continue
            ack = uart.read_packet_strictly(3, timeout_sec=3.0)
            log(f"boot: RESET ACK → {ack and len(ack) or 'None'} bytes")
            if ack and ack[0] == CMD_RESET:
                break
        else:
            self._q.put({"kind": "boot", "data": None, "why": "reset_no_ack"})
            return

        log("boot: 500 ms settle")
        time.sleep(0.5)

        log(f"boot: CMD_START layout={self.layout_id}")
        uart.reset_buffer()
        if not uart.send_packet(CMD_START, self.layout_id):
            self._q.put({"kind": "boot", "data": None, "why": "send_start_fail"})
            return

        board = uart.read_packet_strictly(WIRE_BOARD, timeout_sec=10.0)
        log(f"boot: board → {len(board) if board else 'None'} bytes")
        self._q.put({"kind": "boot", "data": board,
                     "why": "ok" if board else "start_no_resp"})

    def _dispatch(self, kind: str, fn):
        if self._busy:
            log(f"dispatch({kind}): skipped — busy")
            return
        self._busy = True
        def _w():
            self._q.put({"kind": kind, "data": fn()})
        threading.Thread(target=_w, daemon=True).start()

    def _cmd_shuffle(self):
        def fn():
            u = self.uart
            u.reset_buffer()
            if not u.send_packet(CMD_SHUFFLE, 0x00): return None
            r = u.read_packet_strictly(WIRE_BOARD, timeout_sec=4.0)
            if r is None:                              
                r = u.read_packet_strictly(3, timeout_sec=0.5)
            return r
        self._dispatch("shuffle", fn)

    def _cmd_select(self, idx):
        self._sel_pend = idx
        def fn():
            u = self.uart
            u.reset_buffer()
            if not u.send_packet(CMD_SELECT, idx): return None
            return u.read_packet_strictly(3, timeout_sec=1.0)
        self._dispatch("select", fn)

    def _cmd_match(self, idx):
        self._mat_pend = idx
        def fn():
            u = self.uart
            u.reset_buffer()
            if not u.send_packet(CMD_MATCH, idx): return None
            return u.read_packet_strictly(3, timeout_sec=1.0)
        self._dispatch("match", fn)

    def _cmd_hint(self):
        def fn():
            u = self.uart
            u.reset_buffer()
            if not u.send_packet(CMD_HINT, 0x00): return None
            return u.read_packet_strictly(4, timeout_sec=1.5)
        self._dispatch("hint", fn)

    def _cmd_check_moves(self):
        def fn():
            u = self.uart
            u.reset_buffer()
            if not u.send_packet(CMD_HINT, 0x00): return None
            return u.read_packet_strictly(4, timeout_sec=1.5)
        self._dispatch("check_moves", fn)

    def _cmd_giveup(self):
        def fn():
            u = self.uart
            u.reset_buffer()
            u.send_packet(CMD_GIVE_UP, 0x00)
            return u.read_packet_strictly(3, timeout_sec=1.0)
        self._dispatch("giveup", fn)

    def _cmd_time(self):
        def fn():
            u = self.uart
            u.reset_buffer()
            if not u.send_packet(CMD_GET_TIME, 0x00): return None
            return u.read_packet_strictly(WIRE_BOARD, timeout_sec=0.8)
        self._dispatch("time", fn)

    def _cmd_leaders(self):
        def fn():
            u = self.uart
            u.reset_buffer()
            if not u.send_packet(CMD_GET_LEADERS, 0x00): return None
            return u.read_packet_strictly(202, timeout_sec=2.5)
        self._dispatch("leaders", fn)

    def handle_error(self, retry_fn, *args) -> str:
        self._busy = False

        log("handle_error: showing unified Connection Lost dialog")
        while True:
            if modal_ask_retry(self.screen, self.fonts, "Connection Lost!\nCheck USB cable then click Retry."):
                if self.uart.reconnect():
                    log("handle_error: reconnected successfully.")
                    
                    if self.uart.check_for_starting_packet():
                        log("handle_error: Starting packet detected! STM32 lost power.")
                        modal_info(self.screen, self.fonts,
                                   "STM32 Rebooted",
                                   "The board lost power and reset.\nPlease start a new game.", C_RED)
                        return "exit_to_menu"
                    
                    log("handle_error: Connection restored cleanly — retrying command")
                    retry_fn(*args)
                    return ""
                else:
                    log("handle_error: reconnect failed — keeping dialog open")
            else:
                log("handle_error: cancel → menu")
                return "exit_to_menu"
        return ""

    def _on_result(self, kind: str, data, why: str = "") -> str:
        self._busy = False   

        if data is None:
            log(f"_on_result({kind}): data=None why={why!r}")
            if kind == "time":
                return ""   
            retries = {
                "boot":    self.on_enter,
                "shuffle": self._cmd_shuffle,
                "select":  lambda: self._cmd_select(self._sel_pend),
                "match":   lambda: self._cmd_match(self._mat_pend),
                "hint":    self._cmd_hint,
                "check_moves": self._cmd_check_moves,
                "giveup":  self._cmd_giveup,
                "leaders": self._cmd_leaders,
            }
            fn = retries.get(kind)
            if fn:
                return self.handle_error(fn) or ""
            return ""

        if kind == "boot":
            if len(data) == 51 and data[0] == CMD_START:
                self.board_data    = bytes(data[1:])
                self.sel_idx       = None
                self.shuffles_left = 5
                self._elapsed      = 0
                self._clk_on       = True
                self._build_hitboxes()
                self.toast.show("Board ready!  Good luck.", C_ACCENT)
                log("_on_result(boot): BOARD LOADED ✓")
            else:
                log(f"_on_result(boot): unexpected packet ({len(data)}B) — retry in 1 s")
                self.toast.show("Bad board packet — retrying…", C_RED)
                threading.Timer(1.0, self.on_enter).start()
            return ""

        if kind == "shuffle":
            if data and len(data) == 51 and data[0] == CMD_SHUFFLE:
                self.board_data    = bytes(data[1:])
                self.sel_idx       = None
                self.hint_tiles    = []
                self.err_tiles     = []
                self.shuffles_left = max(0, self.shuffles_left - 1)
                self._build_hitboxes()
                self.toast.show("Board shuffled!", C_BLUE)
                self._check_gameover()
            elif data and len(data) >= 2 and data[1] == 0xFF:
                self.shuffles_left = 0
                modal_info(self.screen, self.fonts,
                           "Shuffle", "Shuffle limit reached!")
                self._check_gameover()
            return ""

        if kind == "select":
            if data and len(data) >= 2 and data[0] == CMD_SELECT:
                if data[1] == 0x00:
                    self.sel_idx = self._sel_pend
                else:
                    self._flash_err([self._sel_pend])
            return ""

        if kind == "match":
            if data and len(data) >= 2 and data[0] == CMD_MATCH:
                if data[1] == 0x01:   
                    bd = bytearray(self.board_data)
                    for i in [self._sel_pend, self._mat_pend]:
                        if i is not None and 0 <= i < len(bd):
                            bd[i] = 0
                    self.board_data = bytes(bd)
                    self.sel_idx    = None
                    self._build_hitboxes()
                    if all(v == 0 for v in self.board_data):
                        self._clk_on = False
                        self._trigger_win()
                    else:
                        self._check_gameover()
                else:                  
                    self.sel_idx = None
                    self._flash_err([self._sel_pend, self._mat_pend])
            return ""

        if kind in ("hint", "check_moves"):
            if data and len(data) >= 3 and data[0] == CMD_HINT:
                i1, i2 = data[1], data[2]
                if i1 == 100:
                    return self._eval_defeat() or ""
                elif kind == "hint":
                    self._flash_hint([i1, i2]) 
            return ""

        if kind == "giveup":
            return "exit_to_menu"

        if kind == "time":
            if data and len(data) == 51 and data[0] == CMD_GET_TIME:
                self._elapsed = int.from_bytes(bytes(data[1:5]), "big")
            return ""

        if kind == "leaders":
            leaders = self._parse_leaders(data)
            return self._show_endgame(leaders) or "" 

        return ""

    def _trigger_win(self):
        self._end_state = "win"
        self._bg_name   = "bg_win.png"  
        log("Victory — fetching leaderboard")
        self._cmd_leaders()

    def _check_gameover(self):
        if self.shuffles_left > 0:
            return
        if not self._busy:
            self._cmd_check_moves()

    def _eval_defeat(self):
        if self.shuffles_left == 0:
            self._clk_on    = False
            self._end_state = "loss"
            self._bg_name   = "bg_lose.png"  
            return self._show_endgame(None)
        else:
            self.toast.show("No pairs left — use a shuffle!", C_YELLOW)
            return ""         

    def _parse_leaders(self, raw):
        if not raw or len(raw) < 201 or raw[0] != CMD_GET_LEADERS:
            return None
        payload = raw[1:201]
        out = []
        for i in range(10):
            chunk = payload[i*20:(i+1)*20]
            if len(chunk) < 20: break
            name_raw, pt = struct.unpack_from("<16sI", chunk)
            name = name_raw.decode("utf-8", errors="ignore").rstrip("\x00").strip()
            out.append((name, pt))
        return out

    def _flash_err(self, indices):
        self.err_tiles = [i for i in indices if i is not None and i >= 0]
        self._err_t    = 0.55

    def _flash_hint(self, indices):
        self.hint_tiles = [i for i in indices if i >= 0]
        self._hint_t    = 1.9

    def _build_hitboxes(self):
        self.hitboxes = []
        if not self.board_data:
            return
        if self.layout_id == 0:
            self._hitboxes_sq()
        else:
            self._hitboxes_tri()

    def _hitboxes_sq(self):
        # Square: TILE_STEP_X/Y for grid spacing; TILE_W/H for rendered rect.
        for L, (rows, cols, off_c, off_r, base) in enumerate(SQ_LAYER_SPECS):
            for r in range(rows):
                for c in range(cols):
                    idx = base + r * cols + c
                    if idx >= TILE_COUNT: continue
                    px = SQ_OX + int((c + off_c) * TILE_STEP_X) + L * LAYER_DX
                    py = SQ_OY + int((r + off_r) * TILE_STEP_Y) + L * LAYER_DY
                    self.hitboxes.append((px, py, px + TILE_W, py + TILE_H, idx))

    def _hitboxes_tri(self):
        FIX_X = -15   # трохи вправо
        FIX_Y = 8   # трохи вниз

        for L, (num_rows, base) in enumerate(TRI_LAYERS):
            for R in range(num_rows):
                for C in range(R + 1):
                    idx = base + R * (R + 1) // 2 + C
                    if idx >= TILE_COUNT:
                        continue

                    px = BOARD_CX + (C - R / 2.0) * TRI_TILE_W + FIX_X
                    py = TRI_OY + (L + R) * TRI_TILE_H + FIX_Y

                    self.hitboxes.append((
                        int(px),
                        int(py),
                        int(px + TRI_TILE_W),
                        int(py + TRI_TILE_H),
                        idx
                    ))

    def _show_endgame(self, leaders):
        is_win = (self._end_state == "win")
        title  = "VICTORY!" if is_win else "DEFEAT"
        tc     = C_WOOD if is_win else C_RED
        bg     = self.ax.bg(self._bg_name)

        ph = 440 if (is_win and leaders) else 210
        pw = 640
        px = SW // 2 - pw // 2
        py = SH // 2 - ph // 2

        ok_r = pygame.Rect(SW // 2 - (215 if is_win else 95), py + ph - 62, 180, 44)
        ra_r = pygame.Rect(SW // 2 + 35, py + ph - 62, 180, 44) if is_win else None
        clk  = pygame.time.Clock()
        _fnt_row = pygame.font.SysFont("arial", 17)   # leaderboard rows

        while True:
            for ev in pygame.event.get():
                if ev.type == QUIT:
                    self._do_cleanup(); pygame.quit(); sys.exit()
                if ev.type == MOUSEBUTTONDOWN and ev.button == 1:
                    if ok_r.collidepoint(ev.pos):
                        return "exit_to_menu"
                    if ra_r and ra_r.collidepoint(ev.pos):
                        self._end_state = None
                        self._bg_name   = "bg_game.png"
                        self.on_enter()
                        return ""
                if ev.type == KEYDOWN and ev.key in (K_RETURN, K_ESCAPE):
                    return

            self.screen.blit(bg, (0, 0))

            # Fix 5: minimalist semi-transparent dark-brown panel, no border
            _pan = pygame.Surface((pw, ph), pygame.SRCALPHA)
            pygame.draw.rect(_pan, (30, 20, 10, 180), (0, 0, pw, ph), border_radius=16)
            self.screen.blit(_pan, (px, py))

            # Title + subtitle
            _blit_c(self.screen, title,
                    self.fonts["title"], tc, SW // 2, py + 46)
            _blit_c(self.screen,
                    "You cleared the board!" if is_win
                    else "No moves and no shuffles remaining.",
                    self.fonts["body"], C_WOOD, SW // 2, py + 94)

            # Leaderboard (win only)
            if is_win and leaders:
                _cols = [px+32, px+90, px+350, px+520]
                _hy   = py + 128
                for _hdr, _hx in zip(["#", "Player", "Time", ""], _cols):
                    _blit_a(self.screen, _hdr, _fnt_row, C_GREY, _hx, _hy, "midleft")
                pygame.draw.line(self.screen, (*C_GREY, 100),
                                 (px+18, _hy+16), (px+pw-18, _hy+16), 1)
                for i, (n, t_) in enumerate(leaders[:7]):
                    _ry = _hy + 22 + i * 32
                    if i % 2 == 0:
                        _row = pygame.Surface((pw-20, 26), pygame.SRCALPHA)
                        _row.fill((255, 255, 255, 10))
                        self.screen.blit(_row, (px+10, _ry-1))
                    ts_ = f"{t_//60:02d}:{t_%60:02d}" if t_ < 999999 else "---"
                    _rc = C_WOOD if i < 3 else C_GREY
                    _blit_a(self.screen, str(i+1), _fnt_row, _rc,
                            _cols[0], _ry+12, "midleft")
                    _blit_a(self.screen, n or "Empty", _fnt_row, C_WOOD,
                            _cols[1], _ry+12, "midleft")
                    _blit_a(self.screen, ts_, _fnt_row, C_WOOD,
                            _cols[2], _ry+12, "midleft")

            # Final time
            m, s = self._elapsed // 60, self._elapsed % 60
            _blit_c(self.screen, f"Time: {m:02d}:{s:02d}",
                    self.fonts["body"], C_WOOD, SW // 2, py + ph + 40)

            # Buttons: translucent parchment pill, 1-px C_WOOD outline
            for _br, _lbl in filter(lambda x: x[0] is not None,
                                    [(ok_r, "Return to Menu"), (ra_r, "Play Again")]):
                _bs = pygame.Surface((_br.w, _br.h), pygame.SRCALPHA)
                pygame.draw.rect(_bs, (*C_WOOD, 40),  (0,0,_br.w,_br.h), border_radius=8)
                pygame.draw.rect(_bs, (*C_WOOD, 180), (0,0,_br.w,_br.h), 1, border_radius=8)
                self.screen.blit(_bs, _br.topleft)
                _blit_c(self.screen, _lbl,
                        self.fonts["body"], C_WOOD, _br.centerx, _br.centery)

            pygame.display.flip()
            clk.tick(30)

    def _do_cleanup(self):
        self._clk_on = False
        self.uart.close_port()
        log("Port closed (cleanup)")

    def handle_event(self, ev) -> str:
        if ev.type == MOUSEBUTTONDOWN and ev.button == 1:
            for i, key in enumerate(_BTN_KEYS):
                if not self._btn_en.get(key, True):
                    continue
                if _btn_rect(i).collidepoint(ev.pos):
                    if key == "exit":
                        self._do_cleanup()
                        return "exit_to_menu"
                    elif key == "reset" and not self._busy:
                        self._clk_on = False
                        self.on_enter()
                    elif key == "shuffle" and not self._busy and self.shuffles_left > 0:
                        self._cmd_shuffle()
                    elif key == "hint" and not self._busy:
                        self._cmd_hint()
                    elif key == "giveup" and not self._busy:
                        self._clk_on = False
                        self._cmd_giveup()
            self._board_click(ev.pos)
        return ""

    def _board_click(self, pos):
        if not self.board_data or self._busy:
            return
        clicked = -1
        for hb in reversed(self.hitboxes):
            x1, y1, x2, y2, idx = hb
            if x1 <= pos[0] <= x2 and y1 <= pos[1] <= y2:
                if idx < len(self.board_data) and self.board_data[idx]:
                    clicked = idx
                    break
        if clicked == -1:
            return
        if self.sel_idx is None:
            self._cmd_select(clicked)
        elif clicked == self.sel_idx:
            self.sel_idx = None   
        else:
            self._sel_pend = self.sel_idx
            self._cmd_match(clicked)

    def update(self, dt: float) -> str:
        result = ""

        try:
            while True:
                msg = self._q.get_nowait()
                r   = self._on_result(msg.get("kind",""), msg.get("data"),
                                      msg.get("why",""))
                if r:
                    result = r
        except queue.Empty:
            pass

        if not self._busy and self._clk_on:
            if not self.uart.check_connection():
                log("BUG1: Physical disconnect detected in background")
                self._clk_on = False
                
                while True:
                    if modal_ask_retry(self.screen, self.fonts, "Connection Lost!\nCheck USB cable then click Retry."):
                        if self.uart.reconnect():
                            if self.uart.check_for_starting_packet():
                                log("Background: Starting packet detected! STM32 lost power.")
                                modal_info(self.screen, self.fonts, "STM32 Rebooted", "The board lost power and reset.\nPlease start a new game.", C_RED)
                                self._do_cleanup()
                                return "exit_to_menu"
                            log("Background: reconnect successful cleanly")
                            self._clk_on = True
                            break
                    else:
                        log("Background: reconnect canceled")
                        self._do_cleanup()
                        return "exit_to_menu"

        if self._err_t > 0:
            self._err_t -= dt
            if self._err_t <= 0: self.err_tiles = []
        if self._hint_t > 0:
            self._hint_t -= dt
            if self._hint_t <= 0: self.hint_tiles = []

        if self._clk_on and not self._busy:
            self._tick += dt
            if self._tick >= 1.0:
                self._tick = 0.0
                self._cmd_time()

        self._btn_en["shuffle"] = (self.shuffles_left > 0)

        self.toast.update(dt)
        return result

    def draw(self):
        self.screen.blit(self.ax.bg(self._bg_name), (0, 0))

        # ── Fix 5: two semi-transparent brown HUD plates, no borders/lines ────
        _PAD_X, _PAD_Y, _PR = 8, 4, 8
        _PH = INFO_H - 2 * _PAD_Y      # 32 px plate height

        # Left plate: sandclock + timer + player name
        _LW = 310
        _lp = pygame.Surface((_LW, _PH), pygame.SRCALPHA)
        pygame.draw.rect(_lp, (*C_PLATE, 150), (0, 0, _LW, _PH), border_radius=_PR)
        self.screen.blit(_lp, (_PAD_X, _PAD_Y))

        _ic_y = _PAD_Y + (_PH - HUD_ICON_SZ) // 2
        self.screen.blit(self._img_sandclock, (_PAD_X + 6, _ic_y))

        # Fix 3: generous spacing between timer and player name
        m, s = self._elapsed // 60, self._elapsed % 60
        _timer_x = _PAD_X + 6 + HUD_ICON_SZ + 6
        _name_x  = _timer_x + 90
        _blit_a(self.screen, f"{m:02d}:{s:02d}",
                self.fonts["body"], C_WOOD, _timer_x, _PAD_Y + _PH // 2, "midleft")
        _blit_a(self.screen, self.player_name,
                self.fonts["body"], C_WOOD, _name_x,  _PAD_Y + _PH // 2, "midleft")

        # Right plate: shuffles + layout name
        _RW = 230
        _rp = pygame.Surface((_RW, _PH), pygame.SRCALPHA)
        pygame.draw.rect(_rp, (*C_PLATE, 150), (0, 0, _RW, _PH), border_radius=_PR)
        self.screen.blit(_rp, (SW - _PAD_X - _RW, _PAD_Y))

        _sc = C_RED if self.shuffles_left == 0 else C_WOOD
        _blit_a(self.screen, f"Shuffles: {self.shuffles_left}",
                self.fonts["body"], _sc,
                SW - _PAD_X - _RW + 10, _PAD_Y + _PH // 2, "midleft")

        # Fix 3: Arial for layout name — always legible regardless of custom font
        _fnt_lay = pygame.font.SysFont("arial", 20)
        _lay_lbl = "Triangle" if self.layout_id else "Square"
        _lay_img = _fnt_lay.render(_lay_lbl, True, C_WOOD)
        _lay_r   = _lay_img.get_rect(midright=(SW - _PAD_X - 8, _PAD_Y + _PH // 2))
        self.screen.blit(_lay_img, _lay_r)

        # ── Board tiles ────────────────────────────────────────────────────────
        self._glow.fill((0, 0, 0, 0))
        if self.board_data:
            for (x1, y1, x2, y2, idx) in self.hitboxes:
                if idx >= len(self.board_data) or not self.board_data[idx]:
                    continue
                if   idx == self.sel_idx:    state = "selected"
                elif idx in self.err_tiles:  state = "error"
                elif idx in self.hint_tiles: state = "hint"
                else:                        state = "normal"
                tw = x2 - x1
                th = y2 - y1
                _draw_tile(self.screen, self.ax, x1, y1,
                           self.board_data[idx], state, self.fonts, self._glow,
                           tw, th)
            self.screen.blit(self._glow, (0, 0))
        else:
            dots = "." * (int(time.time() * 2) % 4)
            _blit_c(self.screen, f"Loading board{dots}",
                    self.fonts["head"], C_GREY, SW // 2, SH // 2)

        # ── Toolbar ────────────────────────────────────────────────────────────
        tb = pygame.Surface((SW, TOOLBAR_H), pygame.SRCALPHA)
        tb.fill((6, 8, 16, 215))
        self.screen.blit(tb, (0, BOARD_BOT))
        # No separator line

        for i, key in enumerate(_BTN_KEYS):
            r   = _btn_rect(i)
            img = self._btn_imgs[key]
            if key == "reset":
                # Fix 4: sprite only, centred — no rectangle, no symbol
                ix = r.centerx - img.get_width()  // 2
                iy = r.centery - img.get_height() // 2
                self.screen.blit(img, (ix, iy))
            else:
                self.screen.blit(img, r.topleft)

            if r.collidepoint(pygame.mouse.get_pos()) and self._btn_en.get(key, True):
                hov = pygame.Surface(r.size, pygame.SRCALPHA)
                hov.fill((255, 255, 255, 38))
                self.screen.blit(hov, r.topleft)
            if not self._btn_en.get(key, True):
                dim = pygame.Surface(r.size, pygame.SRCALPHA)
                dim.fill((0, 0, 0, 130))
                self.screen.blit(dim, r.topleft)

        # No yellow busy dot
        self.toast.draw(self.screen, self.fonts["body"])


# ══════════════════════════════════════════════════════ APPLICATION ═══════════
S_MENU = "MENU"
S_GAME = "GAME"


class MahjongApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("STM32 Mahjong")
        self.screen = pygame.display.set_mode((SW, SH))
        self.clock  = pygame.time.Clock()
        self.fonts  = _mk_fonts()
        self.ax     = Assets()
        self.uart   = UARTHandler()
        self.state  = S_MENU

        self.menu = MenuScreen(self.screen, self.ax, self.fonts, self.uart)
        self.game = GameScreen(self.screen, self.ax, self.fonts, self.uart)

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for ev in pygame.event.get():
                if ev.type == QUIT:
                    running = False
                    break
                if self.state == S_MENU:
                    self.menu.handle_event(ev)
                else:
                    res = self.game.handle_event(ev)
                    if res == "exit_to_menu":
                        self._to_menu()

            if not running:
                break

            if self.state == S_MENU:
                res = self.menu.update(dt)
                if res and res.get("action") == "goto_game":
                    self._to_game(res["name"], res["layout"])
            else:
                res = self.game.update(dt)
                if res == "exit_to_menu":
                    self._to_menu()

            if self.state == S_MENU:
                self.menu.draw()
            else:
                self.game.draw()

            pygame.display.flip()

        self.game._clk_on = False
        self.uart.close_port()
        pygame.quit()
        sys.exit(0)

    def _to_game(self, name: str, layout_id: int):
        log(f"App: → game  player='{name}'  layout={layout_id}")
        self.game.player_name = name
        self.game.layout_id   = layout_id
        self.state            = S_GAME
        self.game.on_enter()

    def _to_menu(self):
        log("App: → menu")
        self.game._do_cleanup()   
        self.state        = S_MENU
        self.menu.status  = ""
        self.menu._do_refresh()


if __name__ == "__main__":
    MahjongApp().run()