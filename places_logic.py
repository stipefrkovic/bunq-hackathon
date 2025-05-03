from pydantic import BaseModel
from enum import Enum

class Place_Types(Enum):
    Restaurant = 1
    Bar = 2
    Museum = 3

class Reccomendation_Types(Enum):
    Trending = 1
    Related = 2

class Place(BaseModel):
    name: str
    short_summary: str
    maps_google_link: str
    photos: list[str] | None
    coordinates: tuple[float, float]
    place_type: str
    rec_type: str
    rag_info_id: int