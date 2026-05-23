# Autonomous Research Agent

An advanced AI agent built with **LangGraph**, **Anthropic Claude**, and **FastAPI** that autonomously researches any topic by decomposing it into sub-tasks, searching the web, executing Python code in a sandboxed Docker container, and synthesizing a final report — all in a self-directed ReAct loop.

---

## Architecture

```
User Query
   │
   ▼
Planner Node         ← decomposes query into 3-5 sub-tasks
   │
   ▼
ReAct Loop ──────────────────────────────────────┐
│  Think  →  Act (tool call)  →  Observe         │
│      └──────────────────────────────┘          │
│  Tools: web_search | execute_python | write_file│
└─────────────────────────────────────────────────┘
   │ (all sub-tasks complete)
   ▼
Synthesizer Node     ← merges findings → final report
   │
   ▼
FastAPI SSE Stream   ← streams every node update to the client
```

---

## Quick Start

### 1. Clone & configure

```bash
git clone <your-repo>
cd research_agent
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Pre-build the code sandbox image

```bash
docker build -f docker/sandbox.Dockerfile -t python:3.11-slim-sandbox docker/
```

### 4. Run the API server

```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Send a research request

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the top 3 Python ML libraries by GitHub stars in 2025?"}' \
  --no-buffer
```

You will see a stream of JSON events as the agent thinks, uses tools, and writes its report.

---

## Running with Docker Compose

```bash
docker compose up --build
```

This starts the agent API on port 8000 with:
- Outputs mounted at `./outputs`
- ChromaDB persisted at `./chroma_db`
- Docker socket mounted so the agent can spawn sandbox containers

---

## Running tests

```bash
# Unit tests only (no API key needed)
pytest tests/ -v -m "not integration"

# All tests including end-to-end (requires ANTHROPIC_API_KEY)
pytest tests/ -v
```

---

## Project structure

```
research_agent/
├── agent/
│   ├── graph.py          ← LangGraph state machine (ReAct loop)
│   ├── planner.py        ← query decomposition
│   ├── synthesizer.py    ← report generation
│   └── state.py          ← shared TypedDict state schema
├── tools/
│   ├── web_search.py     ← Playwright + DuckDuckGo with retries
│   ├── code_executor.py  ← Docker-sandboxed Python runner
│   └── file_writer.py    ← persistent intermediate file store
├── memory/
│   └── store.py          ← ChromaDB semantic memory layer
├── api/
│   └── main.py           ← FastAPI + SSE streaming server
├── docker/
│   └── sandbox.Dockerfile
├── tests/
│   └── test_graph.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Key design decisions

| Decision | Why |
|---|---|
| LangGraph state machine | Explicit control flow; easy to add/remove nodes; built-in streaming |
| ReAct loop (Think → Act → Observe) | Agent reasons before and after each tool call — far more reliable than one-shot |
| Docker code sandbox | Prevents prompt-injection attacks from causing the agent to exfiltrate data or call external APIs |
| SSE streaming | Client sees agent reasoning in real time; UX feels interactive even on 60-second queries |
| ChromaDB memory | Agent can retrieve relevant past findings to avoid redundant searches |
| DuckDuckGo (no API key) | Zero cost; good enough for most research tasks |

---

## Resume bullets

```
Autonomous Research Agent | Python, LangGraph, Anthropic API, Docker, FastAPI

• Designed and implemented a multi-step autonomous AI agent using a ReAct
  (Reason + Act) loop with LangGraph, capable of decomposing open-ended
  research queries into sub-tasks and self-directing tool use without human
  intervention at each step.

• Built a Docker-sandboxed Python code execution tool with full network
  isolation (network_disabled=True, read-only filesystem), preventing
  prompt-injection-driven code from exfiltrating data.

• Implemented SSE streaming via FastAPI so clients observe agent reasoning
  in real time, reducing perceived latency from ~60s to interactive feel.

• Integrated a ChromaDB semantic memory layer enabling the agent to retrieve
  relevant past findings across iterations, reducing redundant tool calls.

• Achieved X% task-completion rate on a Y-query benchmark (fill in after
  you run your own eval).
```
