from dotenv import load_dotenv, dotenv_values
load_dotenv() # load .env


from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(
        model='gemini-1.5-flash',
        temperature=0,
        )

from langchain_google_genai import GoogleGenerativeAIEmbeddings
embedder = GoogleGenerativeAIEmbeddings(
        model='models/text-embedding-004',
        )

from langchain_milvus import Milvus
uri = './milvus.db'
vector_store = Milvus(
        embedding_function = embedder,
        connection_args = {'uri':uri},
        # index_params = {'index_type':'FLAT', 'metric_type':'L2'}, # idk what they do really... no docs either :(
        auto_id = True,
        )



def preprocess(text, minlinelen, maxlen):
    asciionly = ''.join([char for char in text if char.isascii()])
    linelist = [line for line in asciionly.split('\n')]
    biglines = [line for line in linelist if len(line)>=minlinelen]
    processed = ''.join(biglines)
    return processed[:maxlen]

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
def summarize(title,text):
    pretext = preprocess(text, 100, 1500) # 1500 cuz gemini can handle more
    system_template = 'You are a smart and helpful AI assistant who responds in a brief and crisp manner.'
    user_template = '{title}\n{text}\nShorten the text into a few lines:\n'
    prompt = ChatPromptTemplate.from_messages(
            [('system', system_template), ('user', user_template)]
            )
    chain = prompt | llm | StrOutputParser()
    summary = chain.invoke({'title':title, 'text':pretext})
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
from langchain_core.documents import Document
def upsert(request, summary, tag):
    doc = Document(page_content=summary, metadata={'tag':tag, 'timestamp':str(datetime.now()), 'url':request.url, 'title':request.title, 'page_text':request.text})
    # ^ used page_text instead of text cuz its reserved
    vector_store.upsert(documents=[doc], ids=vector_store.get_pks(f"url in ['{request.url}']"))
    # ^ ids didnt allow url string, so i had to fetch primary keys related to that url

def similar_links(summary):
    result = vector_store.similarity_search(query=summary, k=4)
    urls = [(item.metadata)['url'] for item in result]
    top3 =  urls[1:] # excluding the first url of summary itself !
    linktagged = [f'<br /><a href="{link}">{link}</a>' for link in top3]
    return ''.join(linktagged)



from pydantic import BaseModel
class Request(BaseModel):
    url: str
    title: str
    text: str

from fastapi import FastAPI
app = FastAPI()

@app.post('/autumn/')
async def autumn(request: Request):
    summary = summarize(request.title,request.text)
    tag = tagger(summary)
    upsert(request, summary, tag)
    toplinks = similar_links(summary)
    response = {'title':request.title, 'tag':tag, 'summary':summary, 'toplinks':toplinks}
    return response
