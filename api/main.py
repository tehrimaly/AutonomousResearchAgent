"""
api/main.py
-----------
FastAPI server exposing the research agent via REST + Server-Sent Events.

Endpoints
---------
POST /research          — start a research job, returns SSE stream
GET  /research/{job_id} — retrieve a completed report by job ID
GET  /health            — liveness check
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.graph import graph
from agent.state import AgentState

app = FastAPI(
    title="Autonomous Research Agent",
    description="LangGraph-powered agent that decomposes queries and researches autonomously.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (swap for Redis in production)
_jobs: dict[str, dict] = {}


# ── Request / Response models ─────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    query: str
    stream: bool = True          # set False to wait for the full report


class ResearchResponse(BaseModel):
    job_id: str
    status: str
    final_report: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _initial_state(query: str) -> AgentState:
    return {
        "query": query,
        "sub_tasks": [],
        "completed_tasks": [],
        "current_task": "",
        "tool_calls": [],
        "scratchpad": "",
        "final_report": "",
        "iteration": 0,
    }


async def _stream_graph(query: str, job_id: str) -> AsyncIterator[str]:
    """Yield SSE-formatted events as the graph progresses."""
    state = _initial_state(query)
    _jobs[job_id] = {"status": "running", "final_report": None}

    try:
        async for event in graph.astream(state):
            node_name = list(event.keys())[0]
            node_state = event[node_name]

            payload = {
                "job_id": job_id,
                "node": node_name,
                "current_task": node_state.get("current_task", ""),
                "iteration": node_state.get("iteration", 0),
                "sub_tasks": node_state.get("sub_tasks", []),
                "scratchpad_tail": (node_state.get("scratchpad") or "")[-400:],
                "final_report": node_state.get("final_report") or None,
            }

            if payload["final_report"]:
                _jobs[job_id] = {"status": "complete", "final_report": payload["final_report"]}

            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0)   # yield control so the loop can flush

    except Exception as exc:
        error_payload = {"job_id": job_id, "error": str(exc)}
        _jobs[job_id] = {"status": "error", "final_report": None}
        yield f"data: {json.dumps(error_payload)}\n\n"

    yield "data: [DONE]\n\n"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/research", response_model=ResearchResponse)
async def start_research(req: ResearchRequest):
    """Start a research job.

    - If `stream=true` (default), returns a `text/event-stream` SSE response.
    - If `stream=false`, runs synchronously and returns the full report as JSON.
    """
    job_id = str(uuid.uuid4())

    if req.stream:
        return StreamingResponse(
            _stream_graph(req.query, job_id),
            media_type="text/event-stream",
            headers={
                "X-Job-ID": job_id,
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming: run to completion
    state = _initial_state(req.query)
    final: AgentState = await graph.ainvoke(state)
    _jobs[job_id] = {"status": "complete", "final_report": final["final_report"]}
    return ResearchResponse(job_id=job_id, status="complete", final_report=final["final_report"])


@app.get("/research/{job_id}", response_model=ResearchResponse)
async def get_research(job_id: str):
    """Retrieve the result of a previously started research job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ResearchResponse(
        job_id=job_id,
        status=job["status"],
        final_report=job.get("final_report"),
    )


@app.get("/health")
def health():
    return {"status": "ok", "jobs_in_memory": len(_jobs)}
