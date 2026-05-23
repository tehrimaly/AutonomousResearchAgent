"""
tests/test_graph.py
-------------------
Unit and integration tests for the research agent.

Run with:   pytest tests/ -v
Fast mode:  pytest tests/ -v -m "not integration"
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# ── Planner tests ─────────────────────────────────────────────────────────────

class TestPlanner:
    def test_planner_returns_list_of_strings(self):
        """Planner should decompose a query into at least 2 sub-tasks."""
        from agent.planner import planner_node
        from agent.state import AgentState

        mock_response = MagicMock()
        mock_response.content = json.dumps([
            "What is the history of Python?",
            "What are Python's main use cases today?",
            "Who maintains Python?",
        ])

        initial: AgentState = {
            "query": "Tell me about Python",
            "sub_tasks": [], "completed_tasks": [], "current_task": "",
            "tool_calls": [], "scratchpad": "", "final_report": "", "iteration": 0,
        }

        with patch("agent.planner.llm") as mock_llm:
            mock_llm.invoke.return_value = mock_response
            # Patch the chain invoke
            with patch("agent.planner.PLANNER_PROMPT.__or__") as mock_pipe:
                mock_chain = MagicMock()
                mock_chain.invoke.return_value = mock_response
                mock_pipe.return_value = mock_chain

                result = planner_node(initial)

        assert isinstance(result["sub_tasks"], list)
        assert len(result["sub_tasks"]) >= 2
        assert result["current_task"] == result["sub_tasks"][0]

    def test_planner_strips_markdown_fences(self):
        """Planner should handle models that wrap JSON in ```json fences."""
        from agent.planner import planner_node
        from agent.state import AgentState

        raw = '```json\n["Task A", "Task B"]\n```'
        mock_response = MagicMock()
        mock_response.content = raw

        initial: AgentState = {
            "query": "Test query", "sub_tasks": [], "completed_tasks": [],
            "current_task": "", "tool_calls": [], "scratchpad": "",
            "final_report": "", "iteration": 0,
        }

        with patch("agent.planner.PLANNER_PROMPT.__or__") as mock_pipe:
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_response
            mock_pipe.return_value = mock_chain
            result = planner_node(initial)

        assert result["sub_tasks"] == ["Task A", "Task B"]


# ── Tool tests ────────────────────────────────────────────────────────────────

class TestWebSearch:
    def test_returns_string(self):
        from tools.web_search import web_search
        with patch("tools.web_search._search_requests") as mock_search:
            mock_search.return_value = "[1] Python — python.org\nPython is a language."
            with patch("tools.web_search._PLAYWRIGHT_AVAILABLE", False):
                with patch("tools.web_search._REQUESTS_AVAILABLE", True):
                    result = web_search.invoke({"query": "Python programming"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_retries_on_failure(self):
        from tools.web_search import web_search
        call_count = {"n": 0}

        def flaky(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionError("timeout")
            return "Success result"

        with patch("tools.web_search._PLAYWRIGHT_AVAILABLE", False):
            with patch("tools.web_search._REQUESTS_AVAILABLE", True):
                with patch("tools.web_search._search_requests", side_effect=flaky):
                    with patch("time.sleep"):   # don't actually sleep in tests
                        result = web_search.invoke({"query": "test"})

        assert result == "Success result"
        assert call_count["n"] == 3


class TestCodeExecutor:
    def test_sandbox_network_disabled(self):
        """The sandbox container must have network_disabled=True."""
        from tools.code_executor import execute_python

        run_kwargs: dict = {}

        def capture_run(**kwargs):
            run_kwargs.update(kwargs)
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = b"ok\n"
            return mock_container

        with patch("tools.code_executor._DOCKER_AVAILABLE", True):
            with patch("tools.code_executor.docker.from_env") as mock_docker:
                client = MagicMock()
                mock_docker.return_value = client
                client.images.get.return_value = MagicMock()
                client.containers.run.side_effect = lambda image, **kw: capture_run(**kw)
                execute_python.invoke({"code": "print('hello')"})

        assert run_kwargs.get("network_disabled") is True, \
            "Sandbox MUST have network_disabled=True"

    def test_returns_stdout(self):
        from tools.code_executor import execute_python

        with patch("tools.code_executor._DOCKER_AVAILABLE", True):
            with patch("tools.code_executor.docker.from_env") as mock_docker:
                client = MagicMock()
                mock_docker.return_value = client
                client.images.get.return_value = MagicMock()
                mock_container = MagicMock()
                mock_container.wait.return_value = {"StatusCode": 0}
                mock_container.logs.return_value = b"hello world\n"
                client.containers.run.return_value = mock_container

                result = execute_python.invoke({"code": "print('hello world')"})

        assert "hello world" in result


class TestFileWriter:
    def test_write_and_read(self, tmp_path):
        import os
        os.environ["OUTPUT_DIR"] = str(tmp_path)

        # Re-import to pick up new env var
        import importlib
        import tools.file_writer as fw
        importlib.reload(fw)

        write_result = fw.write_file.invoke({
            "filename": "test.txt",
            "content": "Hello agent memory",
            "metadata": {"source": "unit test"},
        })
        assert "Written to" in write_result

        read_result = fw.read_file.invoke({"filename": "test.txt"})
        assert "Hello agent memory" in read_result

    def test_prevents_path_traversal(self, tmp_path):
        import os
        os.environ["OUTPUT_DIR"] = str(tmp_path)
        import importlib
        import tools.file_writer as fw
        importlib.reload(fw)

        result = fw.write_file.invoke({
            "filename": "../../etc/passwd",
            "content": "malicious",
        })
        # Should write to tmp_path only, not escape
        import pathlib
        written_files = list(pathlib.Path(tmp_path).glob("*passwd*"))
        assert len(written_files) <= 1
        if written_files:
            assert written_files[0].parent == tmp_path


# ── Memory tests ──────────────────────────────────────────────────────────────

class TestMemoryStore:
    def test_store_and_search(self):
        from memory import store, search, clear, count
        clear()
        assert count() == 0

        store("Python is a high-level programming language", {"tag": "intro"})
        store("NumPy is a library for numerical computing in Python", {"tag": "library"})

        results = search("numerical computing", k=2)
        assert len(results) >= 1
        texts = [r["text"] for r in results]
        assert any("NumPy" in t or "numerical" in t for t in texts)
        clear()

    def test_clear_empties_store(self):
        from memory import store, clear, count
        clear()
        store("some finding")
        store("another finding")
        assert count() == 2
        clear()
        assert count() == 0


# ── Graph routing tests ───────────────────────────────────────────────────────

class TestGraphRouting:
    def _base_state(self, **overrides):
        base = {
            "query": "test", "sub_tasks": ["t1", "t2"], "completed_tasks": [],
            "current_task": "t1", "tool_calls": [], "scratchpad": "",
            "final_report": "", "iteration": 0,
        }
        base.update(overrides)
        return base

    def test_should_continue_when_no_task_complete(self):
        from agent.graph import should_continue
        state = self._base_state(scratchpad="Still thinking...", iteration=2)
        assert should_continue(state) == "continue"

    def test_moves_to_next_task_when_complete(self):
        from agent.graph import should_continue
        state = self._base_state(
            scratchpad="...\nTASK_COMPLETE\n{\"findings\": \"done\"}",
            iteration=1,
        )
        assert should_continue(state) == "next_task"

    def test_synthesizes_when_all_tasks_done(self):
        from agent.graph import should_continue
        state = self._base_state(
            sub_tasks=["t1"],
            completed_tasks=[],
            current_task="t1",
            scratchpad="TASK_COMPLETE\n{}",
            iteration=1,
        )
        assert should_continue(state) == "synthesize"

    def test_force_completes_on_max_iterations(self):
        from agent.graph import should_continue, MAX_ITERATIONS
        state = self._base_state(
            scratchpad="still going...",
            iteration=MAX_ITERATIONS,
        )
        result = should_continue(state)
        assert result in ("next_task", "synthesize")


# ── Integration test (requires real API key) ──────────────────────────────────

@pytest.mark.integration
def test_end_to_end_short_query():
    """Run the full graph on a simple query. Requires ANTHROPIC_API_KEY in env."""
    from agent.graph import graph

    state = graph.invoke({
        "query": "What is 2 + 2? Provide a one-sentence answer.",
        "sub_tasks": [], "completed_tasks": [], "current_task": "",
        "tool_calls": [], "scratchpad": "", "final_report": "", "iteration": 0,
    })

    assert state["final_report"] != "", "Final report should not be empty"
    assert "4" in state["final_report"] or "four" in state["final_report"].lower()
