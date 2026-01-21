from shape import Rect

import pygame
from color import Color

class Slider:

    interface: pygame.Surface = NotImplemented
    mouse_position: tuple[int, int] = (0,0)
    left_mouse_hold: bool = False
    debug_mode: bool = False
    
    # Adds sensitivity to the slider.
    INPUT_HORIZONTAL_LENIENCY: int = 30
    INPUT_VERTICAL_LENIENCY: int = 20

    def __init__(self,
                 x:int,
                 y:int,
                 width:int,
                 height:int,
                 min:int|float=0.0,
                 max:int|float=1.0,
                 initial_val:int|float=0.5,
                 num_type:type=int,
                 *,
                 track_color:Color=Color.HYPERDARK_GRAY,
                 track_width:int=3,
                 knob_radius:int = 12,
                 knob_color:Color=Color.DARK_GRAY,
                 track_border_width:int=-1,
                 track_border_color:Color=Color.BLACK,
                 knob_hover_color:Color=Color.GRAY,
                 knob_disabled_color:Color=Color.HYPERDARK_GRAY,
                 knob_drag_color:Color=Color.DARK_BLUE,
                 knob_border_width:int=-1,
                 knob_border_color:Color=Color.LIGHT_GRAY,
                 enabled:bool=True,
                 visible:bool=True):
        if initial_val < min or initial_val > max:
            raise ValueError(f"Initial value {initial_val} is not between min:{min} and max:{max}")
        self.x: int = x
        self.y: int = y
        self.width: int = width
        self.height: int = height
        self.min: int | float = min
        self.max: int | float = max
        self.val: int | float = initial_val
        self.num_type: type = num_type
        self.track_color: Color = track_color
        self.track_width: int = track_width
        self.track_border_width: int = track_border_width
        self.track_border_color: Color = track_border_color
        self.knob_x: int = int((initial_val - min) / (max - min) * width) + x
        self.knob_radius: int = knob_radius
        self.knob_color: Color = knob_color
        self.knob_hover_color: Color = knob_hover_color
        self.knob_disabled_color: Color = knob_disabled_color
        self.knob_drag_color: Color = knob_drag_color
        self.knob_border_width: int = knob_border_width
        self.knob_border_color: Color = knob_border_color
        self.enabled: bool = enabled
        self.visible: bool = visible

        self.input_space: Rect = Rect(
            x - Slider.INPUT_HORIZONTAL_LENIENCY, 
            y - Slider.INPUT_VERTICAL_LENIENCY, 
            width + Slider.INPUT_HORIZONTAL_LENIENCY * 2,
            height + Slider.INPUT_VERTICAL_LENIENCY * 2)
        self.track_rect: pygame.Rect = pygame.Rect(
            x,
            y + height // 2 - track_width // 2,
            width,
            track_width)
        # Debug Space
        self.slider_background: pygame.Rect = pygame.Rect(
            x,
            y,
            width,
            height)
        self.input_space_rect: pygame.Rect = pygame.Rect(
            x - Slider.INPUT_HORIZONTAL_LENIENCY, 
            y - Slider.INPUT_VERTICAL_LENIENCY, 
            width + Slider.INPUT_HORIZONTAL_LENIENCY * 2,
            height + Slider.INPUT_VERTICAL_LENIENCY * 2)

    @staticmethod
    def set_screen(screen) -> None:
        Slider.interface = screen
    
    @staticmethod
    def update_mouse_position(mouse_position: tuple[int, int]) -> None:
        Slider.mouse_position = mouse_position
    
    @staticmethod
    def update_left_mouse_hold(left_mouse_hold: bool) -> None:
        Slider.left_mouse_hold = left_mouse_hold

    def update(self) -> None:
        self.knob_x = int((self.val - self.min) / (self.max - self.min) * self.width) + self.x
        self.input_space = Rect(
            self.x - Slider.INPUT_HORIZONTAL_LENIENCY, 
            self.y - Slider.INPUT_VERTICAL_LENIENCY, 
            self.width + Slider.INPUT_HORIZONTAL_LENIENCY * 2,
            self.height + Slider.INPUT_VERTICAL_LENIENCY * 2)
        self.track_rect = pygame.Rect(
            self.x,
            self.y + self.height // 2 - self.track_width // 2,
            self.width,
            self.track_width)
        # Debug Space
        self.slider_background = pygame.Rect(
            self.x,
            self.y,
            self.width,
            self.height)
        self.input_space_rect = pygame.Rect(
            self.x - Slider.INPUT_HORIZONTAL_LENIENCY, 
            self.y - Slider.INPUT_VERTICAL_LENIENCY, 
            self.width + Slider.INPUT_HORIZONTAL_LENIENCY * 2,
            self.height + Slider.INPUT_VERTICAL_LENIENCY * 2)
    

    def is_hovered(self) -> bool:
        # For the sake of consistency, the slider is not hovered if the shape is not visible or enabled
        return self.visible and self.enabled and self.input_space.inside_shape(*Slider.mouse_position)

    def draw(self) -> None:
        """Draws the slider onto the screen."""
        if not self.visible:
            return
        # Debug
        if Slider.debug_mode:
            pygame.draw.rect(Slider.interface, Color.RED.value, self.input_space_rect)
            pygame.draw.rect(Slider.interface, Color.GOLD.value, self.slider_background)
        # Draw track
        pygame.draw.rect(Slider.interface, self.track_color.value, self.track_rect, border_radius=self.track_width // 2)
        pygame.draw.rect(Slider.interface, self.track_border_color.value, self.track_rect, border_radius=self.track_width // 2, width=self.track_border_width)
        # Draw knob
        current_knob_color: Color = self.knob_color
        if not self.enabled:
            current_knob_color = self.knob_disabled_color
        elif self.is_hovered():
            if Slider.left_mouse_hold:
                current_knob_color = self.knob_drag_color
            else:
                current_knob_color = self.knob_hover_color
        pygame.draw.circle(Slider.interface, current_knob_color.value, (self.knob_x, self.y + self.height // 2), self.knob_radius)
        pygame.draw.circle(Slider.interface, self.knob_border_color.value, (self.knob_x, self.y + self.height // 2), self.knob_radius, width=self.knob_border_width)

    def drag(self) -> None: 
        """Drag the knob to a different position on the slider"""
        if not self.is_hovered() or not Slider.left_mouse_hold:
            return
        self.knob_x = int(self._clamp(Slider.mouse_position[0], self.x, self.x + self.width))
        percentage = float(self._clamp((Slider.mouse_position[0] - self.x) / self.width, 0.0, 1.0))
        if self.num_type == int:
            self.val = round((self.max - self.min) * percentage + self.min)
        elif self.num_type == float:
            self.val = (self.max - self.min) * percentage + self.min
        else:
            raise TypeError("Variable self.num_type is neither a int or float type.")
        if Slider.debug_mode:
            print(self.val)

    def _clamp(self, n:int|float, low:int|float, high:int|float) -> int|float:
        """Clamps the value n between the min and max"""
        if type(n) != type(low) or type(low) != type(high):
            raise TypeError(f"Value n:{n}, low:{low}, high:{high} is not the same type.")
        return max(low, min(n, high)) 
