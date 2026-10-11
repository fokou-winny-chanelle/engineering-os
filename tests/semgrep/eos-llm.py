# Fixtures for core/scaffold/llm/semgrep-llm.yml (semgrep --test). Not executed.
# ruff: noqa: S102, PLW1510
import os
import sqlite3
import subprocess

from anthropic import Anthropic
from openai import AsyncOpenAI, OpenAI
from sqlalchemy import text

# ruleid: eos-llm-client-default-timeout
client = OpenAI()
# ruleid: eos-llm-client-default-timeout
aclient = AsyncOpenAI(max_retries=1)
# ruleid: eos-llm-client-default-timeout
claude = Anthropic()
# ok: eos-llm-client-default-timeout
good = OpenAI(timeout=30.0, max_retries=0)
# ok: eos-llm-client-default-timeout
good_claude = Anthropic(timeout=20.0)


def run_generated(question: str, db: sqlite3.Connection) -> None:
    r = good.responses.create(model="gpt-6-luna", input=question, max_output_tokens=300)
    code = r.output_text
    # ruleid: eos-llm-output-to-exec
    eval(code)
    # ruleid: eos-llm-output-to-exec
    exec(code)
    # ruleid: eos-llm-output-to-exec
    os.system(f"convert {code}")
    # ruleid: eos-llm-output-to-exec
    subprocess.run(code, shell=True)
    # ruleid: eos-llm-output-to-exec
    db.execute(f"SELECT * FROM invoices WHERE {code}")
    # ok: eos-llm-output-to-exec
    db.execute("SELECT * FROM invoices WHERE ref = ?", (code,))
    # ruleid: eos-llm-output-to-exec
    text("DELETE FROM t WHERE " + code)


def claude_sql(question: str, cur) -> None:
    msg = good_claude.messages.create(
        model="claude-haiku-5-5", max_tokens=200, messages=[{"role": "user", "content": question}]
    )
    where = msg.content[0].text
    # ruleid: eos-llm-output-to-exec
    cur.execute("SELECT * FROM orders WHERE " + where)
    # ok: eos-llm-output-to-exec
    cur.execute("SELECT * FROM orders WHERE status = %s", (where,))


def safe_choice(question: str) -> str:
    r = good.responses.create(model="gpt-6-luna", input=question, max_output_tokens=20)
    choice = r.output_text.strip()
    if choice not in {"refund", "track", "agent"}:
        return "agent"
    # ok: eos-llm-output-to-exec
    subprocess.run(["notify", "--kind", "fixed"], check=True)
    return choice


def limits(question: str, kwargs: dict) -> None:
    # ruleid: eos-llm-missing-max-tokens
    good.responses.create(model="gpt-6-luna", input=question)
    # ok: eos-llm-missing-max-tokens
    good.responses.create(model="gpt-6-luna", input=question, max_output_tokens=500)
    # ruleid: eos-llm-missing-max-tokens
    good.chat.completions.create(model="gpt-6-luna", messages=[])
    # ok: eos-llm-missing-max-tokens
    good.chat.completions.create(model="gpt-6-luna", messages=[], max_completion_tokens=400)
    # ok: eos-llm-missing-max-tokens
    good.responses.create(**kwargs)
