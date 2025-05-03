import os
import re
import uuid
import json
from typing import List

import faiss
from fastapi import FastAPI, Request
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

API_KEY = "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"

if not os.environ.get("NVIDIA_API_KEY"):
    os.environ["NVIDIA_API_KEY"] = API_KEY

app = FastAPI()

# ---------- Data ----------

def get_locations():
    return [
        {"name": "Cafe Bliss", "price_level": 3, "category": "cafe", "reviews": ["Great atmosphere", "Best coffee in town"], "tags": ["cozy", "organic", "wifi"]},
        {"name": "Urban Grind", "price_level": 2, "category": "cafe", "reviews": ["Good for remote work", "Affordable"], "tags": ["wifi", "remote-friendly", "cheap"]},
        {"name": "Bean There", "price_level": 3, "category": "cafe", "reviews": ["Nice ambience", "Great coffee"], "tags": ["cozy", "wifi"]},
        {"name": "Sunset Bar", "price_level": 4, "category": "bar", "reviews": ["Amazing cocktails", "Great rooftop view"], "tags": ["rooftop", "sunset", "romantic"]},
        {"name": "Vegan Delight", "price_level": 3, "category": "restaurant", "reviews": ["Delicious vegan meals", "Friendly staff"], "tags": ["vegan", "healthy", "eco-friendly"]},
        {"name": "Techie's Brew", "price_level": 2, "category": "cafe", "reviews": ["Fast wifi", "Great for coding"], "tags": ["tech-friendly", "outlets", "wifi"]},
        {"name": "The Rustic Fork", "price_level": 3, "category": "restaurant", "reviews": ["Home-style meals", "Comfort food heaven"], "tags": ["comfort food", "family-friendly", "classic"]},
        {"name": "Night Owl Espresso", "price_level": 2, "category": "cafe", "reviews": ["Open late", "Strong coffee"], "tags": ["late-night", "espresso", "study spot"]},
        {"name": "Bloom Garden Bistro", "price_level": 4, "category": "restaurant", "reviews": ["Charming garden seating", "Perfect for brunch"], "tags": ["outdoor", "brunch", "aesthetic"]},
        {"name": "Hops & Crafts", "price_level": 3, "category": "bar", "reviews": ["Great local beers", "Relaxed vibe"], "tags": ["craft beer", "casual", "hangout"]},
        {"name": "Minimalist Mug", "price_level": 3, "category": "cafe", "reviews": ["Scandinavian design", "Quiet and clean"], "tags": ["minimalist", "design", "calm"]},
        {"name": "Sizzle Grill", "price_level": 4, "category": "restaurant", "reviews": ["Juicy steaks", "Modern interior"], "tags": ["steakhouse", "grill", "modern"]}
    ]

class State(TypedDict):
    question: str
    count: str
    context: List[Document]
    answer: str

llm = init_chat_model("meta/llama3-70b-instruct", model_provider="nvidia")
embeddings = NVIDIAEmbeddings(model="NV-Embed-QA")
embedding_dim = len(embeddings.embed_query("hello world"))
index = faiss.IndexFlatL2(embedding_dim)
vector_store = FAISS(embedding_function=embeddings, index=index, docstore=InMemoryDocstore(), index_to_docstore_id={})

locations = get_locations()
primary = locations[0]
secondaries = locations[1:]
location_lookup = {}
documents = []

for loc in secondaries:
    loc_id = str(uuid.uuid4())
    loc["id"] = loc_id
    location_lookup[loc_id] = loc
    text = f"[{loc_id}] {loc['name']} {loc['category']} {loc['price_level']} {' '.join(loc['reviews'])} {' '.join(loc['tags'])}"
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

Recommend the top {count} similar locations. Return their [id] and a short reason.
Give a response even if the location does not match fully.

Format:
1. [location_id] - Reason
2. [location_id] - Reason
...
"""
)


def retrieve(state: State):
    # retrieve_docs = vector_store.similarity_search(state["question"], k=5)
    retrieved_docs = [Document(
        page_content=f"[{loc['id']}] {loc['name']} {loc['category']} {loc['price_level']} {' '.join(loc['reviews'])} {' '.join(loc['tags'])}")
                      for loc in location_lookup.values()]
    return {"context": retrieved_docs}

def generate(state: State):
    docs_content = "\n\n".join(doc.page_content for doc in state["context"])
    count = int(state.get("count", 3))
    messages = prompt.invoke({"question": state["question"], "context": docs_content, "count": str(count)})
    response = llm.invoke(messages)
    return {"answer": response.content}

graph_builder = StateGraph(State).add_sequence([retrieve, generate])
graph_builder.add_edge(START, "retrieve")
graph = graph_builder.compile()

class RecommendRequest(BaseModel):
    pass  # Placeholder if you want future extensions

@app.get("/recommend")
async def recommend(count: int = 3):
    primary_text = f"{primary['category']} {primary['price_level']} {' '.join(primary['reviews'])} {' '.join(primary['tags'])}"
    result = graph.invoke({"question": primary_text, "context": [], "answer": "", "count": str(count)})

    recommended_ids = re.findall(r"\[(.*?)\]", result["answer"])
    # recommended_locations = [location_lookup[loc_id] for loc_id in recommended_ids if loc_id in location_lookup]

    return JSONResponse({
        "recommended_ids": recommended_ids,
        # "raw_answer": result["answer"]
    })
