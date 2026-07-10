"""Vision recognition via the OpenAI Codex CLI.

Instead of calling a metered vision API, this shells out to the ``codex`` CLI,
which authenticates with the user's Codex / ChatGPT subscription (``codex
login``). Codex's non-interactive ``exec`` mode accepts an image and returns a
final text message, which we constrain to a strict JSON object and parse.

The CLI must be installed and logged in on the host running the API:

    npm install -g @openai/codex   # or: brew install codex
    codex login                    # sign in with the Codex/ChatGPT account

Relevant invocation (prompt must precede flags in exec mode):
    codex exec "<prompt>" --image <file> --output-last-message <file> \\
        --sandbox read-only --skip-git-repo-check [--model <m>]

`codex exec` reuses the auth saved by `codex login` by default, so no API key
is involved when signed in with a Codex/ChatGPT subscription.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from .receipts import PHOTO_SYSTEM_PROMPT, SYSTEM_PROMPT, ParseResult, json_mode_prompt

# Codex can spin up its own reasoning; give it generous headroom but bound it so
# a hung CLI can't wedge a request forever.
CODEX_TIMEOUT_SECONDS = 180

# The final message must be machine-parseable. Codex is a coding agent, not a
# structured-output API, so we pin the response shape explicitly.
_JSON_CONTRACT = (
    'Respond with ONLY a single JSON object and nothing else — no markdown, no '
    'code fences, no explanation. Use exactly this shape:\n'
    '{"items": [{"type": "<lowercase keyword>", "count": <integer >= 1>}], '
    '"confidence": "high" | "low" | "none"}\n'
    'If there are no Red Bull products, return {"items": [], "confidence": "none"}.'
)

_EXT_BY_MEDIA = {
    "image/png": "png",
    "image/webp": "webp",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
}


class CodexError(RuntimeError):
    """Raised when the Codex CLI fails or returns unparseable output."""


def _build_prompt(mode: str) -> str:
    base = json_mode_prompt(PHOTO_SYSTEM_PROMPT if mode == "photo" else SYSTEM_PROMPT)
    task = (
        "Count the Red Bull cans visible in the attached photo."
        if mode == "photo"
        else "Parse the attached receipt image for Red Bull purchases."
    )
    return f"{base}\n\n{task}\n\n{_JSON_CONTRACT}"


def _run_codex(argv: list[str], *, cwd: str, timeout: int) -> str:
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise CodexError(
            f"codex CLI not found ({argv[0]!r}). Install it and run `codex login`."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise CodexError(f"codex timed out after {timeout}s") from e

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-500:]
        raise CodexError(f"codex exited with {proc.returncode}: {tail}")
    return proc.stdout or ""


def _last_json_object(text: str) -> dict[str, Any] | None:
    """Return the last top-level ``{...}`` in ``text`` that parses as JSON."""
    best: dict[str, Any] | None = None
    depth = 0
    start: int | None = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    parsed = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    best = parsed
                start = None
    return best


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise CodexError("codex returned empty output")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    obj = _last_json_object(text)
    if obj is not None:
        return obj

    raise CodexError(f"could not parse JSON from codex output: {text[:200]!r}")


def _sanitize_items(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for it in raw:
        if not isinstance(it, dict):
            continue
        type_ = it.get("type")
        if not isinstance(type_, str) or not type_.strip():
            continue
        try:
            count = int(it.get("count"))
        except (TypeError, ValueError):
            continue
        if count < 1:
            continue
        out.append({"type": type_.strip().lower(), "count": count})
    return out


def parse_via_codex(
    *,
    image_bytes: bytes,
    media_type: str,
    mode: str,
    codex_bin: str = "codex",
    model: str = "",
    runner: Callable[..., str] | None = None,
) -> ParseResult:
    """Recognize Red Bull cans/purchases in an image using the Codex CLI.

    ``mode`` is ``"receipt"`` or ``"photo"``. ``runner`` is injectable for tests.
    """
    run = runner or _run_codex
    ext = _EXT_BY_MEDIA.get(media_type, "jpg")

    with tempfile.TemporaryDirectory(prefix="rb-codex-") as td:
        img_path = Path(td) / f"scan.{ext}"
        img_path.write_bytes(image_bytes)
        out_path = Path(td) / "codex-last-message.txt"

        # `codex exec` uses a positional-first parser: the prompt must come
        # before the flags, otherwise it is swallowed as a flag value.
        argv = [
            codex_bin,
            "exec",
            _build_prompt(mode),
            "--image",
            str(img_path),
            "--output-last-message",
            str(out_path),
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
        ]
        if model:
            argv += ["--model", model]

        stdout = run(argv, cwd=td, timeout=CODEX_TIMEOUT_SECONDS)

        raw_text = ""
        if out_path.exists() and out_path.stat().st_size:
            raw_text = out_path.read_text(encoding="utf-8", errors="replace")
        if not raw_text.strip():
            raw_text = stdout

        data = _extract_json(raw_text)

    items = _sanitize_items(data.get("items"))
    confidence = data.get("confidence")
    if confidence not in {"high", "low", "none"}:
        confidence = "high" if items else "none"
    if not items:
        confidence = "none"

    return ParseResult(
        items=items,
        confidence=confidence,
        model_used=f"codex:{model or 'default'}",
        raw_response=data,
    )
