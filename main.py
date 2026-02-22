from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# DEV CORS: tighten later (set specific origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
Role = Literal["system", "user", "assistant"]

class Message(BaseModel):
    role: Role
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    #temperature: Optional[float] = 0.7

# --- Simple auth gate so strangers can't burn your Azure quota ---
def require_dev_secret(x_dev_secret: Optional[str]) -> None:
    expected = os.getenv("DEV_SECRET")
    if expected and x_dev_secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/api/chat")
async def chat(req: ChatRequest, x_dev_secret: Optional[str] = Header(default=None)):
    require_dev_secret(x_dev_secret)

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")  # e.g. https://YOUR-RESOURCE.openai.azure.com
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")  # your Foundry deployment name
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")  # use what "View code" shows

    if not all([endpoint, api_key, deployment]):
        raise HTTPException(status_code=500, detail="Missing Azure env vars")

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions"
    params = {"api-version": api_version}

    payload = {
        "messages": [m.model_dump() for m in req.messages],
        #"temperature": req.temperature,
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, params=params, json=payload, headers=headers)

    # Return Azure errors clearly
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    data = r.json()
    output = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    return {"output": output, "raw": data}