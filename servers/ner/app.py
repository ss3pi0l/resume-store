#!./.env_ner/bin/python3

import os
import json
import requests

from llama_index.core import Settings
from llama_index.embeddings.gradient import GradientEmbedding
from llama_index.llms.gradient import GradientBaseModelLLM
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core import PromptTemplate

from flask import Flask, request, jsonify

import chromadb

os.environ["GRADIENT_ACCESS_TOKEN"] = "BW4sZsTCZJ6enaO3wdcyxu8jwkJZsJW7"
os.environ["GRADIENT_WORKSPACE_ID"] = "dc0af1d6-5a3d-4431-bae1-bf5a5f9a01ef_workspace"

os.environ["NO_PROXY"] = "127.0.0.1"

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
        # this is triggered when the llm is not able to create an entity
        # that is, when ner[key] = ""
        if key == "work_title":
            ner[key] = [{"position": "", "organisation": ""}]
        elif key in ("work_location", "tech_skills", "soft_skills"):
            ner[key] = [""]
        elif key == "summary":
            s = "The candidate is skilled at: "
            for i in ner["tech_skills"]:
                s = s + i + ", "
            s += ". "
            for i in ner["soft_skills"]:
                s = s + i + ", "
            s += "."
            ner["summary"] = s
        else:
            ner[key] = ""


def sanitize(d):
    print("Sanitising the parsed named entities")
    ner_list = (
        "name",
        "email",
        "work_title",
        "work_location",
        "tech_skills",
        "soft_skills",
        "summary",
    )
    for k in list(d):
        if k not in ner_list:
            del d[k]


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

client = chromadb.PersistentClient(path="../../db/")
client.heartbeat()
collection = client.get_or_create_collection(name="candidate_dataset")

app = Flask(__name__)


@app.route("/sendusername", methods=["POST"])
def receive_user_name():
    global username
    username = request.data.decode("utf-8")
    username = str(username)
    print("Received text data:", username)
    print(username)
    return "Data received", 200


@app.route("/uploadresume_toNER", methods=["POST"])
def upload_pdf():
    if request.method == "POST":
        print(request.files)
        pdf_file = request.files["file"]
        # Save the PDF file to the server's filesystem
        upload_folder = "tmp"
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        pdf_path = os.path.join(upload_folder, "uploaded.pdf")
        pdf_file.save(pdf_path)

        reader = SimpleDirectoryReader(input_files=[r"./tmp/uploaded.pdf"])
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

        print("Parsing name")
        response = query_engine.query(
            """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
        Candidate Name (JSON key as "name"),

        and output that as JSON.
        """
        )
        dictionarize(response, "name")

        print("Parsing email id")
        response = query_engine.query(
            """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
        Email-id (JSON key as "email", select only one),

        and output that as JSON.
        """
        )
        dictionarize(response, "email")

        print("Parsing work titles")
        response = query_engine.query(
            """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
        Work Details (JSON key as "work_title", which is a list of "position" and "organisation"),

        and output that as JSON.
        """
        )
        dictionarize(response, "work_title")

        print("Parsing work locations")
        response = query_engine.query(
            """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
        Work Locations (JSON key as "work_location", which is a list of all cities),

        and output that as JSON.
        """
        )
        dictionarize(response, "work_location")

        print("Parsing tech skills")
        response = query_engine.query(
            """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
        Technical Skills (JSON key as "tech_skills", which is a list of all technical skills like
        programming languages, domain specific tools and knowledge bases. This should not 
        include any soft skills),

        and output that as JSON.
        """
        )
        dictionarize(response, "tech_skills")

        print("Parsing soft skills")
        response = query_engine.query(
            """From {SOME REFERENCE OF THE DOCUMENT}, Extract the following entities
        Soft Skills (JSON key as "soft_skills", which is a list of all soft skills.
        These should not contain tech skills.),

        and output that as JSON.
        """
        )
        dictionarize(response, "soft_skills")

        print("Generating a summary")
        response = query_engine.query(
            """From {SOME REFERENCE OF THE DOCUMENT}, generate a big summary of the document
            such that it covers all the document. The generated summary should be about 200 words
            long. It is compulsory to generate the summary. 

        and output that as JSON.
        """
        )
        dictionarize(response, "summary")

        sanitize(ner)
        # print(json.dumps(ner, indent=4))  # for logging purposes, can be commented out

        ##### the following code was tried and tested for sending to api using http post
        ##### but i could not get it to work
        ##### hence saving to file and then unmarshalling through API approach was taken
        # print("Serialising the NER")
        # j = json.dumps(ner)
        # print("Sending it to API")

        print("Saving the data")
        with open(r"./tmp/ner.json", "w") as fp:
            json.dump(ner, fp)

        print("Cleaning the parsed data and creating embeddings")
        summary = ner["summary"]
        chroma_ner = dict()
        chroma_ner["name"] = ner["name"]
        chroma_ner["email"] = ner["email"]
        work_location_string = ""
        for i in ner["work_location"]:
            work_location_string += i + ", "
        chroma_ner["work_location"] = work_location_string
        tech_string = ""
        for i in ner["tech_skills"]:
            tech_string += i + ", "
        chroma_ner["tech_skills"] = tech_string
        soft_string = ""
        for i in ner["soft_skills"]:
            soft_string += i + ", "
        chroma_ner["soft_skills"] = soft_string
        work_title_string = ""
        for i in ner["work_title"]:
            work_title_string += (
                "Worked as " + i["position"] + " at " + i["organisation"] + ". "
            )
        chroma_ner["work_title"] = work_title_string

        print("Uploading the parsed data to the vector database")
        collection.upsert(ids=[username], metadatas=[chroma_ner], documents=[summary])
        print(collection.peek())

        url = "http://localhost:8080/receive-ner"
        response = requests.post(url, json=json.dumps(ner))
        print(response.text)

        return jsonify(ner)

    else:
        print("Something went wrong...")
        return


@app.route("/ner-query", methods=["POST"])
def submit_query():
    data = request.get_json()
    # user_query = data.get("query")

    # Process the query and generate a response
    # response = "Flask says hi!" + data
    print("\nRecieved query: ", data, "\n")
    query = data["query"]
    print("Query for chroma: ", query, "\n")

    client.heartbeat()
    results = collection.query(query_texts=[query], n_results=2)
    fetched_docs = list()
    no_docs = len(results["ids"][0])
    for i in range(no_docs):
        matching = {}
        matching["chroma_id"] = results["ids"][0][i]
        matching["info"] = results["documents"][0][i]
        # matching_json = json.dumps(matching)
        # fetched_docs.append(matching_json)
        fetched_docs.append(matching)
    # fetched_docs = json.dumps(fetched_docs)
    print(fetched_docs)
    # print(jsonify(fetched_docs))
    # return jsonify(fetched_docs)
    return jsonify(fetched_docs)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
