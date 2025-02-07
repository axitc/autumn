from langchain_ollama import ChatOllama
llm = ChatOllama(
        model='qwen2.5:0.5b',
        temperature=0,
        num_predict=128,
        cache=False,
        num_thread=4,
        #seed=0,
        #top_k=0,
        #top_p=0,
        )


from langchain_ollama import OllamaEmbeddings
embedder = OllamaEmbeddings(model='snowflake-arctic-embed:33m')


from pymilvus import MilvusClient
client = MilvusClient('milvus.db')

if not client.has_collection(collection_name='collection'):
    client.create_collection(
            collection_name='collection',
            dimension=384, # snowflake vector dimension
            )



def preprocess(text, minlinelen, maxlen):
    asciionly = ''.join([char for char in text if char.isascii()])
    linelist = [line for line in asciionly.split('\n')]
    biglines = [line for line in linelist if len(line)>=minlinelen]
    processed = ''.join(biglines)
    return processed[:maxlen]

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
def summarize(text):
    pretext = preprocess(text, 150, 1000)
    system_template = 'You are a smart and helpful AI assistant who responds in a brief and crisp manner.'
    user_template = '{text}\nShorten the text into a small paragraph:\n'
    prompt = ChatPromptTemplate.from_messages(
            [('system', system_template), ('user', user_template)]
            )
    chain = prompt | llm | StrOutputParser()
    summary = chain.invoke({'text':pretext})
    return summary

def tagger(summary):
    system_template = 'You are a classifier which categorizes input text from given list of tags. You just output tag name like BERT classifier model.'
    user_template = 'Input text: {text}\nClassify using tags : -Travel -Science -Health -Technology -Finance -History -Sports -Politics -Entertainment\nClass: '
    prompt = ChatPromptTemplate.from_messages(
            [('system', system_template), ('user', user_template)]
            )
    chain = prompt | llm | StrOutputParser()
    tag = chain.invoke({'text':summary})
    return tag

from datetime import datetime
def upsert(url, summary, tag):
    vector = embedder.embed_query(summary)
    data = [{'id':hash(url), 'vector':vector, 'text':summary, 'url':url, 'tag':tag, 'timestamp':str(datetime.now())}]
    client.upsert(collection_name='collection', data=data)

def similar_links(summary):
    query_vector = embedder.embed_query(summary)
    result = client.search(
            collection_name = 'collection',
            data = [query_vector],
            # filter = "tag == 'value'",
            limit = 4,
            output_fields = ['url'],
            )
    urls = [item['entity']['url'] for item in result[0]]
    top3 =  urls[1:] # excluding the url of summary itself !
    linktagged = [f'<br/><a href="{link}">{link}</a>' for link in top3]
    return ''.join(linktagged)



from pydantic import BaseModel
class Request(BaseModel):
    url: str
    title: str
    text: str

from fastapi import FastAPI
app = FastAPI()

@app.post('/summer/')
async def summer(request: Request):
    summary = summarize(request.text)
    tag = tagger(summary)
    upsert(request.url, summary, tag)
    toplinks = similar_links(summary)
    response = {'title':request.title, 'tag':tag, 'summary':summary, 'toplinks':toplinks}
    return response
