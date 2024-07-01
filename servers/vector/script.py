'''
Requirements

pip install langchain
pip install bitsandbytes accelerate xformers einops
pip install datasets loralib sentencepiece
pip install sentence_transformers
pip install chromadb

'''


# To use custom embedding model in ChromaDB
    
    import chromadb
    from chromadb.db.base import UniqueConstraintError
    from chromadb.utils import embedding_functions
    client = chromadb.PersistentClient(path="db/")  # data stored in 'db' folder
    default_ef = embedding_functions.DefaultEmbeddingFunction() # default embedding
    em = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="Huffon/sentence-klue-roberta-base")
    try:
        collection = client.create_collection(name='article', embedding_function=em)
    except UniqueConstraintError:  # already exist collection
        collection = client.get_collection(name='article', embedding_function=em)

#  Setting up ChromaDB as our Vector Database
    
    vectordb=Chroma.from_documents(document_chunks,embedding=embeddings, persist_directory='./data')

# Downloading the Llama2 chat model from Huggingface 
    
    tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-2-7b-chat-hf",
                                             use_auth_token=True,)

    model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b-chat-hf",
                                                device_map='auto',
                                                 torch_dtype=torch.float16,
                                                use_auth_token=True,
                                                #load_in_8bit=True,
                                                load_in_4bit=True
                                                 )
#  Creating a Huggingface Pipeline
    
    pipe=pipeline("text-generation",
                 model=model,
                tokenizer=tokenizer,
                torch_dtype=torch.bfloat16,
                 device_map='auto',
                 max_new_tokens=512,
                min_new_tokens=-1,
                 top_k=30
                 )
    
    llm=HuggingFacePipeline(pipeline=pipe, model_kwargs={'temperature':0})
    llm=ChatOpenAI(temperature=0.7, model_name='gpt-3.5-turbo')
    llm

#  Creating a memory object to hold a conversation

    memory=ConversationBufferMemory(memory_key='chat_history', return_messages=True)

# Creating a QA chain
    
    pdf_qa=ConversationalRetrievalChain.from_llm(llm=llm,
                                                 retriever=vectordb.as_retriever(search_kwargs={'k':6}),
                                                 verbose=False, memory=memory)
    result=pdf_qa({"question":"YOLOv7 is trained on which dataset"})
    result['answer']
