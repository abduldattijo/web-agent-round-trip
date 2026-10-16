"""Full-loop policy comparison on recorded correct decisions. API cap: $2 total."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import statistics
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic
from playwright.sync_api import sync_playwright

from audit import ROOT, TASKS, coarse, freeze, sha
from pilot import MODEL, PRICE_IN, PRICE_OUT, api_key, load_page, small_png

POLICIES = ("unverified", "generic", "round_trip")
FINAL_SEEDS = tuple(range(10, 30))
DEV_SEEDS = (0, 1)
RUNS = (1, 2, 3)
CAP_USD = 2.0
SHARD_CAP_USD = 0.45  # Four shards + prior spend remain below the $2 overall cap.
MAX_BROWSER_ACTIONS = 3
ACTION_SCHEMA = {"type":"object","properties":{
    "action":{"type":"string","enum":["done","type","click","hover","wait"]},
    "x":{"type":"number"},"y":{"type":"number"},
    "text":{"type":"string"},"ms":{"type":"number"},"value":{"type":"number"}},
    "required":["action"],"additionalProperties":False}
SYSTEM = (
    "You control a browser from a 900 by 600 screenshot. Follow the instruction visible "
    "near the top. You have already made an initial correct decision, but the browser "
    "harness may have mishandled it. You will receive tool feedback and a new screenshot. "
    "Return exactly one JSON object, no prose. Options: "
    "{\"action\":\"done\"} if the task is complete; for a chart value use "
    "{\"action\":\"done\",\"value\":number}. To act, use "
    "{\"action\":\"type\",\"text\":\"exact name\"}, "
    "{\"action\":\"click\",\"x\":number,\"y\":number}, "
    "{\"action\":\"hover\",\"x\":number,\"y\":number}, or "
    "{\"action\":\"wait\",\"ms\":number}. Coordinates refer to the 900 by 600 image. "
    "A screenshot may show a different state from the text feedback; decide from both. "
    "Do not claim completion unless the visible evidence supports it."
)


def parse(reply):
    match = re.search(r"\{.*?\}", reply, re.S)
    if not match:
        return None
    try:
        item = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    kind = item.get("action")
    if kind == "done":
        return item
    if kind == "type" and isinstance(item.get("text"), str):
        return item
    if kind in ("click", "hover") and all(isinstance(item.get(k),(int,float)) and 0<=item[k]<=bound
                                          for k,bound in (("x",900),("y",600))):
        return item
    if kind == "wait" and isinstance(item.get("ms"),(int,float)) and 0<=item["ms"]<=1000:
        return item
    return None


def ask(client, screenshot, previous, feedback, history, remaining, spent):
    if spent + .005 >= CAP_USD:
        raise RuntimeError(f"$2 hard cap would be approached: ${spent:.4f}")
    note = (f"Previous action: {json.dumps(previous)}\nHarness feedback: {feedback}\n"
            f"History: {json.dumps(history[-3:])}\nBrowser actions remaining: {remaining}. "
            "You may say done now. If none remain, you must say done or explain failure with "
            "{\"action\":\"done\"}; the result will be scored from the page and your answer.")
    started = time.monotonic()
    resp = client.messages.create(
        model=MODEL,max_tokens=300,thinking={"type":"disabled"},system=SYSTEM,
        output_config={"format":{"type":"json_schema","schema":ACTION_SCHEMA}},
        messages=[{"role":"user","content":[
            {"type":"text","text":note},
            {"type":"image","source":{"type":"base64","media_type":"image/png",
                                       "data":base64.b64encode(screenshot).decode("ascii")}}
        ]}]
    )
    reply = "".join(block.text for block in resp.content if getattr(block,"type",None)=="text")
    usage = {"input_tokens":resp.usage.input_tokens,"output_tokens":resp.usage.output_tokens,
             "latency_s":round(time.monotonic()-started,3),"stop_reason":resp.stop_reason}
    usage["cost_usd"]=(usage["input_tokens"]*PRICE_IN+usage["output_tokens"]*PRICE_OUT)/1_000_000
    return reply,usage


def page_goal(page, cfg):
    task=cfg["task"]
    if task=="search_token":
        return page.locator("#status").inner_text()=="Found "+cfg["target"]
    if task=="scaled_click":
        return page.locator("#status").inner_text()=="Selected Item "+str(cfg["target_index"])
    if task=="frame_feedback":
        selected=page.frame_locator("#rows").locator(".selected")
        return bool(selected.count() and selected.first.get_attribute("id")==cfg["target"])
    if task=="hover_value":
        return page.locator("#tooltip").is_visible()
    return False


def take_action(page,cfg,action):
    """Faulty harness executor. Returns raw feedback and executed CSS point."""
    kind=action["action"]
    task=cfg["task"]
    executed=None
    if kind=="type" and task=="search_token":
        page.locator("#query").fill(action["text"]+"[im_end]")
        page.locator("#submit").click()
    elif kind=="click":
        scale=1 if task=="scaled_click" else 4/3
        executed=[round(action["x"]*scale,2),round(action["y"]*scale,2)]
        page.mouse.click(*executed)
    elif kind=="hover":
        executed=[round(action["x"]*4/3,2),round(action["y"]*4/3,2)]
        page.mouse.move(*executed)
        page.wait_for_timeout(10 if task=="hover_value" else 50)
    elif kind=="wait":
        page.wait_for_timeout(min(1000,max(0,int(action["ms"]))))
    else:
        return "Unsupported action",executed
    if task=="frame_feedback":
        page.wait_for_timeout(30)
        return "No detectable change",executed
    if task=="hover_value":
        return "Observation captured",executed
    return page.locator("#status").inner_text(),executed


def policy_feedback(page,cfg,policy,before,after,raw,action,executed):
    if policy=="unverified":
        return "Tool feedback: "+raw
    if policy=="generic":
        changed=(before["url"]!=after["url"] or before["main_state"]!=after["main_state"]
                 or abs(before["text_length"]-after["text_length"])>5)
        return "Tool feedback: "+raw+". Generic top-page check: "+("change seen" if changed else "no change seen")+"."
    task=cfg["task"]
    if task=="search_token":
        value=page.locator("#query").input_value()
        return (f"Round-trip check: search field contains {value!r}; requested exact name "
                f"{cfg['target']!r}; page says {raw!r}.")
    if task=="scaled_click":
        target=page.locator("#button-"+str(cfg["target_index"]))
        box=target.bounding_box()
        centre=(round(box["x"]+box["width"]/2,2),round(box["y"]+box["height"]/2,2))
        hit=page.evaluate("([x,y])=>document.elementFromPoint(x,y)?.textContent",executed) if executed else None
        return (f"Round-trip check: requested Item {cfg['target_index']}; executed CSS point {executed} "
                f"hit {hit!r}; requested target's CSS center is {centre}; page says {raw!r}.")
    if task=="frame_feedback":
        selected=page.frame_locator("#rows").locator(".selected")
        actual=selected.first.get_attribute("id") if selected.count() else None
        return (f"Round-trip check: frame selected {actual!r}; requested {cfg['target']!r}. "
                f"Raw tool feedback said {raw!r}.")
    visible=page.locator("#tooltip").is_visible()
    return (f"Round-trip check: chart tooltip visible in this observation: {visible}. "
            "If missing, a short wait can reveal a delayed tooltip.")


def episode(browser,base,cfg,tape,policy,run,client,spent,shots):
    task,seed=cfg["task"],cfg["seed"]
    page=load_page(browser,base,cfg)
    steps=[]; history=[]; actions=0; usage=[]; final=None
    started=time.monotonic()
    action=tape["parsed_action"]
    for turn in range(MAX_BROWSER_ACTIONS):
        if action is None or action.get("action") not in ("type","click","hover","wait"):
            break
        before=coarse(page)
        raw,executed=take_action(page,cfg,action)
        after=coarse(page)
        # Capture the next view before reading the independent page ledger.
        screenshot=small_png(page.screenshot())
        captured_goal=page_goal(page,cfg)
        shot=shots/f"{task}_{seed}_{policy}_run{run}_step{turn+1}.png"
        shot.write_bytes(screenshot)
        feedback=policy_feedback(page,cfg,policy,before,after,raw,action,executed)
        ledger=page.evaluate("window.__ledger")
        step={"action":action,"raw_feedback":raw,"policy_feedback":feedback,
              "executed_css":executed,"before":before,"after":after,
              "ledger":ledger,"screenshot":str(shot.relative_to(ROOT)),
              "page_goal_at_capture":captured_goal}
        steps.append(step); actions+=1
        history.append({"action":action,"feedback":feedback})
        reply,u=ask(client,screenshot,action,feedback,history,MAX_BROWSER_ACTIONS-actions,spent+sum(x["cost_usd"] for x in usage))
        usage.append(u)
        decision=parse(reply)
        step["model_reply"]=reply;step["model_decision"]=decision;step["usage"]=u
        if decision is None:
            final={"action":"unparsed"};break
        if decision["action"]=="done":
            final=decision;break
        action=decision
    goal=page_goal(page,cfg)
    if task=="hover_value":
        success=bool(final and final.get("action")=="done" and final.get("value")==cfg["value"]
                     and steps and steps[-1]["page_goal_at_capture"])
    else:
        success=bool(final and final.get("action")=="done" and goal)
    record={"task":task,"seed":seed,"run":run,"policy":policy,
            "recorded_initial_reply":tape["model_reply"],"recorded_initial_action":tape["parsed_action"],
            "steps":steps,"browser_actions":actions,"model_calls":len(usage),
            "final_decision":final,"page_goal":goal,"task_success":success,
            "input_tokens":sum(x["input_tokens"] for x in usage),
            "output_tokens":sum(x["output_tokens"] for x in usage),
            "cost_usd":sum(x["cost_usd"] for x in usage),
            "elapsed_s":round(time.monotonic()-started,3)}
    page.close()
    return record


def stamp():
    return (f"manifest_sha256 {sha(ROOT/'manifest.json')}\n"
            f"phase_b_sha256 {sha(ROOT/'results/phase_b.jsonl')}\n"
            f"phase_c_code_sha256 {sha(ROOT/'phase_c.py')}\n"
            f"prompt_sha256 {hashlib.sha256(SYSTEM.encode()).hexdigest()}\n"
            f"model {MODEL}\npolicies {'|'.join(POLICIES)}\nseeds 10-29\nruns 1-3\n"
            f"execution four seed shards, ${SHARD_CAP_USD} cap per shard\n")


def freeze_phase_c():
    freeze()
    path=ROOT/"PHASE_C_FROZEN.txt"
    value=stamp()
    if path.exists() and path.read_text()!=value:
        raise RuntimeError("Phase C inputs or implementation changed after freezing")
    path.write_text(value)


def summarize(rows):
    by={}
    for task in TASKS:
        by[task]={}
        for policy in POLICIES:
            group=[r for r in rows if r["task"]==task and r["policy"]==policy]
            per_run={str(run):sum(r["task_success"] for r in group if r["run"]==run)
                     for run in RUNS}
            by[task][policy]={"episodes":len(group),"successes":sum(r["task_success"] for r in group),
                "success_by_run":per_run,
                "mean_browser_actions":round(statistics.mean(r["browser_actions"] for r in group),3) if group else None,
                "median_elapsed_s":round(statistics.median(r["elapsed_s"] for r in group),3) if group else None,
                "cost_usd":round(sum(r["cost_usd"] for r in group),6)}
    return {"episodes":len(rows),"model_calls":sum(r["model_calls"] for r in rows),
            "input_tokens":sum(r["input_tokens"] for r in rows),
            "output_tokens":sum(r["output_tokens"] for r in rows),
            "phase_c_cost_usd":round(sum(r["cost_usd"] for r in rows),6),"by_task":by}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("dev","freeze","run"))
    ap.add_argument("--shard",type=int,choices=range(4),default=None)
    args=ap.parse_args()
    if args.mode=="freeze":
        freeze_phase_c();print((ROOT/"PHASE_C_FROZEN.txt").read_text());return
    if args.mode=="run":freeze_phase_c()
    configs={(c["task"],c["seed"]):c for c in freeze()}
    tape={(r["task"],r["seed"]):r for r in
          (json.loads(line) for line in (ROOT/"results/phase_b.jsonl").read_text().splitlines())}
    seeds=FINAL_SEEDS if args.mode=="run" else DEV_SEEDS
    if args.mode=="run" and args.shard is not None:
        seeds=tuple(seed for i,seed in enumerate(FINAL_SEEDS) if i%4==args.shard)
    # Development uses the real recorded pilot decisions on seeds 0 and 1.
    if args.mode=="dev":
        pilot_rows=[json.loads(line) for line in (ROOT/"results/pilot.jsonl").read_text().splitlines()]
        tape.update({(r["task"],r["seed"]):r for r in pilot_rows if not r["defect"]})
    name=(f"phase_c_shard{args.shard}.jsonl" if args.mode=="run" and args.shard is not None
          else "phase_c.jsonl" if args.mode=="run" else "phase_c_dev.jsonl")
    dest=ROOT/"results"/name
    rows=[json.loads(line) for line in dest.read_text().splitlines()] if dest.exists() else []
    done={(r["task"],r["seed"],r["policy"],r["run"]) for r in rows}
    previous_cost=sum(r["cost_usd"] for r in rows)
    other_cost=sum(json.loads(line)["usage"]["cost_usd"] for line in
                   (ROOT/"results/phase_b.jsonl").read_text().splitlines())
    other_cost+=json.loads((ROOT/"results/pilot.summary.json").read_text())["cost_usd"]
    for prior in (ROOT/"results/phase_c_dev.jsonl",
                  ROOT/"results/archive/phase_c_dev_v1_unstructured.jsonl",
                  ROOT/"results/archive/phase_c_v1_partial_serial.jsonl"):
        if prior.exists():
            other_cost+=sum(json.loads(line)["cost_usd"] for line in prior.read_text().splitlines())
    shots=ROOT/"results"/("phase_c_screenshots" if args.mode=="run" else "phase_c_dev_screenshots")
    shots.mkdir(parents=True,exist_ok=True)
    client=anthropic.Anthropic(api_key=api_key())
    class Quiet(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/"site"),**kw)
        def log_message(self,*a):pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as pw,dest.open("a") as out:
            browser=pw.chromium.launch(headless=True)
            for task in TASKS:
                for seed in seeds:
                    for policy in POLICIES:
                        for run in (RUNS if args.mode=="run" else (1,)):
                            key=(task,seed,policy,run)
                            if key in done:continue
                            spent=other_cost+previous_cost
                            if spent+.005>=CAP_USD:raise RuntimeError("$2 cap reached")
                            if args.shard is not None and previous_cost+.005>=SHARD_CAP_USD:
                                raise RuntimeError("Per-shard cap reached")
                            record=episode(browser,base,configs[(task,seed)],tape[(task,seed)],policy,run,
                                           client,spent,shots)
                            previous_cost+=record["cost_usd"]
                            out.write(json.dumps(record)+"\n");out.flush();rows.append(record)
                    if seed%5==4:print(f"{task} through seed {seed}: {len(rows)} episodes, ${previous_cost:.5f} Phase C",flush=True)
            browser.close()
    finally:
        server.shutdown()
    result=summarize(rows)
    path=dest.with_suffix(".summary.json")
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
