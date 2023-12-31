# coding=utf-8
import time
import torch
import uvicorn
from pydantic import BaseModel#, Field
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List#, Literal, Optional, Union
#from transformers import AutoTokenizer, AutoModel
#from sse_starlette.sse import EventSourceResponse
from fastapi import FastAPI, Depends, HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED
#import argparse
import tiktoken
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import PolynomialFeatures
from typing import Union

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EmbeddingProcessRequest(BaseModel):
    input: List[str]
    model: str

class EmbeddingQuestionRequest(BaseModel):
    input: str
    model: str

class EmbeddingResponse(BaseModel):
    data: list
    model: str
    object: str
    usage: dict

async def verify_token(request: Request):
    auth_header = request.headers.get('Authorization')
    if auth_header:
        token_type, _, token = auth_header.partition(' ')
        if token_type.lower() == "bearer" and token == "sk-hv6xtPbK183j3RR306Fe23B6196b4d919a8e854887F6213d": # 这里配置你的token
            return True
    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Invalid authorization credentials",
    )

def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding('cl100k_base')
    num_tokens = len(encoding.encode(string))
    return num_tokens

def expand_features(embedding, target_length):
    poly = PolynomialFeatures(degree=2)
    expanded_embedding = poly.fit_transform(embedding.reshape(1, -1))
    expanded_embedding = expanded_embedding.flatten()
    if len(expanded_embedding) > target_length:
        # 如果扩展后的特征超过目标长度，可以通过截断或其他方法来减少维度
        expanded_embedding = expanded_embedding[:target_length]
    elif len(expanded_embedding) < target_length:
        # 如果扩展后的特征少于目标长度，可以通过填充或其他方法来增加维度
        expanded_embedding = np.pad(expanded_embedding, (0, target_length - len(expanded_embedding)))
    return expanded_embedding

@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def get_embeddings(request: Union[EmbeddingProcessRequest, EmbeddingQuestionRequest]):
    #data = await request.body()
    #print(data)
    #return
    if isinstance(request, EmbeddingProcessRequest): 
        print('EmbeddingProcessRequest')
        payload = request.input
    elif isinstance(request, EmbeddingQuestionRequest): 
        print('EmbeddingQuestionRequest')
        payload = [request.input]
    else:
        print('Request')
        data = request.json()
        print(data)
        return
        
    print(payload)
    embeddings = [embeddings_model.encode(text) for text in payload]

    
    # 如果嵌入向量的维度不为1536，则使用插值法扩展至1536维度 
    #embeddings = [expand_features(embedding, 1536) if len(embedding) < 1536 else embedding for embedding in embeddings]
    
    # Min-Max normalization
    embeddings = [(embedding - np.min(embedding)) / (np.max(embedding) - np.min(embedding)) if np.max(embedding) != np.min(embedding) else embedding for embedding in embeddings]
    
    # 将numpy数组转换为列表
    embeddings = [embedding.tolist() for embedding in embeddings]
    prompt_tokens = sum(len(text.split()) for text in payload)
    total_tokens = sum(num_tokens_from_string(text) for text in payload)

    response = {
        "data": [
            {
                "embedding": embedding,
                "index": index,
                "object": "embedding"
            } for index, embedding in enumerate(embeddings)
        ],
        "model": request.model,
        "object": "list",
        "usage": {
            "prompt_tokens": prompt_tokens,
            "total_tokens": total_tokens,
        }
    }



    
    #print(response)
    
    return response



if __name__ == "__main__":
    embeddings_model = SentenceTransformer('moka-ai/m3e-base',device='cpu')

    uvicorn.run(app, host='0.0.0.0', port=6006, workers=1)
