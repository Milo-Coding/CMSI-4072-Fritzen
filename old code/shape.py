from abc import ABC, abstractmethod
import math

class Shape(ABC):
    @abstractmethod
    def inside_shape(self, x:int, y:int, tolerance:float) -> bool:
        pass

class Rect(Shape):
    def __init__(self, x:int, y:int, width:int, height:int):
        self.x: int = x
        self.y: int = y
        self.width: int = width
        self.height: int = height

    def inside_shape(self, x:int, y:int, tolerance:float=0.0) -> bool:
        left = self.x
        right = self.x + self.width
        top = self.y
        bottom = self.y + self.height
        return left < x and x < right and top < y and y < bottom
    
class Ellipse(Shape):
    def __init__(self, x:int, y:int, width:int, height:int):
        self.x: int = x
        self.y: int = y
        self.width: int = width
        self.height: int = height
    
    def inside_shape(self, x:int, y:int, tolerance:float = 1e-9) -> bool:
        # get the center of the circle by adding the offset
        x_mid = self.x + (self.width // 2)
        y_mid = self.y + (self.height // 2)
        dist = (((x - x_mid) ** 2) / (self.width ** 2) +
                ((y - y_mid) ** 2) / (self.height ** 2))
        # tolerance is used due to floating-point arithmetic
        return dist <= 0.25 + tolerance