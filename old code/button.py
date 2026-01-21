from typing import Callable, Any
from shape import Rect, Ellipse

import pygame
from color import Color

class Button:

    interface: pygame.Surface = NotImplemented
    mouse_position: tuple[int, int] = (0, 0)
    left_mouse_hold: bool = False
    click: bool = False

    # These default values are standardized for the game.
    def __init__(self,
                 x:int, 
                 y:int, 
                 width:int,
                 height:int,
                 *,
                 shape:str="rect",
                 text:str="", 
                 text_toggled:str="",
                 font:pygame.font.Font=pygame.font.Font(None,30),
                 font_color:Color=Color.BLACK,
                 color:Color=Color.WHITE,
                 hover_color:Color=Color.LIGHT_GRAY,
                 disabled_color:Color=Color.HYPERDARK_GRAY,
                 pressed_color:Color=Color.GRAY,
                 toggle_color:Color=Color.YELLOW,
                 border_radius:int=8,
                 border_width:int=2,
                 border_color:Color=Color.BLACK,
                 toggle:bool=False,
                 toggleable:bool=False,
                 enabled:bool=True,
                 visible:bool=True,
                 action:Callable=lambda:print("Clicked")):
        
        self.shape_type = shape
        self.shape: Rect | Ellipse = NotImplemented
        match shape:
            case "rect":
                self.shape = Rect(x, y, width, height)
            case "ellipse":
                self.shape = Ellipse(x, y, width, height)
            case _:
                raise ValueError(f"Shape must be a rect or ellipse, not {shape}.")
        self.rect: pygame.Rect = pygame.Rect(x, y, width, height)
        self.color: Color = color
        self.hover_color: Color = hover_color
        self.disabled_color: Color = disabled_color
        self.pressed_color: Color = pressed_color
        self.toggle_color: Color = toggle_color
        self.border_radius: int = border_radius
        self.border_width:int = border_width
        self.border_color:Color = border_color
        self.button_text: pygame.Surface = font.render(text, True, font_color.value)
        self.button_text_toggled: pygame.Surface = font.render(text_toggled or text, True, font_color.value)
        self.text_rect: pygame.Rect = self.button_text.get_rect(center=(x+width/2,y+height/2))
        self.text_toggled_rect: pygame.Rect = self.button_text_toggled.get_rect(center=(x+width/2,y+height/2))
        self.toggle: bool = toggle and toggleable
        self.toggleable: bool = toggleable
        self.enabled: bool = enabled
        self.visible: bool = visible
        self.action: Callable = action
    
    @staticmethod
    def set_screen(screen) -> None:
        Button.interface = screen
    
    @staticmethod
    def update_mouse_position(mouse_position: tuple[int, int]) -> None:
        Button.mouse_position = mouse_position
    
    @staticmethod
    def update_left_mouse_hold(left_mouse_hold: bool) -> None:
        Button.left_mouse_hold = left_mouse_hold

    @staticmethod
    def update_click(click: bool) -> None:
        Button.click = click

    def is_hovered(self) -> bool:
        return self.shape.inside_shape(*Button.mouse_position) and self.enabled and self.visible

    def draw(self) -> None:
        """Draws the button onto the screen."""
        if not self.visible:
            return
        button_color: Color = self.color
        if not self.enabled:
            button_color = self.disabled_color
        elif self.is_hovered():
            if Button.left_mouse_hold:
                button_color = self.pressed_color
            else:
                button_color = self.hover_color
        elif self.toggleable and self.toggle:
            button_color = self.toggle_color
        match self.shape_type:
            case "rect":
                pygame.draw.rect(Button.interface, button_color.value, self.rect, border_radius=self.border_radius)
                if self.border_width > 0:
                    pygame.draw.rect(Button.interface, self.border_color.value, self.rect, self.border_width, self.border_radius)
            case "ellipse":
                pygame.draw.ellipse(Button.interface, button_color.value, self.rect)
                if self.border_width > 0:
                    pygame.draw.ellipse(Button.interface, self.border_color.value, self.rect, self.border_width)
            case _:
                raise ValueError(f"Shape {self.shape_type} is not valid.")
        if self.toggleable and self.toggle:
            Button.interface.blit(self.button_text_toggled, self.text_toggled_rect)
        else:
            Button.interface.blit(self.button_text, self.text_rect)

    def trigger(self) -> Any:
        # For the sake of consistency, if the button is not visible, then it is also not enabled.
        if self.is_hovered() and Button.click:
            if self.toggleable:
                self.toggle = not self.toggle
            return self.action()