import auth
import places_logic
from fastapi import FastAPI
import pandas as pd
from pydantic import BaseModel
from datetime import datetime
import googlemaps
from dotenv import load_dotenv
import os
from typing import Dict
import json
import pprint

app = FastAPI()

load_dotenv()
GMAPS_API_KEY = os.getenv("GOOGLEMAPS_API_KEY", "Default Value")
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

SRC_USER_PLACE_NUM = 3
TARGET_USER_PLACE_NUM = 3

all_place_records = pd.DataFrame({
    'user_id': pd.Series(dtype='int32'),
    'place_id': pd.Series(dtype='string'),
    'time': pd.Series(dtype='datetime64[ns]')
})
gmaps_place_index = {}

@app.get("/bunq/auth")
def authentification(username: str, password: str) -> int:
    return auth.verify_users_credentials(username, password).id

@app.get("/bunq/{user_id}/suggested_places")
async def sugested_places(user_id: str):
    # TODO authentication
    print('======================\n', all_place_records, all_place_records.dtypes)
    # print(all_place_records['user_id'].dtype, type(int(user_id)))
    user_records = all_place_records[all_place_records['user_id'] == int(user_id)]
    print(user_records)
    # print(all_user_records, user_records, type(user_id), all_user_records['user_id'])
    places_hist = user_records['place_id'].value_counts()
    print(places_hist)
    first_place = places_hist.idxmax()
    candidate_people = all_place_records[(all_place_records['user_id'] != int(user_id)) & (all_place_records['place_id'] == first_place)]['user_id'].unique()
    candidate_places_hist = all_place_records[(all_place_records['user_id'].isin(candidate_people)) & (all_place_records['place_id'] != first_place)]['place_id'].value_counts()
    l = candidate_places_hist.index.tolist()
    print(l)
    for id in l:
        print(pprint.pprint(gmaps_place_index[id]))


def put_place_record(user_id: int, description: str):
    global all_place_records
    geocode_result = gmaps.find_place(description, input_type='textquery')
    place_id = geocode_result['candidates'][0]['place_id']
    place = gmaps.place(place_id)
    gmaps_place_index[place_id] = place
    place_record = {
        'user_id': int(user_id),
        'place_id': str(place_id),
        'time': datetime.now()
    }
    add_place_record = pd.DataFrame([place_record])
    all_place_records = pd.concat([all_place_records, add_place_record], ignore_index=True)

@app.put("/bunq/{user_id}/place_records")
async def update_user_record(user_id: int, payment: Dict):
    payment_description = payment['description']
    put_place_record(user_id, payment_description)
    

@app.post("/bunq/place_records")
async def get_place_records():
    with open('data/payments.json', 'r') as f:
        data = json.load(f)
    for payment in data:
        put_place_record(payment['user_id'], payment['description'])
    print(all_place_records)