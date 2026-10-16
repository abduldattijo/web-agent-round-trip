"""Haiku vision pilot on development layouts only; logs every response and charge."""
from __future__ import annotations

import base64
import io
import json
import os
import re
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

import anthropic
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

from audit import ROOT, TASKS, freeze

MODEL = "claude-haiku-5-5"
PRICE_IN = 0.10  # USD per million tokens, prompt <=100k
PRICE_OUT = 0.50
PILOT_CAP = 0.05
SYSTEM = (
    "You operate a browser from a 900 by 600 pixel screenshot. Follow the instruction "
    "visible near the top of the page. Return exactly one JSON object and no other text. "
    "For a search, use {\"action\":\"type\",\"text\":\"exact name\"}. "
    "For a button or row, use {\"action\":\"click\",\"x\":number,\"y\":number}. "
    "For a chart mark, use {\"action\":\"hover\",\"x\":number,\"y\":number}. "
    "Coordinates must refer to this 900 by 600 image. Pick the center of the target."
)


def api_key():
    value = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if value:
        return value
    raise RuntimeError("Anthropic API key unavailable")


def small_png(raw):
    image = Image.open(io.BytesIO(raw)).convert("RGB").resize((900, 600))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def parse_action(reply):
    match = re.search(r"\{.*?\}", reply, re.S)
    if not match:
        return None
    try:
        action = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    if action.get("action") == "type" and isinstance(action.get("text"), str):
        return action
    if action.get("action") in ("click", "hover") and all(
        isinstance(action.get(k), (int, float)) and 0 <= action[k] <= bound
        for k, bound in (("x", 900), ("y", 600))
    ):
        return action
    return None


def ask(client, png, spent):
    if spent + 0.005 > PILOT_CAP:
        raise RuntimeError("Pilot spend guard reached before next request")
    started = time.monotonic()
    resp = client.messages.create(
        model=MODEL, max_tokens=120, thinking={"type": "disabled"}, system=SYSTEM,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": "What is the next single browser action?"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.b64encode(png).decode("ascii")}}
        ]}]
    )
    reply = "".join(part.text for part in resp.content if getattr(part, "type", None) == "text")
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    usage["cost_usd"] = (usage["input_tokens"]*PRICE_IN+usage["output_tokens"]*PRICE_OUT)/1_000_000
    usage["latency_s"] = round(time.monotonic()-started, 3)
    return reply, usage


def load_page(browser, base, cfg):
    page = browser.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=1)
    page.goto(base + "/index.html?cfg=" + quote(json.dumps(cfg, separators=(",", ":"))))
    if cfg["task"] == "frame_feedback":
        page.frame_locator("#rows").locator("button").first.wait_for()
    return page


def execute(page, cfg, action, defect):
    task = cfg["task"]
    if action is None:
        return {"action_success": False, "round_trip_success": False, "feedback": "Unparsed reply",
                "ledger": [], "executed_css": None}
    executed = None
    if task == "search_token" and action["action"] == "type":
        text = action["text"] + ("[im_end]" if defect else "")
        page.locator("#query").fill(text)
        page.locator("#submit").click()
    elif task in ("scaled_click", "frame_feedback") and action["action"] == "click":
        factor = 1 if (task == "scaled_click" and defect) else 4/3
        executed = [round(action["x"]*factor, 2), round(action["y"]*factor, 2)]
        page.mouse.click(*executed)
    elif task == "hover_value" and action["action"] == "hover":
        executed = [round(action["x"]*4/3, 2), round(action["y"]*4/3, 2)]
        page.mouse.move(*executed)
        page.wait_for_timeout(10 if defect else 200)
    else:
        return {"action_success": False, "round_trip_success": False, "feedback": "Wrong action type",
                "ledger": [], "executed_css": None}
    if task == "frame_feedback":
        page.wait_for_timeout(35)
    ledger = page.evaluate("window.__ledger")
    if task == "search_token":
        success = any(e["type"] == "submit" and e["detail"] == cfg["target"] for e in ledger)
        feedback = page.locator("#status").inner_text()
        round_trip = success
    elif task == "scaled_click":
        success = any(e["type"] == "click" and e["detail"] == "button-"+str(cfg["target_index"]) for e in ledger)
        feedback = page.locator("#status").inner_text()
        round_trip = success
    elif task == "frame_feedback":
        success = any(e["type"] == "row" and e["detail"] == cfg["target"] for e in ledger)
        feedback = "No detectable change" if defect else "Selected "+(ledger[-1]["detail"] if ledger else "none")
        round_trip = success and feedback == "Selected "+cfg["target"]
    else:
        success = any(e["type"] == "hover" for e in ledger)
        round_trip = any(e["type"] == "tooltip_visible" for e in ledger)
        feedback = "Tooltip visible" if round_trip else "Tooltip missing from observation"
    return {"action_success": success, "round_trip_success": round_trip, "feedback": feedback,
            "ledger": ledger, "executed_css": executed}


def make_visual(before, after, action, seed, directory):
    """Annotated screenshot sequence, not a video of an external site."""
    if not action or action.get("action") != "click":
        return None
    base = Image.open(io.BytesIO(before)).convert("RGB")
    end = Image.open(io.BytesIO(after)).convert("RGB")
    chosen = (action["x"], action["y"])
    landed = (action["x"]*.75, action["y"]*.75)
    def mark(image, step):
        pic=Image.new("RGB",(900,640),"white")
        pic.paste(image,(0,0)); d=ImageDraw.Draw(pic)
        d.rectangle((0,600,899,639),fill="#14212d")
        d.text((12,613),step,fill="white")
        d.ellipse((chosen[0]-13,chosen[1]-13,chosen[0]+13,chosen[1]+13),outline="#00c853",width=5)
        d.ellipse((landed[0]-13,landed[1]-13,landed[0]+13,landed[1]+13),outline="#e53935",width=5)
        d.line((chosen[0],chosen[1],landed[0],landed[1]),fill="#e53935",width=4)
        return pic
    frames=[mark(base,"Model target (green); faulty click (red)"),
            mark(base,"Coordinate conversion skipped"),
            mark(end,"Actual browser state after faulty click")]
    directory.mkdir(exist_ok=True)
    png = directory/f"scaled_click_seed{seed}_comparison.png"
    gif = directory/f"scaled_click_seed{seed}.gif"
    comparison=Image.new("RGB",(1800,640),"white")
    comparison.paste(frames[0],(0,0)); comparison.paste(frames[-1],(900,0)); comparison.save(png)
    frames[0].save(gif,save_all=True,append_images=frames[1:],duration=[1100,900,1800],loop=0,optimize=True)
    return {"png":str(png.relative_to(ROOT)),"gif":str(gif.relative_to(ROOT)),
            "green_image_point":chosen,"red_image_point":landed}


def main():
    cfgs={(c["task"],c["seed"]):c for c in freeze() if c["seed"] in (0,1)}
    client=anthropic.Anthropic(api_key=api_key())
    class Quiet(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/"site"),**kw)
        def log_message(self,*a): pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f"http://127.0.0.1:{server.server_port}"
    shots=ROOT/"results"/"pilot_screenshots"; shots.mkdir(parents=True,exist_ok=True)
    rows=[]; spent=0.0; visual=None
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        for task in TASKS:
            for seed in (0,1):
                cfg=cfgs[(task,seed)]
                clean=load_page(browser,base,cfg)
                before=small_png(clean.screenshot())
                input_path=shots/f"{task}_{seed}_input.png"; input_path.write_bytes(before)
                reply,usage=ask(client,before,spent)
                spent+=usage["cost_usd"]
                action=parse_action(reply)
                for defect in (False,True):
                    page=clean if not defect else load_page(browser,base,cfg)
                    result=execute(page,cfg,action,defect)
                    after=small_png(page.screenshot())
                    after_path=shots/f"{task}_{seed}_{'defect' if defect else 'clean'}_after.png"
                    after_path.write_bytes(after)
                    row={"task":task,"seed":seed,"defect":defect,"model":MODEL,
                         "model_reply":reply,"parsed_action":action,"usage":usage if not defect else None,
                         "input_screenshot":str(input_path.relative_to(ROOT)),
                         "after_screenshot":str(after_path.relative_to(ROOT)),**result}
                    rows.append(row)
                    if (task=="scaled_click" and defect and visual is None
                            and rows[-2]["round_trip_success"] and not result["round_trip_success"]
                            and any(e["type"]=="click" and e["detail"].startswith("button-")
                                    for e in result["ledger"])):
                        visual=make_visual(before,after,action,seed,ROOT/"figures")
                    page.close()
                print(f"{task} seed {seed}: clean={rows[-2]['round_trip_success']} "
                      f"defect={rows[-1]['round_trip_success']} cost=${spent:.5f}",flush=True)
        browser.close()
    server.shutdown()
    dest=ROOT/"results"/"pilot.jsonl"
    dest.write_text("".join(json.dumps(r)+"\n" for r in rows))
    summary={"model":MODEL,"decisions":8,"episodes":len(rows),"cost_usd":round(spent,6),
             "input_tokens":sum(r["usage"]["input_tokens"] for r in rows if r["usage"]),
             "output_tokens":sum(r["usage"]["output_tokens"] for r in rows if r["usage"]),
             "by_task":{task:{"clean_correct":sum(r["round_trip_success"] for r in rows if r["task"]==task and not r["defect"]),
                              "defect_correct":sum(r["round_trip_success"] for r in rows if r["task"]==task and r["defect"]),
                              "layouts":2} for task in TASKS},"visual":visual}
    (ROOT/"results"/"pilot.summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))


if __name__=="__main__": main()
