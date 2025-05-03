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

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,              # or ["*"] for all origins
    allow_credentials=True,
    allow_methods=["*"],                # allow all HTTP methods
    allow_headers=["*"],                # allow all headers
)

load_dotenv()
GMAPS_API_KEY = os.getenv("GOOGLEMAPS_API_KEY", "Default Value")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
# print(NVIDIA_API_KEY, 'hello')

gmaps = googlemaps.Client(key=GMAPS_API_KEY)

all_place_records = pd.DataFrame({
    'user_id': pd.Series(dtype='int32'),
    'place_id': pd.Series(dtype='string'),
    'time': pd.Series(dtype='datetime64[ns]')
})
gmaps_place_index = {}

@app.get("/bunq/auth")
def authentification(username: str, password: str) -> int:
    user = auth.verify_users_credentials(username, password)
    if user is not None:
        return user.id
    return -1

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
        for review in point['result']['reviews'][:1]:
            review_texts.append(review['text'])
        pprint.pprint(point)
        locations.append({
            "id": point['result']['place_id'],
            "name": point['result']['name'],
            "category": point['result']['types'][0], 
            "price_level": point['result'].get('price_level', 2),
            "reviews": review_texts,
        })
    return locations

def personal_rag(locations, count):
    print(locations)
    llm = init_chat_model("meta/llama3-70b-instruct", model_provider="nvidia")
    embeddings = NVIDIAEmbeddings(model="NV-Embed-QA")
    embedding_dim = len(embeddings.embed_query("hello world"))
    index = faiss.IndexFlatL2(embedding_dim)
    vector_store = FAISS(embedding_function=embeddings, index=index, docstore=InMemoryDocstore(), index_to_docstore_id={})

    primary = locations[0]
    secondaries = locations[1:]
    location_lookup = {}
    documents = []

    for loc in secondaries:
        text = f"[{loc['id']}] {loc['name']} {loc['category']} {loc['price_level']} {' '.join(loc['reviews'])}"
        documents.append(Document(page_content=text))

    vector_store.add_documents(documents=documents)

    prompt = PromptTemplate(
        input_variables=["question", "context", "count"],
        template="""
    You are a smart location recommendation agent.
    Primary Location:
    {question}

    Candidate Locations:
    {context}

    Recommend the top {count} most similar candidate locations. Return their [id] and a short reason.
    Provide a recommendation even if there is only a partial match.

    Format:
    1. [id] - Reason
    2. [id] - Reason
    ...
    """
    )

    def retrieve(state: State):
        retrieved_docs = vector_store.similarity_search(state["question"], k=5)
        count = int(state.get("count", 2))
        # retrieved_docs = [Document(
            # page_content=f"[{loc['id']}] {loc['name']} {loc['category']} {loc['price_level']} {' '.join(loc['reviews'])}")
                        # for loc in location_lookup.values()]
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

        recommended_places = [gmaps_place_index[id] for id in recommended_ids]

        matches = re.split(r'\n?\d+\.\s+', result['answer'])

        # The first element is the intro text before the list
        intro = matches[0].strip()

        # The rest are the individual recommendations
        recommendations = [entry.strip() for entry in matches[1:] if entry.strip()]

        names = [gmaps_place_index[id]['result']['name'] for id in recommended_ids]
        short_summaries = recommendations
        maps_google_links = [gmaps_place_index[id]['result']['url'] for id in recommended_ids]
        photoss = [0 for _ in recommended_ids]
        # print(gmaps_place_index[recommended_ids[0]].keys())
        coordinates = [gmaps_place_index[id]['result']['geometry']['location'] for id in recommended_ids]
        place_types = [gmaps_place_index[id]['result']['types'][0] for id in recommended_ids]
        rec_types = [2 for _ in recommended_ids]
        rag_info_ids = [0 for _ in recommended_ids]

        json_list = []
        for idx, name in enumerate(names):
            json_list.append({
                "name": names[idx],
                "short_summary": short_summaries[idx],
                "maps_google_link": maps_google_links[idx],
                "photos": photoss[idx],
                "coordinates": tuple(coordinates[idx].values()),
                "place_type": place_types[idx],
                "rec_type": rec_types[idx],
                "rag_info_id": rag_info_ids[idx]
                })
        return json_list
        # return JSONResponse({
        #     "recommended_ids": recommended_ids,
        #     "recommended_places": recommended_places,
        #     "raw_answer": recommendations
        # })
    
    return recommend(count)