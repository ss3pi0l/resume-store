#!./.env_vector/bin/python
# from langchain_community.document_loaders import JSONLoader
import chromadb

import json

# from pathlib import Path
from pprint import pprint

client = chromadb.PersistentClient(path="../../db/")
client.heartbeat()
# collection = client.create_collection(name="candidate_dataset")
# collection = client.get_collection(name="candidate_dataset")
# collection = client.get_or_create_collection(name="candidate_dataset")
client.delete_collection(name="candidate_dataset")
# # loader = JSONLoader(
# #     file_path="../ner/tmp/ner.json",
# #     jq_schema=".name.email.work_title.tech_skills.soft_skills.summary",
# # )
# # data = loader.load()
# # pprint(data)
# with open("../ner/tmp/ner.json") as json_file:
#     data = json.load(json_file)
#
# pprint(data)

# collection.upsert(data)

#
# def query_chromadb(query):
#     query_embeddings = generate_embeddings(query)
#     return query_embeddings
#
# print(query_chromadb("Find resumes with experience in civil engineering"))
#
# print(collection.peek())
# print("\n\n\n")
# query_results = collection.query(
#     query_texts=["Find a candidate with experience in civil engineering"], n_results=1
# )
# print(query_results)
