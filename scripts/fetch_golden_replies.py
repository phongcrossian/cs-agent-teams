"""One-off analysis helper (Phase-4 reopen): fetch the first public agent reply for every
ticket in a Freshdesk CSV export and join it with the CS-agent-entered properties.

Read-only. Writes a JSONL to OUT_PATH (NOT committed — contains customer PII).
Usage: .venv/bin/python scripts/fetch_golden_replies.py <csv1> [<csv2> ...]
       (uv is NOT on PATH in background shells — call the venv python directly)
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

import httpx

_REPO_ROOT = Path(__file__).parent.parent
# persistent (gitignored) so a pause/resume does not lose the fetch
OUT_PATH = _REPO_ROOT / ".planning" / "phases" / \
    "04-reply-pipeline-classify-extract-ground-draft-safety-guards" / ".golden-analysis.jsonl"

# load .env.prd — OVERRIDE any stale env values (setdefault was a bug: a pre-set
# FRESHDESK_* in the shell env silently shadowed .env.prd and caused 404s)
_envprd: dict[str, str] = {}
for line in (_REPO_ROOT / ".env.prd").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        _envprd[k.strip()] = v.strip()

DOMAIN = _envprd["FRESHDESK_DOMAIN"]
API_KEY = _envprd["FRESHDESK_API_KEY"]
print(f"using domain={DOMAIN} keylen={len(API_KEY)}")

# properties we care about for rule derivation
PROP_COLS = [
    "Ticket ID", "Subject", "Status", "Priority", "Source", "Type", "Group",
    "Tags", "Order", "Customer_Request", "Product_line", "Customer_Feedback",
    "Feedback_Issue", "Additional_Feedback", "Additional_Feedback_Issue",
    "Rootcause", "Rootcause_type", "Section_Flow", "Product_label",
    "Escalation level", "Survey results",
]


def first_public_reply(client: httpx.Client, tid: str) -> dict | None:
    r = client.get(f"https://{DOMAIN}/api/v2/tickets/{tid}/conversations",
                   auth=(API_KEY, "X"), timeout=30)
    if r.status_code != 200:
        return {"_error": f"HTTP {r.status_code}"}
    convs = [c for c in r.json() if c.get("incoming") is False and c.get("private") is False]
    convs.sort(key=lambda c: c.get("created_at", ""))
    if not convs:
        return None
    c = convs[0]
    return {
        "created_at": c.get("created_at"),
        "from_email": c.get("from_email"),
        "body_text": (c.get("body_text") or "")[:4000],
    }


def _category(csv_path: str) -> str:
    name = Path(csv_path).stem.lower()
    if "change" in name or "cancel" in name:
        return "change_request"
    if "complaint" in name:
        return "complaint"
    if "inquiry" in name:
        return "inquiry"
    return name


def main(csv_paths: list[str]) -> int:
    n = total = 0
    with httpx.Client() as client, open(OUT_PATH, "w", encoding="utf-8") as out:
        for csv_path in csv_paths:
            cat = _category(csv_path)
            rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
            total += len(rows)
            print(f"== {cat}: {len(rows)} tickets ({csv_path}) ==")
            for row in rows:
                tid = (row.get("Ticket ID") or "").strip()
                if not tid:
                    continue
                props = {k: row.get(k, "") for k in PROP_COLS}
                try:
                    reply = first_public_reply(client, tid)
                except Exception as exc:  # noqa: BLE001
                    reply = {"_error": str(exc)}
                out.write(json.dumps(
                    {"category_file": cat, "props": props, "reply": reply},
                    ensure_ascii=False) + "\n")
                out.flush()
                n += 1
                ok = bool(reply and "body_text" in reply)
                print(f"[{n}/{total}] {cat} {tid} -> {'reply' if ok else reply}")
                time.sleep(0.35)  # polite rate limiting
    print(f"DONE {n} tickets -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
