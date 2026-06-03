"""Analyze .golden-analysis.jsonl (props + first public reply) to derive the authorized-offer
rule set: per (category, Customer_Request sub-type), what offers/actions the CS agents actually make.

Read-only over the local JSONL (no network, no PII surfaced — only aggregate counts + redacted snippets).
Usage: .venv/bin/python scripts/analyze_golden.py
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

IN = Path(".planning/phases/04-reply-pipeline-classify-extract-ground-draft-safety-guards/.golden-analysis.jsonl")

SIGNALS = {
    "refund_50": re.compile(r"50%\s*refund", re.I),
    "refund_full": re.compile(r"full refund|entire payment|100% refund", re.I),
    "discount_40": re.compile(r"40%\s*(?:vip\s*)?(?:discount|off)", re.I),
    "discount_20": re.compile(r"20%\s*(?:vip\s*)?(?:discount|off|courtesy)", re.I),
    "free_replacement": re.compile(r"complimentary replacement|free replacement|replacement at no|new (?:order|replacement).{0,30}no (?:additional )?cost|send (?:you )?a (?:new|free|complimentary)", re.I),
    "keep_item": re.compile(r"no need to (?:return|mail|send)|keep (?:it|your|the)|donate", re.I),
    "ask_measurements": re.compile(r"measurements|underbust|full[\s-]?bust|waist.{0,20}hip", re.I),
    "ask_evidence": re.compile(r"\bphoto|\bpicture|defective areas|shipping label|evidence", re.I),
    "two_options": re.compile(r"option 1|option 2|two (?:options|solutions|alternatives)", re.I),
    "free_shipping": re.compile(r"free shipping", re.I),
    "address_updated": re.compile(r"address has been|updated your (?:shipping )?address|confirm (?:the|your) (?:new )?address|verify your address", re.I),
    "cancel_done": re.compile(r"cancel(?:led|ed)? your order|order has been cancel|process(?:ed)? the cancellation", re.I),
    "variant_changed": re.compile(r"updated your order|changed (?:the|your) (?:size|variant|item)|swap|exchange the size", re.I),
    "tracking_info": re.compile(r"tracking|track your|carrier|on its way|in transit|delivered", re.I),
    "warranty_window": re.compile(r"45 days|14 days|within (?:the )?warranty|warranty (?:period|policy)|qualifies for", re.I),
    "escalate_ish": re.compile(r"forward(?:ed|ing)? (?:your|this) (?:case|issue|request) to|specialist team|investigate|look into this further|get back to you", re.I),
}

TEMPLATE_FP = {
    "B7 (within-grt, non-defective, cannot-replace: 50%+40%)": re.compile(r"both benefits are included together", re.I),
    "B3/B8 (variant N/A: 50%+20% OR 40%)": re.compile(r"do not have any variant|currently do not have", re.I),
    "B-RETURN (return->offer alternatives first)": re.compile(r"before (?:proceeding|we proceed) with (?:a )?(?:return|your refund)", re.I),
}


def main() -> int:
    if not IN.exists():
        print(f"missing {IN} — run fetch_golden_replies.py first")
        return 1
    recs = [json.loads(l) for l in IN.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"{len(recs)} records\n")

    # group by (category_file, Customer_Request)
    groups: dict[tuple, list] = collections.defaultdict(list)
    no_reply = err = 0
    for r in recs:
        reply = r.get("reply") or {}
        body = reply.get("body_text") if isinstance(reply, dict) else None
        if isinstance(reply, dict) and reply.get("_error"):
            err += 1
        if not body:
            no_reply += 1
        cat = r.get("category_file", "?")
        cr = (r.get("props", {}).get("Customer_Request") or "∅").strip() or "∅"
        groups[(cat, cr)].append(body or "")

    print(f"no_reply={no_reply} errors={err}\n")
    for (cat, cr), bodies in sorted(groups.items()):
        n = len(bodies)
        sig = collections.Counter()
        tpl = collections.Counter()
        for b in bodies:
            for name, rx in SIGNALS.items():
                if rx.search(b):
                    sig[name] += 1
            for name, rx in TEMPLATE_FP.items():
                if rx.search(b):
                    tpl[name] += 1
        present = {k: v for k, v in sig.items() if v}
        top = sorted(present.items(), key=lambda x: -x[1])
        print(f"== {cat} / {cr}  (n={n}) ==")
        print("   signals: " + (" | ".join(f"{k}:{v}" for k, v in top) or "none detected"))
        if tpl:
            print("   templates: " + " | ".join(f"{k}:{v}" for k, v in tpl.items()))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
