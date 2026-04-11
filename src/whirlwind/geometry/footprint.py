from dataclasses import dataclass 

@dataclass 
class FootPrint:
    minx: float 
    miny: float 
    maxx: float 
    maxy: float 
    
    def __init__(self, minx: float, miny: float, maxx: float, maxy: float):
        self.minx = minx 
        self.miny = miny 
        self.maxx = maxx 
        self.maxy = maxy 

    def to_record(self) -> dict[str, float]:
        return {
            "minx": self.minx,
            "miny": self.miny,
            "maxx": self.maxx,
            "maxy": self.maxy
            }
    def contains(self, x: float, y: float) -> bool:
        return self.minx <= x <= self.maxx and self.miny <= y <= self.maxy 

    def intersects(self, other: "FootPrint") -> bool:
        return not (
            self.maxx < other.minx
            or self.minx > other.maxx
            or self.maxy < other.miny
            or self.miny > other.maxy
            )
    
    @property 
    def width(self) -> float:
        return self.maxx - self.minx 

    @property 
    def height(self) -> float:
        return self.maxy - self.miny
