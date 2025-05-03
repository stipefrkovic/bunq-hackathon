from fastapi import FastAPI
import pandas as pd

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
all_user_records = pd.DataFrame(data)

def suggest_places(user_id):
    # TODO implement fail to auth?
    user_records = all_user_records[all_user_records['user_id'] == int(user_id)]
    # print(all_user_records, user_records, type(user_id), all_user_records['user_id'])
    place_id_hist = user_records['place_id'].value_counts().to_dict()
    print(place_id_hist)

@app.get("/bunq/{user_id}/suggested_places")
def sugested_places(user_id: str):
    # TODO authentication
    suggest_places(user_id)