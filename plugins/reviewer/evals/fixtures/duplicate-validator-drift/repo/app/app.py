"""Application entrypoint."""

from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health() -> str:
    return "ok"
