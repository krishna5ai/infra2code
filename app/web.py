from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .generator import generate

app = FastAPI(title="Infra2Code AI")


class Brief(BaseModel):
    requirement: str = Field(min_length=10, max_length=4000)
    env: Literal["dev", "prod"] = "dev"


@app.post("/api/generate")
def generate_api(brief: Brief):
    try:
        return generate(brief.requirement, "aws", brief.env)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# serves static/index.html at http://127.0.0.1:8000
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "static", html=True))