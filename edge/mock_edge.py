"""Drop-in camera/display mock; deliberately controllable failures."""
import argparse
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.contracts import DisplayPayload

app = FastAPI(title="Mock smart stop")
count, failure, latest_display = 0, "none", None


class CountCommand(BaseModel):
    count: int = Field(ge=0)


class FailCommand(BaseModel):
    mode: str


@app.get("/count")
async def read():
    if failure == "timeout":
        await asyncio.sleep(3)
    if failure == "error":
        raise HTTPException(503, "Mock camera unavailable")
    return {"count": count, "measured_at": datetime.now(timezone.utc).isoformat()}


@app.post("/display", status_code=204)
def display(payload: DisplayPayload):
    global latest_display
    latest_display = payload.model_dump(mode="json")


@app.post("/mock/count")
def set_count(payload: CountCommand):
    global count
    count = payload.count
    return {"count": count}


@app.post("/mock/fail")
def fail(payload: FailCommand):
    global failure
    if payload.mode not in {"none", "timeout", "error"}:
        raise HTTPException(422, "Invalid failure mode")
    failure = payload.mode
    return {"mode": failure}


@app.get("/mock/display")
def last_display():
    return latest_display


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
