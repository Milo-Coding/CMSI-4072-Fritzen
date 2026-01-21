import pygame
import math

pygame.init()

from button import Button
from color import Color
from slider import Slider
import random


## Initialization
running: bool = True
interface: pygame.Surface = pygame.display.set_mode((1000, 1000), pygame.SCALED)
Button.interface = interface
Slider.interface = interface
Slider.debug_mode = True
CURSOR_STRING = (
  ".                       ",
  "..                      ",
  ".X.                     ",
  ".XX.                    ",
  ".XXX.                   ",
  ".XXXX.                  ",
  ".XXXXX.                 ",
  ".XXXXXX.                ",
  ".XXXXXXX.               ",
  ".XXXXXXXX.              ",
  ".XXXXXXXXX.             ",
  ".XXXXXXXXXX.            ",
  ".XXXXXX.....            ",
  ".XXX.XX.                ",
  ".XX. .XX.               ",
  ".X.  .XX.               ",
  "..    .XX.              ",
  "      .XX.              ",
  "       ..               ",
  "                        ",
  "                        ",
  "                        ",
  "                        ",
  "                        ")
SELECT_CURSOR_STRING = (
    "     ..                 ",
    "    .XX.                ",
    "    .XX.                ",
    "    .XX.                ",
    "    .XX.                ",
    "    .XX.                ",
    "    .XX...              ",
    "    .XX.XX...           ",
    "    .XX.XX.XX..         ",
    "    .XX.XX.XX.X.        ",
    "... .XX.XX.XX.XX.       ",
    ".XX..XXXXXXXX.XX.       ",
    ".XXX.XXXXXXXXXXX.       ",
    " .XX.XXXXXXXXXXX.       ",
    "  .X.XXXXXXXXXXX.       ",
    "  .XXXXXXXXXXXXX.       ",
    "   .XXXXXXXXXXXX.       ",
    "   .XXXXXXXXXXX.        ",
    "    .XXXXXXXXXX.        ",
    "    .XXXXXXXXXX.        ",
    "     .XXXXXXXX.         ",
    "     .XXXXXXXX.         ",
    "     ..........         ",
    "                        "
)
cursor = pygame.cursors.compile(CURSOR_STRING)
select_cursor = pygame.cursors.compile(SELECT_CURSOR_STRING)
pointing = False

# Buttons
button = Button(500, 850, 200, 100, shape="rect", text="Hi Dr. Johnson", border_width=3, border_radius=10, border_color=Color.YELLOW, enabled=True, visible=False, action=lambda:random.randint(0, 10))
def invert():
    button.visible = not button.visible
button2 = Button(100, 850, 200, 100, shape="rect", text="Hello", border_width=3, border_radius=10, border_color=Color.RED, enabled=True, action=invert)

buttons = (
    button,
    button2)
buttons_val = [None] * len(buttons)

# Sliders
slider = Slider(100, 100, 300, 20, 0, 100, 50, track_width=8, track_color=Color.LIGHT_GREEN, knob_border_color=Color.LIGHT_GRAY, knob_drag_color=Color.YELLOW,knob_border_width=2)
slider2 = Slider(100, 200, 300, 20, 0, 100, 50, track_width=8, knob_border_color=Color.LIGHT_GRAY, knob_border_width=2)
slider3 = Slider(100, 500, 300, 20, 0, 100, 50, track_width=8, knob_border_color=Color.LIGHT_GRAY, knob_border_width=2)
slider4 = Slider(100, 700, 300, 20, 0, 100, 50, track_width=30, knob_border_color=Color.LIGHT_GRAY, knob_border_width=2)

sliders = (
    slider,
    slider2,
    slider3,
    slider4)

## Game Loop
while running:
    interface.fill(Color.BLACK.value)
    Button.update_click(False)
    Button.update_left_mouse_hold(pygame.mouse.get_pressed()[0])
    Button.update_mouse_position(pygame.mouse.get_pos())
    Slider.update_left_mouse_hold(pygame.mouse.get_pressed()[0])
    Slider.update_mouse_position(pygame.mouse.get_pos())
    for event in pygame.event.get():
        match event.type:
            case pygame.QUIT:
                running = False
            case pygame.MOUSEBUTTONUP:
                Button.update_click(True)
    for i, b in enumerate(buttons):
        if b.is_hovered():
            pointing = True
        b.draw()
        buttons_val[i] = b.trigger()
    for s in sliders:
        if s.is_hovered():
            pointing = True
        s.drag()
        s.update()
        s.draw()
    
    slider2.width = int(slider.val * 5 + 100)
    slider3.x = int(slider.val * 5 + 100)
    slider3.y = int(math.asin(math.sin(slider.val / math.pi * 180 / 300)) * 100 + 500)

    if buttons_val[0] is not None:
        print(f"The random number is a {buttons_val[0]}")

    if pointing:
        pygame.mouse.set_cursor((24, 24), (6, 1), *select_cursor)
    else:
        pygame.mouse.set_cursor((24, 24), (0, 0), *cursor)
    pointing = False

    pygame.display.flip()
