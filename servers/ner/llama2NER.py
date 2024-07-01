#!./.env_ner/bin/python3

import os
import json

from llama_index.core import Settings
from llama_index.embeddings.gradient import GradientEmbedding
from llama_index.llms.gradient import GradientBaseModelLLM
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core import PromptTemplate

os.environ["GRADIENT_ACCESS_TOKEN"] = "BW4sZsTCZJ6enaO3wdcyxu8jwkJZsJW7"
os.environ["GRADIENT_WORKSPACE_ID"] = "dc0af1d6-5a3d-4431-bae1-bf5a5f9a01ef_workspace"

ner = dict()


def dictionarize(message, key):
    try:
        message = str(message)
        first_paren = message.index("{")
        last_paren = message.rfind("}")
        res = message[first_paren : last_paren + 1]
        json_obj = json.loads(res)
        json_obj = dict(json_obj)
        for k, v in json_obj.items():
            ner[k] = v
    except:
        ner[key] = ""


llm = GradientBaseModelLLM(
    base_model_slug="llama2-7b-chat",
    max_tokens=400,
)

embed_model = GradientEmbedding(
    gradient_access_token=os.environ["GRADIENT_ACCESS_TOKEN"],
    gradient_workspace_id=os.environ["GRADIENT_WORKSPACE_ID"],
    gradient_model_slug="bge-large",
)

Settings.llm = llm
Settings.embed_model = embed_model
chunk_size = 1024


filename = str(input())
reader = SimpleDirectoryReader(input_files=[filename])
documents = reader.load_data()


system_prompt = """
    You are a Named Entity Recognizer.
    You need to extract the given entities from the data.
    The extraction must be accurate.
    You need to give answers as only JSON.
"""

query_wrapper_prompt = PromptTemplate("<|USER|>{query_str}<|ASSISTANT|>")


index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)
query_engine = index.as_query_engine(llm=llm)


response = query_engine.query(
    """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
Candidate Name (JSON key as "name"),

and output that as JSON.
"""
)
dictionarize(response, "name")

response = query_engine.query(
    """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
Email-id (JSON key as "email", select only one),

and output that as JSON.
"""
)
dictionarize(response, "email")


response = query_engine.query(
    """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
Work Details (JSON key as "work_title", which is a list of "position" and "organisation"),

and output that as JSON.
"""
)
dictionarize(response, "work_title")

response = query_engine.query(
    """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
Work Locations (JSON key as "work_location", which is a list of all cities),

and output that as JSON.
"""
)
dictionarize(response, "work_location")


response = query_engine.query(
    """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
Technical Skills (JSON key as "tech_skills", which is a list of all technical skills like
programming languages, domain specific tools and knowledge bases),

and output that as JSON.
"""
)
dictionarize(response, "tech_skills")


response = query_engine.query(
    """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
Soft Skills (JSON key as "soft_skills", which is a list of all soft skills),

and output that as JSON.
"""
)
dictionarize(response, "soft_skills")

print(ner)
