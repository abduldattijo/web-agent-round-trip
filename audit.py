"""Deterministic local browser round-trip audit. No model or external site calls."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import random
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
TASKS = ("search_token", "scaled_click", "frame_feedback", "hover_value")
ADDITIONAL = ("additional_delay", "additional_offscreen", "additional_overlay", "additional_disabled")
POLICIES = ("unverified", "generic", "pixel", "round_trip")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest():
    rows = []
    for task in TASKS + ADDITIONAL:
        for seed in range(50):
            rng = random.Random(f"round-trip-v1:{task}:{seed}")
            c = {"task": task, "seed": seed, "target": f"Record-{seed:02d}",
                 "x": rng.randrange(520, 850, 20), "y": rng.randrange(180, 450, 20),
                 "value": rng.randrange(10, 99), "instruction": "Complete the displayed task."}
            if task == "scaled_click":
                c["buttons"] = [[100 + 180 * col, 70 + 105 * row] for row in range(5) for col in range(5)]
                c["target_index"] = rng.randrange(13, 25)
                c["instruction"] = f"Click Item {c['target_index']}."
            if task == "frame_feedback":
                c["target"] = "row-" + str(rng.randrange(5))
                c["instruction"] = f"Select Record {c['target'][-1]} inside the frame."
            if task == "hover_value":
                c["instruction"] = "Hover over the chart mark and read its value."
            if task == "search_token":
                c["instruction"] = f"Search the exact record name {c['target']}."
            if task == "additional_offscreen":
                c["y"] = 1100 + rng.randrange(0, 120, 20)
            rows.append(c)
    return rows


def freeze():
    path = ROOT / "manifest.json"
    if not path.exists():
        path.write_text(json.dumps(manifest(), indent=2) + "\n")
    frozen = ROOT / "FROZEN.txt"
    value = f"manifest_sha256 {sha(path)}\naudit_code_sha256 {sha(ROOT / 'audit.py')}\nsite_sha256 {sha(ROOT / 'site/index.html')}\nframe_sha256 {sha(ROOT / 'site/frame.html')}\nfinal_seeds 10-49\n"
    if frozen.exists() and frozen.read_text() != value:
        raise RuntimeError("Frozen files changed; archive and explicitly version the audit before rerunning")
    frozen.write_text(value)
    return json.loads(path.read_text())


def pixel_fraction(before, after):
    a = Image.open(io.BytesIO(before)).convert("RGB").resize((300, 200))
    b = Image.open(io.BytesIO(after)).convert("RGB").resize((300, 200))
    diff = ImageChops.difference(a, b).convert("L")
    hist = diff.histogram()
    return sum(hist[16:]) / (300 * 200)


def coarse(page):
    return {"url": page.url, "text_length": len(page.locator("body").inner_text()),
            "main_state": page.locator("#status").inner_text()}


def browser_case(browser, base, cfg, defect, repeat):
    task = cfg["task"]
    page = browser.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=1)
    url = base + "/index.html?cfg=" + quote(json.dumps(cfg, separators=(",", ":")))
    page.goto(url)
    if task == "frame_feedback":
        page.frame_locator("#rows").locator("button").first.wait_for()
    if task == "additional_offscreen":
        page.locator("#stage").evaluate("e=>e.style.height='1400px'")
    before = coarse(page)
    before_png = page.screenshot()
    started = time.monotonic()
    intended = None
    executed = None
    hit = None
    feedback = None
    if task == "search_token":
        typed = cfg["target"] + ("[im_end]" if defect else "")
        page.locator("#query").fill(typed)
        page.locator("#submit").click()
        feedback = page.locator("#status").inner_text()
    elif task == "scaled_click":
        target_id = "button-" + str(cfg["target_index"])
        box = page.locator("#" + target_id).bounding_box()
        intended = [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2]
        executed = [round(v * .75, 2) for v in intended] if defect else intended
        hit = page.evaluate("([x,y])=>document.elementFromPoint(x,y)?.id", executed)
        page.mouse.click(*executed)
        feedback = page.locator("#status").inner_text()
    elif task == "frame_feedback":
        page.frame_locator("#rows").locator("#" + cfg["target"]).click()
        page.wait_for_timeout(25)
        actual = page.frame_locator("#rows").locator(".selected").get_attribute("id")
        feedback = "No detectable change" if defect else "Selected " + actual
    elif task == "hover_value":
        box = page.locator("#mark").bounding_box()
        intended = [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2]
        executed = intended
        page.mouse.move(*executed)
        page.wait_for_timeout(10 if defect else 200)
        feedback = "Captured next view"
    else:
        box = page.locator("#target").bounding_box()
        intended = [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2]
        executed = intended
        hit = page.evaluate("([x,y])=>document.elementFromPoint(x,y)?.id", executed)
        page.mouse.click(*executed)
        page.wait_for_timeout(100)
        feedback = page.locator("#status").inner_text()
    after = coarse(page)
    after_png = page.screenshot()
    # The oracle is read only after every policy-visible observation has been captured.
    if task == "search_token":
        visible = {"input": page.locator("#query").input_value(), "status": feedback}
    elif task == "scaled_click":
        visible = {"selected": page.locator(".selected").first.get_attribute("id") if page.locator(".selected").count() else None}
    elif task == "frame_feedback":
        visible = {"selected": page.frame_locator("#rows").locator(".selected").get_attribute("id")}
    elif task == "hover_value":
        visible = {"tooltip": page.locator("#tooltip").is_visible(),
                   "tooltip_text": page.locator("#tooltip").inner_text()}
    else:
        visible = {"selected": page.locator("#target").get_attribute("class"),
                   "status": feedback}
    ledger = page.evaluate("window.__ledger")
    eventual_success = None
    if task == "additional_delay":
        page.wait_for_timeout(850)
        eventual_success = any(e["type"] == "activated" for e in page.evaluate("window.__ledger"))
    if task == "frame_feedback":
        action_success = any(e["type"] == "row" and e["detail"] == cfg["target"] for e in ledger)
        oracle_success = action_success and feedback == "Selected " + cfg["target"]
    elif task == "search_token":
        oracle_success = any(e["type"] == "submit" and e["detail"] == cfg["target"] for e in ledger)
        action_success = oracle_success
    elif task == "scaled_click":
        oracle_success = any(e["type"] == "click" and e["detail"] == "button-" + str(cfg["target_index"]) for e in ledger)
        action_success = oracle_success
    elif task == "hover_value":
        oracle_success = any(e["type"] == "tooltip_visible" for e in ledger)
        action_success = any(e["type"] == "hover" for e in ledger)
    else:
        oracle_success = any(e["type"] == "activated" for e in ledger)
        action_success = any(e["type"] == "click" and e["detail"] == "target" for e in ledger)
    delta = pixel_fraction(before_png, after_png)
    generic_changed = (before["url"] != after["url"] or before["main_state"] != after["main_state"]
                       or abs(before["text_length"] - after["text_length"]) > 5)
    if task == "search_token":
        round_trip_ok = visible["input"] == cfg["target"] and visible["status"] == "Found " + cfg["target"]
    elif task == "scaled_click":
        round_trip_ok = hit == "button-" + str(cfg["target_index"]) and visible["selected"] == hit
    elif task == "frame_feedback":
        round_trip_ok = visible["selected"] == cfg["target"] and feedback == "Selected " + visible["selected"]
    elif task == "hover_value":
        round_trip_ok = visible["tooltip"] and visible["tooltip_text"] == "Value: " + str(cfg["value"])
    else:
        round_trip_ok = "selected" in (visible["selected"] or "") and visible["status"] == "Activated"
    alerts = {"unverified": False, "generic": not generic_changed,
              "pixel": delta < .002, "round_trip": not round_trip_ok}
    rec = {"task": task, "seed": cfg["seed"], "repeat": repeat, "defect": defect,
           "intended_css": intended, "executed_css": executed, "image_size": [900, 600],
           "viewport_size": [1200, 800], "hit_element": hit, "before": before, "after": after,
           "visible_evidence": visible, "feedback": feedback, "ledger": ledger,
           "action_success": action_success, "round_trip_success": oracle_success,
           "eventual_success": eventual_success,
           "pixel_changed_fraction": round(delta, 6), "elapsed_s": round(time.monotonic()-started, 4),
           "alerts": alerts, "model_calls": 0, "cost_usd": 0}
    page.close()
    return rec


def wilson(k, n):
    if not n: return [None, None]
    z = 1.96
    p = k/n
    den = 1+z*z/n
    centre = (p+z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(centre-half, 3), round(centre+half, 3)]


def summary(rows):
    out = {}
    for task in TASKS+ADDITIONAL:
        all_repeats=[r for r in rows if r["task"]==task]
        group=[r for r in all_repeats if r["repeat"]==0]
        out[task]={}
        out[task]["timing_disagreements"] = sum(
            len({r["round_trip_success"] for r in all_repeats
                 if r["seed"]==first["seed"] and r["defect"]==first["defect"]})>1
            for first in group)
        for policy in POLICIES:
            failures=[r for r in group if not r["round_trip_success"]]
            successes=[r for r in group if r["round_trip_success"]]
            caught=sum(r["alerts"][policy] for r in failures)
            false=sum(r["alerts"][policy] for r in successes)
            out[task][policy]={"failures":len(failures),"detected":caught,
                "detection_rate":round(caught/len(failures),3) if failures else None,
                "detection_95_wilson":wilson(caught,len(failures)),
                "successes":len(successes),"false_alarms":false,
                "false_alarm_rate":round(false/len(successes),3) if successes else None,
                "false_alarm_95_wilson":wilson(false,len(successes))}
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "freeze", "run"])
    args=ap.parse_args()
    if args.mode=="freeze":
        freeze(); print((ROOT/"FROZEN.txt").read_text()); return
    if args.mode=="run":
        configs=freeze()
        seeds=range(10,50)
    else:
        configs=manifest(); seeds=range(2)
    by_key={(c["task"],c["seed"]):c for c in configs}
    class Quiet(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/"site"),**kw)
        def log_message(self,*a):pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f"http://127.0.0.1:{server.server_port}"
    rows=[]
    dest=ROOT/"results"/("phase_a.jsonl" if args.mode=="run" else "dev.jsonl")
    dest.parent.mkdir(exist_ok=True)
    with sync_playwright() as pw, dest.open("w") as f:
        browser=pw.chromium.launch(headless=True)
        for task in TASKS+ADDITIONAL:
            for seed in seeds:
                modes=(False,True) if task in TASKS else (True,)
                for defect in modes:
                    repeats=range(3) if task in ("hover_value","additional_delay") else range(1)
                    for repeat in repeats:
                        rec=browser_case(browser,base,by_key[(task,seed)],defect,repeat)
                        f.write(json.dumps(rec)+"\n"); f.flush(); rows.append(rec)
            print(f"{task}: {sum(r['task']==task for r in rows)} cases",flush=True)
        browser.close()
    server.shutdown()
    result=summary(rows)
    path=dest.with_suffix(".summary.json")
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(f"wrote {len(rows)} cases to {dest}; summary {path}")


if __name__=="__main__": main()
