"""Record real Haiku decisions on 20 frozen layouts per task, then replay successes."""
from __future__ import annotations

import hashlib
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import anthropic
from playwright.sync_api import sync_playwright

from audit import ROOT, TASKS, freeze, sha
from pilot import MODEL, SYSTEM, api_key, ask, execute, load_page, parse_action, small_png

SEEDS = tuple(range(10, 30))
DEST = ROOT / "results" / "phase_b.jsonl"


def frozen_configs():
    configs = freeze()
    stamp = (f"manifest_sha256 {sha(ROOT/'manifest.json')}\n"
             f"phase_b_code_sha256 {sha(ROOT/'phase_b.py')}\n"
             f"pilot_code_sha256 {sha(ROOT/'pilot.py')}\n"
             f"prompt_sha256 {hashlib.sha256(SYSTEM.encode()).hexdigest()}\n"
             f"model {MODEL}\nseeds 10-29\n")
    path = ROOT / "PHASE_B_FROZEN.txt"
    if path.exists() and path.read_text() != stamp:
        raise RuntimeError("Phase B code, prompt, or manifest changed after freezing")
    path.write_text(stamp)
    return {(c["task"], c["seed"]): c for c in configs if c["task"] in TASKS and c["seed"] in SEEDS}


def aggregate(rows):
    return {"model": MODEL, "decisions": len(rows),
            "cost_usd": round(sum(r["usage"]["cost_usd"] for r in rows), 6),
            "input_tokens": sum(r["usage"]["input_tokens"] for r in rows),
            "output_tokens": sum(r["usage"]["output_tokens"] for r in rows),
            "by_task": {task: {
                "decisions": sum(r["task"] == task for r in rows),
                "clean_correct": sum(r["clean"]["round_trip_success"] for r in rows if r["task"] == task),
                "replayed": sum(r["defect"] is not None for r in rows if r["task"] == task),
                "defect_round_trip_success": sum(bool(r["defect"] and r["defect"]["round_trip_success"])
                                                  for r in rows if r["task"] == task)
            } for task in TASKS}}


def main():
    cfgs = frozen_configs()
    rows = [json.loads(line) for line in DEST.read_text().splitlines()] if DEST.exists() else []
    done = {(r["task"], r["seed"]) for r in rows}
    spent = sum(r["usage"]["cost_usd"] for r in rows)
    shots = ROOT / "results" / "phase_b_screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic(api_key=api_key())
    class Quiet(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw): super().__init__(*a, directory=str(ROOT/"site"), **kw)
        def log_message(self, *a): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as pw, DEST.open("a") as out:
            browser = pw.chromium.launch(headless=True)
            for task in TASKS:
                for seed in SEEDS:
                    if (task, seed) in done:
                        continue
                    cfg = cfgs[(task, seed)]
                    clean_page = load_page(browser, base, cfg)
                    before = small_png(clean_page.screenshot())
                    input_path = shots / f"{task}_{seed}_input.png"
                    input_path.write_bytes(before)
                    reply, usage = ask(client, before, spent)
                    spent += usage["cost_usd"]
                    action = parse_action(reply)
                    clean = execute(clean_page, cfg, action, False)
                    clean_path = shots / f"{task}_{seed}_clean.png"
                    clean_path.write_bytes(small_png(clean_page.screenshot()))
                    clean_page.close()
                    defect = None
                    defect_path = None
                    if clean["round_trip_success"]:
                        broken_page = load_page(browser, base, cfg)
                        defect = execute(broken_page, cfg, action, True)
                        defect_path = shots / f"{task}_{seed}_defect.png"
                        defect_path.write_bytes(small_png(broken_page.screenshot()))
                        broken_page.close()
                    row = {"task":task,"seed":seed,"model":MODEL,"model_reply":reply,
                           "parsed_action":action,"usage":usage,
                           "input_screenshot":str(input_path.relative_to(ROOT)),
                           "clean_screenshot":str(clean_path.relative_to(ROOT)),
                           "defect_screenshot":str(defect_path.relative_to(ROOT)) if defect_path else None,
                           "clean":clean,"defect":defect}
                    out.write(json.dumps(row)+"\n"); out.flush(); rows.append(row)
                print(f"{task}: {aggregate(rows)['by_task'][task]} cumulative ${spent:.5f}",flush=True)
            browser.close()
    finally:
        server.shutdown()
    summary = aggregate(rows)
    (ROOT/"results"/"phase_b.summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))


if __name__ == "__main__": main()
