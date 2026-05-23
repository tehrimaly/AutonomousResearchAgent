# Autonomous Research Agent

> An advanced AI agent that autonomously researches any topic — breaking queries into sub-tasks, searching the web, executing code in a sandboxed Docker container, and synthesizing a final report. Built with **LangGraph**, **Google Gemini**, **FastAPI**, and **Docker**.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2.28-green?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal?style=flat-square)
![Gemini](https://img.shields.io/badge/Google-Gemini-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)

---

## What It Does

You type a research question. The agent figures out the rest — no human intervention needed at each step.

**The agent autonomously:**
1.  Breaks your question into 3–5 focused sub-tasks (Planner)
2.  Searches the web for each sub-task using Playwright + DuckDuckGo
3.  Writes and runs Python code in an isolated Docker container
4.  Stores findings in a semantic memory layer (ChromaDB)
5.  Synthesizes everything into a structured final report
6.  Streams every step live to a real-time dashboard UI

---

##  Architecture

```
User Query
    │
    ▼
┌─────────────┐
│   Planner   │  ← Gemini decomposes query into 3-5 sub-tasks
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────┐
│          ReAct Loop              │
│   Think → Tool Call → Observe   │  ← Repeats until TASK_COMPLETE
│                                  │
│   Tools available:               │
│   • web_search  (Playwright)     │
│   • execute_python  (Docker)     │
│   • write_file  (disk)           │
└──────┬───────────────────────────┘
       │  (all sub-tasks complete)
       ▼
┌─────────────┐
│ Synthesizer │  ← Merges all findings into final report
└──────┬──────┘
       │
       ▼
FastAPI SSE Stream → Real-time Dashboard UI
```

---

##  Quick Start

### Prerequisites
- Python 3.11+
- Docker Desktop (for sandboxed code execution)
- Google Gemini API key — **free** at [aistudio.google.com](https://aistudio.google.com)

### 1. Clone the repo
```bash
git clone https://github.com/tehrimaly/autonomous-research-agent.git
cd autonomous-research-agent
```

### 2. Set up environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
playwright install chromium
```

### 3. Add your API key
```bash
# Create .env file
echo "GOOGLE_API_KEY=your-key-here" > .env
```

### 4. Start the server
```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Open the UI
Open `research_agent_ui.html` in your browser, type a question, and hit **Run**!

---

##  Project Structure

```
autonomous-research-agent/
├── agent/
│   ├── graph.py           # LangGraph state machine (the brain)
│   ├── planner.py         # Decomposes query into sub-tasks
│   ├── synthesizer.py     # Merges findings into final report
│   └── state.py           # Shared TypedDict state schema
├── tools/
│   ├── web_search.py      # Playwright + DuckDuckGo with retries
│   ├── code_executor.py   # Docker-sandboxed Python runner
│   └── file_writer.py     # Saves intermediate findings to disk
├── memory/
│   └── store.py           # ChromaDB semantic memory layer
├── api/
│   └── main.py            # FastAPI server with SSE streaming
├── docker/
│   └── sandbox.Dockerfile # Isolated code execution container
├── tests/
│   └── test_graph.py
├── research_agent_ui.html # Real-time dashboard
├── requirements.txt
└── .env.example
```

---

##  Key Technical Decisions

| Decision | Why |
|----------|-----|
| **LangGraph** state machine | Explicit control flow; deterministic routing between loop/next-task/synthesize |
| **ReAct pattern** | Agent reasons before and after every tool call — far more reliable than one-shot prompting |
| **Docker sandbox** | Prevents prompt-injection attacks from running malicious code or leaking data |
| **SSE streaming** | Client sees agent reasoning in real time — feels interactive even on 60s queries |
| **ChromaDB memory** | Semantic search lets agent retrieve relevant past findings to avoid redundant searches |
| **DuckDuckGo** (no API key) | Zero cost; sufficient for most research tasks |

---

##  Running Tests

```bash
# Unit tests only (no API key needed)
pytest tests/ -v -m "not integration"

# All tests including end-to-end
pytest tests/ -v
```

---

##  Docker Compose

```bash
docker compose up --build
```

Starts the agent on port 8000 with outputs mounted at `./outputs` and ChromaDB persisted at `./chroma_db`.

---

## Resume Bullets

```
Autonomous Research Agent | Python · LangGraph · Google Gemini · Docker · FastAPI

• Designed a multi-step autonomous AI agent using a ReAct (Reason + Act) loop
  with LangGraph, capable of decomposing open-ended research queries into
  parallel sub-tasks without human intervention at each step.

• Built a Docker-sandboxed Python code execution tool with full network
  isolation, preventing prompt-injection-driven code from exfiltrating data
  or calling external services.

• Implemented server-sent event (SSE) streaming via FastAPI so clients
  observe agent reasoning in real time, reducing perceived latency from
  ~60s to an interactive feel.

• Integrated a ChromaDB semantic memory layer enabling the agent to retrieve
  relevant past findings across iterations, reducing redundant tool calls.
```

---

##  Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Model | Google Gemini 1.5 Flash |
| Agent Framework | LangGraph 0.2, LangChain 0.3 |
| Backend | FastAPI, Uvicorn, Python 3.11 |
| Web Scraping | Playwright, BeautifulSoup4 |
| Code Execution | Docker SDK (sandboxed) |
| Memory | ChromaDB (vector store) |
| Frontend | HTML/CSS/JS + SSE streaming |

---

