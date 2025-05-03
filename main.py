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

import re
import uuid
import json
from typing import List
import faiss
from fastapi import Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from langchain.chat_models import init_chat_model
from langchain.prompts import PromptTemplate
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langgraph.graph import START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

app = FastAPI()

load_dotenv()
GMAPS_API_KEY = os.getenv("GOOGLEMAPS_API_KEY", "Default Value")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
# print(NVIDIA_API_KEY, 'hello')

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

@app.get("/bunq/{user_id}/suggested_places/{count}")
async def sugested_places(user_id: str, count: int):
    # print('======================\n', all_place_records, all_place_records.dtypes)
    # print(all_place_records['user_id'].dtype, type(int(user_id)))
    user_records = all_place_records[all_place_records['user_id'] == int(user_id)]
    # print(user_records)
    # print(all_user_records, user_records, type(user_id), all_user_records['user_id'])
    places_hist = user_records['place_id'].value_counts()
    # print(places_hist)
    first_place = places_hist.idxmax()
    candidate_people = all_place_records[(all_place_records['user_id'] != int(user_id)) & (all_place_records['place_id'] == first_place)]['user_id'].unique()
    candidate_places_hist = all_place_records[(all_place_records['user_id'].isin(candidate_people)) & (all_place_records['place_id'] != first_place)]['place_id'].value_counts()
    l = candidate_places_hist.index.tolist()
    l.insert(0, first_place)
    gmap_points = []
    for idx in l:
        gmap_points.append(gmaps_place_index[idx])
    locations = format_locations(gmap_points)
    return personal_rag(locations, count)

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

################# RAG ##################

class State(TypedDict):
    question: str
    count: str
    context: List[Document]
    answer: str

def format_locations(gmaps_points):
    locations = []
    for idx, point in enumerate(gmaps_points):
        review_texts = []
        for review in point['result']['reviews']:
            review_texts.append(review['text'])
        pprint.pprint(point)
        locations.append({
            "name": point['result']['name'],
            "price_level": point['result'].get('price_level', 0),
            "id": point['result']['place_id'],
            "category": point['result']['types'][0], 
            "reviews": review_texts,
        })
    return locations

def personal_rag(locations, count):
    llm = init_chat_model("meta/llama3-70b-instruct", model_provider="nvidia")

    primary = locations[0]
    secondaries = locations[1:]
    location_lookup = {}
    documents = []

    for loc in secondaries:
        text = f"[{loc['id']}] {loc['name']} {loc['category']} {loc['price_level']} {' '.join(loc['reviews'])}"
        documents.append(Document(page_content=text))

    prompt = PromptTemplate(
        input_variables=["question", "context", "count"],
        template="""
    You are a smart location recommendation agent.
    Primary Location:
    {question}

    Candidate Locations:
    {context}

    Recommend the top {count} similar locations. Return their [id] and a short reason.
    Give a response even if the location does not match fully.

    Format:
    1. [location_id] - Reason
    2. [location_id] - Reason
    ...
    """
    )

    def retrieve(state: State):
        retrieved_docs = [Document(
            page_content=f"[{loc['id']}] {loc['name']} {loc['category']} {loc['price_level']} {' '.join(loc['reviews'])}")
                        for loc in location_lookup.values()]
        return {"context": retrieved_docs}

    def generate(state: State):
        docs_content = "\n\n".join(doc.page_content for doc in state["context"])
        count = int(state.get("count", 2))
        messages = prompt.invoke({"question": state["question"], "context": docs_content, "count": str(count)})
        response = llm.invoke(messages)
        return {"answer": response.content}

    graph_builder = StateGraph(State).add_sequence([retrieve, generate])
    graph_builder.add_edge(START, "retrieve")
    graph = graph_builder.compile()

    class RecommendRequest(BaseModel):
        pass  # Placeholder if you want future extensions

    def recommend(count: int = 2):
        primary_text = f"{primary['category']} {primary['price_level']} {' '.join(primary['reviews'])}"
        result = graph.invoke({"question": primary_text, "context": [], "answer": "", "count": str(count)})

        recommended_ids = re.findall(r"\[(.*?)\]", result["answer"])
        # recommended_locations = [location_lookup[loc_id] for loc_id in recommended_ids if loc_id in location_lookup]

        return JSONResponse({
            # "recommended_ids": recommended_ids,
            "raw_answer": result["answer"]
        })
    
    return recommend(count)