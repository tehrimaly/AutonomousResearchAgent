import textwrap
from langchain_core.tools import tool

try:
    import docker
    from docker.errors import ContainerError, ImageNotFound, APIError
    _DOCKER_AVAILABLE = True
except ImportError:
    _DOCKER_AVAILABLE = False


_SANDBOX_IMAGE = "python:3.11-slim"
_PREINSTALLED = (
    "import sys, os, json, math, re, datetime, collections, itertools, "
    "functools, pathlib\n"
)

# Pre-install common data-science packages into the image once.
# The agent's Docker container handles this via docker-compose.


@tool
def execute_python(code: str) -> str:
    """Execute Python code in an isolated Docker sandbox and return stdout/stderr.

    The sandbox has:
    - No network access (network_disabled=True)
    - 256 MB memory limit
    - 30-second wall-clock timeout
    - Read-only filesystem except /tmp

    Args:
        code: Valid Python source code to execute.

    Returns:
        Combined stdout and stderr from the execution.
    """
    if not _DOCKER_AVAILABLE:
        return (
            "ERROR: docker Python SDK not installed. "
            "Run: pip install docker"
        )

    # Prepend common imports so the model doesn't have to worry about them
    full_code = _PREINSTALLED + textwrap.dedent(code)

    try:
        client = docker.from_env()

        # Ensure the base image exists locally; pull if not
        try:
            client.images.get(_SANDBOX_IMAGE)
        except ImageNotFound:
            client.images.pull(_SANDBOX_IMAGE)

        container = client.containers.run(
            image=_SANDBOX_IMAGE,
            command=["python", "-c", full_code],
            mem_limit="256m",
            memswap_limit="256m",
            network_disabled=True,
            read_only=True,
            tmpfs={"/tmp": "size=64m"},
            remove=False,          # we remove manually after reading logs
            detach=True,
            stdout=True,
            stderr=True,
            user="nobody",
        )

        try:
            exit_code = container.wait(timeout=30)["StatusCode"]
        except Exception:
            container.kill()
            return "ERROR: execution timed out (30s limit)"
        finally:
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            container.remove(force=True)

        if exit_code != 0:
            return f"EXIT {exit_code}\n{logs}"
        return logs if logs.strip() else "(no output)"

    except ContainerError as exc:
        return f"ContainerError: {exc.stderr.decode() if exc.stderr else str(exc)}"
    except APIError as exc:
        return f"Docker API error: {exc}"
    except Exception as exc:
        return f"Unexpected error: {exc}"
