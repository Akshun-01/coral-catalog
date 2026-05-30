import json
import os
import re
import subprocess
import threading
import time
import uuid
import urllib.error
import urllib.request

from dotenv import load_dotenv
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from groq import Groq

load_dotenv(override=True)
groq_api_key = os.getenv("GROQ_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

DEMO_DIR = Path(__file__).resolve().parent
ROOT = DEMO_DIR.parent
OPTIMIZED = ROOT / "optimized_catalog"
DEFAULT_PORT = 8765
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_TOOL_OUTPUT_CHARS = 12000
MAX_AGENT_STEPS = 14

RUNS = {}
RUNS_LOCK = threading.Lock()


def now_ms():
    return int(time.time() * 1000)


def read_text(path):
    return path.read_text(encoding="utf-8")


def run_coral_json(sql):
    result = subprocess.run(
        ["coral", "sql", "--format", "json", sql],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout.strip() or "[]"


def coral_rows(sql):
    return json.loads(run_coral_json(sql))


def selected_source_filter(sources):
    quoted = ", ".join("'" + source.replace("'", "''") + "'" for source in sources)
    return quoted or "''"


def list_sources():
    rows = coral_rows(
        "SELECT schema_name, COUNT(*) AS table_count "
        "FROM coral.tables GROUP BY schema_name ORDER BY schema_name"
    )
    groq_configured = bool(groq_api_key)
    gemini_configured = bool(gemini_api_key)
    default_provider = "gemini" if gemini_configured else "groq"
    return {
        "providerConfigured": groq_configured or gemini_configured,
        "groqConfigured": groq_configured,
        "geminiConfigured": gemini_configured,
        "defaultProvider": default_provider,
        "defaultModel": DEFAULT_GEMINI_MODEL if default_provider == "gemini" else DEFAULT_GROQ_MODEL,
        "models": {
            "groq": DEFAULT_GROQ_MODEL,
            "gemini": DEFAULT_GEMINI_MODEL,
        },
        "sources": [
            {
                "name": row["schema_name"],
                "tableCount": row["table_count"],
                "catalogAvailable": (OPTIMIZED / "sources" / f"{row['schema_name']}.md").exists(),
            }
            for row in rows
        ],
    }


def load_catalog_context(sources):
    parts = []
    index_path = OPTIMIZED / "catalog_index.md"
    if index_path.exists():
        parts.append("# Optimized Catalog Index\n" + read_text(index_path))

    for source in sources:
        page = OPTIMIZED / "sources" / f"{source}.md"
        if page.exists():
            parts.append(f"# Source Page: {source}\n" + read_text(page))

    recipes = OPTIMIZED / "query_recipes.json"
    if recipes.exists():
        recipe_payload = json.loads(read_text(recipes))
        selected_recipes = {
            name: recipe
            for name, recipe in recipe_payload.items()
            if recipe.get("src") in sources
        }
        if selected_recipes:
            parts.append("# Query Recipes\n" + json.dumps(selected_recipes, separators=(",", ":")))

    return "\n\n".join(parts)


def usage_zero():
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def add_usage(total, usage):
    for key in total:
        total[key] += int(usage.get(key, 0) or 0)


def call_model(messages, model, provider):
    if provider == "gemini":
        return call_gemini(messages, model)
    return call_groq(messages, model)


def call_groq(messages, model):
    api_key = groq_api_key
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    client = Groq(api_key=api_key)
    completion = None
    for attempt in range(6):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            break
        except Exception as error:
            message = str(error)
            if is_rate_limit_error(message) and attempt < 5:
                time.sleep(retry_delay_seconds(message))
                continue
            raise RuntimeError(f"Groq SDK error: {error}") from error
    if completion is None:
        raise RuntimeError("Groq SDK returned no completion")

    content = completion.choices[0].message.content
    usage = completion.usage
    return content, {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
        "completion_tokens": getattr(usage, "completion_tokens", 0),
        "total_tokens": getattr(usage, "total_tokens", 0),
    }


def gemini_role(role):
    return "model" if role == "assistant" else "user"


def call_gemini(messages, model):
    api_key = gemini_api_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    system_parts = []
    contents = []
    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "system":
            system_parts.append({"text": content})
        else:
            contents.append(
                {
                    "role": gemini_role(role),
                    "parts": [{"text": content}],
                }
            )

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": system_parts}

    body = None
    for attempt in range(4):
        request = urllib.request.Request(
            GEMINI_URL.format(model=model),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
                break
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code == 429 and attempt < 3:
                time.sleep(retry_delay_seconds(detail))
                continue
            raise RuntimeError(f"Gemini API error {error.code}: {detail}") from error
    if body is None:
        raise RuntimeError("Gemini API returned no response")

    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {body}")
    parts = candidates[0].get("content", {}).get("parts", [])
    content = "".join(part.get("text", "") for part in parts)
    usage_metadata = body.get("usageMetadata", {})
    usage = {
        "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
        "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
        "total_tokens": usage_metadata.get("totalTokenCount", 0),
    }
    return content, usage


def retry_delay_seconds(error_detail):
    match = re.search(r"try again in ([0-9.]+)\s*ms", error_detail, flags=re.IGNORECASE)
    if match:
        return min(max(float(match.group(1)) / 1000.0 + 0.25, 0.5), 65)
    match = re.search(r'"retryDelay"\s*:\s*"(\d+)s"', error_detail)
    if match:
        return min(max(int(match.group(1)) + 1, 5), 65)
    match = re.search(r"retry in ([0-9.]+)s", error_detail, flags=re.IGNORECASE)
    if match:
        return min(max(int(float(match.group(1))) + 1, 5), 65)
    return 20


def is_rate_limit_error(message):
    lowered = message.lower()
    return "429" in lowered or "rate_limit" in lowered or "rate limit" in lowered


def parse_action(content):
    try:
        action = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Model returned invalid JSON: {content[:500]}") from error
    if action.get("action") not in {"coral_sql", "final"}:
        raise RuntimeError(f"Unknown model action: {action}")
    if action["action"] == "coral_sql" and not action.get("sql"):
        raise RuntimeError(f"coral_sql action missing sql: {action}")
    if action["action"] == "final" and not action.get("answer"):
        raise RuntimeError(f"final action missing answer: {action}")
    return action


def referenced_schemas(sql):
    schemas = set()
    for match in re.finditer(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w]*)\.", sql, flags=re.IGNORECASE):
        schemas.add(match.group(1))
    return schemas


def is_discovery_sql(sql):
    normalized = sql.lower()
    return "coral.tables" in normalized or "coral.columns" in normalized or "coral.filters" in normalized


def discovery_kind(sql):
    normalized = sql.lower()
    if "coral.tables" in normalized:
        return "tables"
    if "coral.columns" in normalized:
        return "columns"
    if "coral.filters" in normalized:
        return "filters"
    return ""


def validate_sql(sql, selected_sources):
    stripped = sql.strip()
    normalized = stripped.lower()
    if not (normalized.startswith("select") or normalized.startswith("with")):
        raise RuntimeError("Only read-only SELECT/WITH SQL is allowed")
    if ";" in stripped.rstrip(";"):
        raise RuntimeError("Multiple SQL statements are not allowed")
    banned = r"\b(insert|update|delete|drop|alter|create|truncate|merge|copy|vacuum|attach|detach|pragma)\b"
    if re.search(banned, normalized):
        raise RuntimeError("Write-like SQL keyword rejected")

    allowed = set(selected_sources) | {"coral"}
    for schema in referenced_schemas(stripped):
        if schema not in allowed:
            raise RuntimeError(f"SQL references unselected source '{schema}'")


def compact_tool_result(raw):
    if len(raw) <= MAX_TOOL_OUTPUT_CHARS:
        return raw
    return raw[:MAX_TOOL_OUTPUT_CHARS] + f"\n... truncated {len(raw) - MAX_TOOL_OUTPUT_CHARS} chars ..."


def agent_prompt(kind, question, sources):
    source_list = ", ".join(sources)
    protocol = (
        "You control Coral by returning JSON only. "
        "Return either {\"action\":\"coral_sql\",\"sql\":\"SELECT ...\"} or "
        "{\"action\":\"final\",\"answer\":\"...\"}. "
        "The SQL must be a single SELECT or WITH query. "
        "Metadata tables are real SQL tables: use SELECT ... FROM coral.tables, "
        "SELECT ... FROM coral.columns, and SELECT ... FROM coral.filters. "
        "Do not call coral.tables() or any metadata function. "
        "Never include markdown fences. Use only selected sources: "
        f"{source_list}."
    )
    if kind == "cold":
        return (
            protocol
            + "\nYou are the Cold Agent. You have no catalog. First discover schema using "
            "coral.tables, coral.columns, and coral.filters for the selected sources. "
            "Then query data. Include enough SQL evidence to answer correctly."
            + f"\nUser question: {question}"
        )

    catalog_context = load_catalog_context(sources)
    return (
        protocol
        + "\nYou are the Catalog Agent. Use the optimized catalog context below. "
        "Do not query coral.tables, coral.columns, or coral.filters for catalog-covered selected sources unless a data query fails due to schema drift. "
        "Prefer query recipes when relevant, replacing placeholders like <incident_id> after the root-cause query. "
        "For the enterprise SSO incident question, first run the exact SQL from recipe ops_incident_root_cause. "
        "Keep each SQL action compact; use one recipe query per action instead of inventing a large multi-CTE query."
        + f"\n\nCatalog context:\n{catalog_context}"
        + f"\n\nUser question: {question}"
    )


def new_agent_state(label):
    return {
        "label": label,
        "status": "queued",
        "steps": [],
        "sqlCalls": [],
        "answer": "",
        "error": "",
        "usage": usage_zero(),
        "modelCalls": 0,
        "toolCalls": 0,
        "sqlQueries": 0,
        "discoveryCalls": 0,
        "resultBytes": 0,
        "startedAt": None,
        "endedAt": None,
        "elapsedMs": 0,
    }


def update_run(run_id, agent_key, mutate):
    with RUNS_LOCK:
        run = RUNS[run_id]
        mutate(run["agents"][agent_key])


def run_agent(run_id, agent_key, kind, question, sources, model, provider):
    started = now_ms()

    def start(agent):
        agent["status"] = "running"
        agent["startedAt"] = started

    update_run(run_id, agent_key, start)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a careful data agent. Use Coral SQL actions to inspect data. "
                "Return strict JSON only for every turn."
            ),
        },
        {"role": "user", "content": agent_prompt(kind, question, sources)},
    ]

    try:
        cold_discovery_seen = set()
        parse_retries = 0
        for _ in range(MAX_AGENT_STEPS):
            content, usage = call_model(messages, model, provider)

            def record_model(agent):
                add_usage(agent["usage"], usage)
                agent["modelCalls"] += 1
                agent["steps"].append({"type": "model", "content": content})

            update_run(run_id, agent_key, record_model)
            try:
                action = parse_action(content)
            except RuntimeError as error:
                parse_retries += 1
                if parse_retries > 2:
                    raise
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was not valid action JSON. "
                            f"Error: {error}. Return exactly one JSON object now."
                        ),
                    }
                )

                def record_parse_policy(agent):
                    agent["steps"].append({"type": "policy", "content": str(error)})

                update_run(run_id, agent_key, record_parse_policy)
                continue

            if action["action"] == "final":
                ended = now_ms()

                def finish(agent):
                    agent["status"] = "done"
                    agent["answer"] = action["answer"]
                    agent["endedAt"] = ended
                    agent["elapsedMs"] = ended - started

                update_run(run_id, agent_key, finish)
                return

            sql = action["sql"]
            validate_sql(sql, sources)
            discovery = is_discovery_sql(sql)
            if kind == "cold" and not discovery and cold_discovery_seen != {"tables", "columns", "filters"}:
                policy_result = {
                    "error": (
                        "Cold Agent policy: discover coral.tables, coral.columns, "
                        "and coral.filters for selected sources before data queries."
                    ),
                    "seen": sorted(cold_discovery_seen),
                }
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": "Policy result JSON:\n" + json.dumps(policy_result),
                    }
                )

                def record_policy(agent):
                    agent["steps"].append({"type": "policy", "content": policy_result})

                update_run(run_id, agent_key, record_policy)
                continue

            if kind == "catalog" and discovery:
                catalog_pages = [
                    OPTIMIZED / "sources" / f"{source}.md"
                    for source in sources
                ]
                if any(page.exists() for page in catalog_pages):
                    policy_result = {
                        "error": "Catalog Agent policy: live schema discovery is forbidden for catalog-covered selected sources.",
                    }
                    messages.append({"role": "assistant", "content": content})
                    messages.append(
                        {
                            "role": "user",
                            "content": "Policy result JSON:\n" + json.dumps(policy_result),
                        }
                    )

                    def record_policy(agent):
                        agent["steps"].append({"type": "policy", "content": policy_result})

                    update_run(run_id, agent_key, record_policy)
                    continue

            try:
                raw_result = run_coral_json(sql)
            except Exception as error:
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Coral SQL error JSON:\n"
                            + json.dumps({"error": str(error), "sql": sql})
                            + "\nFix the SQL and continue."
                        ),
                    }
                )

                def record_sql_error(agent):
                    agent["steps"].append(
                        {
                            "type": "coral_sql_error",
                            "sql": sql,
                            "error": str(error),
                        }
                    )

                update_run(run_id, agent_key, record_sql_error)
                continue
            result = compact_tool_result(raw_result)
            result_bytes = len(raw_result.encode("utf-8"))
            if discovery:
                kind_seen = discovery_kind(sql)
                if kind_seen:
                    cold_discovery_seen.add(kind_seen)

            def record_sql(agent):
                agent["toolCalls"] += 1
                agent["sqlQueries"] += 1
                agent["resultBytes"] += result_bytes
                if discovery:
                    agent["discoveryCalls"] += 1
                agent["sqlCalls"].append(
                    {
                        "sql": sql,
                        "discovery": discovery,
                        "resultBytes": result_bytes,
                        "resultPreview": result[:2000],
                    }
                )
                agent["steps"].append(
                    {
                        "type": "coral_sql",
                        "sql": sql,
                        "discovery": discovery,
                        "resultBytes": result_bytes,
                    }
                )

            update_run(run_id, agent_key, record_sql)
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": "Coral SQL result JSON:\n" + result,
                }
            )

        raise RuntimeError("Agent reached max steps without final answer")
    except Exception as error:
        ended = now_ms()

        def fail(agent):
            agent["status"] = "error"
            agent["error"] = str(error)
            agent["endedAt"] = ended
            agent["elapsedMs"] = ended - started

        update_run(run_id, agent_key, fail)


def run_pair(run_id):
    with RUNS_LOCK:
        run = RUNS[run_id]
        question = run["question"]
        sources = run["sources"]
        model = run["model"]
        provider = run["provider"]

    threads = [
        threading.Thread(
            target=run_agent,
            args=(run_id, "cold", "cold", question, sources, model, provider),
            daemon=True,
        ),
        threading.Thread(
            target=run_agent,
            args=(run_id, "catalog", "catalog", question, sources, model, provider),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with RUNS_LOCK:
        RUNS[run_id]["status"] = "done"
        RUNS[run_id]["endedAt"] = now_ms()


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DEMO_DIR), **kwargs)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def send_json(self, payload, status=200):
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.path = "/demo.html"
            return super().do_GET()
        if path == "/api/sources":
            try:
                return self.send_json(list_sources())
            except Exception as error:
                return self.send_json({"error": str(error)}, status=500)
        if path.startswith("/api/runs/"):
            run_id = path.rsplit("/", 1)[-1]
            with RUNS_LOCK:
                run = RUNS.get(run_id)
                if not run:
                    return self.send_json({"error": "run not found"}, status=404)
                return self.send_json(run)
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/runs":
            payload = self.read_json()
            provider = payload.get("provider") or "gemini"
            if provider not in {"groq", "gemini"}:
                return self.send_json({"error": "provider must be groq or gemini"}, status=400)
            if provider == "groq" and not groq_api_key:
                return self.send_json(
                    {"error": "GROQ_API_KEY is not set. Set it before starting demo_server.py."},
                    status=400,
                )
            if provider == "gemini" and not gemini_api_key:
                return self.send_json(
                    {"error": "GEMINI_API_KEY or GOOGLE_API_KEY is not set. Set one before starting demo_server.py."},
                    status=400,
                )
            question = (payload.get("question") or "").strip()
            sources = payload.get("sources") or []
            model = payload.get("model") or (
                DEFAULT_GEMINI_MODEL if provider == "gemini" else DEFAULT_GROQ_MODEL
            )
            if not question:
                return self.send_json({"error": "question is required"}, status=400)
            if not sources:
                return self.send_json({"error": "select at least one source"}, status=400)

            available = {source["name"] for source in list_sources()["sources"]}
            invalid = sorted(set(sources) - available)
            if invalid:
                return self.send_json({"error": f"unknown sources: {', '.join(invalid)}"}, status=400)

            run_id = uuid.uuid4().hex
            run = {
                "id": run_id,
                "status": "running",
                "question": question,
                "sources": sources,
                "model": model,
                "provider": provider,
                "createdAt": now_ms(),
                "endedAt": None,
                "agents": {
                    "cold": new_agent_state("Coral Only"),
                    "catalog": new_agent_state("Catalog + Coral"),
                },
            }
            with RUNS_LOCK:
                RUNS[run_id] = run

            threading.Thread(target=run_pair, args=(run_id,), daemon=True).start()
            return self.send_json({"id": run_id})

        if path == "/api/rebuild":
            command = [
                "python",
                "scripts/coral_catalog.py",
                "build",
                "--no-claude",
                "--output-dir",
                str(ROOT / ".demo_catalog"),
            ]
            result = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return self.send_json(
                {
                    "ok": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                },
                status=200 if result.returncode == 0 else 500,
            )

        return self.send_json({"error": "not found"}, status=404)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", DEFAULT_PORT), DemoHandler)
    print(f"Demo server: http://127.0.0.1:{DEFAULT_PORT}")
    if not groq_api_key:
        print("GROQ_API_KEY is not set; Groq runs will be disabled.")
    if not gemini_api_key:
        print("GEMINI_API_KEY / GOOGLE_API_KEY is not set; Gemini runs will be disabled.")
    server.serve_forever()


if __name__ == "__main__":
    main()
