from fastapi import FastAPI
import pandas as pd
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

SRC_USER_PLACE_NUM = 3
TARGET_USER_PLACE_NUM = 3

data = [
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
all_place_records = pd.DataFrame(data)

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

class UserlessPlaceRecord(BaseModel):
    place_id: str
    time: datetime

@app.post("/bunq/{user_id}/place_records")
async def update_user_record(user_id: int, userless_place_record: UserlessPlaceRecord):
    global all_place_records
    place_record = userless_place_record.dict()
    place_record['user_id'] = user_id
    add_place_record = pd.DataFrame([place_record])
    all_place_records = pd.concat([all_place_records, add_place_record], ignore_index=True)
    print(all_place_records)
