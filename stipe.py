from fastapi import FastAPI
import pandas as pd
from pydantic import BaseModel
from datetime import datetime
import googlemaps
from dotenv import load_dotenv
import os
from typing import Dict

app = FastAPI()

load_dotenv()
GMAPS_API_KEY = os.getenv("GOOGLEMAPS_API_KEY", "Default Value")
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

SRC_USER_PLACE_NUM = 3
TARGET_USER_PLACE_NUM = 3

place_records_data = [
    {"user_id": 1, "place_id": "A", "time": "2025-05-03 08:30:00"},
    {"user_id": 1, "place_id": "A", "time": "2025-05-03 05:30:00"},
    
    {"user_id": 2, "place_id": "A", "time": "2025-05-03 10:30:00"},
    {"user_id": 2, "place_id": "A", "time": "2025-05-03 07:00:00"},
    {"user_id": 2, "place_id": "B", "time": "2025-05-03 03:00:00"},
    {"user_id": 2, "place_id": "B", "time": "2025-05-03 04:00:00"},
    
    {"user_id": 3, "place_id": "A", "time": "2025-05-03 10:00:00"},
    {"user_id": 3, "place_id": "B", "time": "2025-05-03 10:00:00"},
    {"user_id": 3, "place_id": "C", "time": "2025-05-03 10:00:00"},

    {"user_id": 4, "place_id": "B", "time": "2025-05-03 04:00:00"},
    {"user_id": 4, "place_id": "B", "time": "2025-05-03 02:00:00"},
    {"user_id": 4, "place_id": "C", "time": "2025-05-03 10:00:00"},

    {"user_id": 5, "place_id": "B", "time": "2025-05-03 04:00:00"},
    {"user_id": 5, "place_id": "B", "time": "2025-05-03 11:00:00"},
    {"user_id": 5, "place_id": "D", "time": "2025-05-03 14:00:00"},
    {"user_id": 5, "place_id": "D", "time": "2025-05-03 18:00:00"},
]
all_place_records = pd.DataFrame(place_records_data)

gmaps_place_index = {}

def suggest_places(user_id):
    # TODO implement fail to auth?
    user_records = all_place_records[all_place_records['user_id'] == int(user_id)]
    # print(all_user_records, user_records, type(user_id), all_user_records['user_id'])
    places_hist = user_records['place_id'].value_counts()
    first_place = places_hist.idxmax()
    candidate_people = all_place_records[(all_place_records['user_id'] != int(user_id)) & (all_place_records['place_id'] == first_place)]['user_id'].unique()
    candidate_places_hist = all_place_records[(all_place_records['user_id'].isin(candidate_people)) & (all_place_records['place_id'] != first_place)]['place_id'].value_counts()
    print(candidate_places_hist.index.tolist())

@app.get("/bunq/{user_id}/suggested_places")
async def sugested_places(user_id: str):
    # TODO authentication
    suggest_places(user_id)

@app.post("/bunq/{user_id}/place_records")
async def update_user_record(user_id: int, payment: Dict):
    global all_place_records
    print(payment)
    payment_description = payment['description']
    geocode_result = gmaps.find_place(payment_description, input_type='textquery')
    place_id = geocode_result['candidates'][0]['place_id']
    place = gmaps.place(place_id)
    gmaps_place_index[place_id] = place
    place_record = {
        'user_id': user_id,
        'place_id': place_id,
        'time': datetime.now()
    }
    add_place_record = pd.DataFrame([place_record])
    all_place_records = pd.concat([all_place_records, add_place_record], ignore_index=True)
    print(all_place_records)
