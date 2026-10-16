"""Continuous WebM replay of one recorded Phase B decision; no new model call."""
from __future__ import annotations

import json
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from audit import ROOT, freeze

SEED = 12
TASK = "scaled_click"


def label(page, message, x, y, color):
    page.evaluate("""({message,x,y,color}) => {
      document.querySelector('#evidence-banner')?.remove();
      document.querySelector('#evidence-point')?.remove();
      const banner=document.createElement('div'); banner.id='evidence-banner';
      banner.textContent=message;
      Object.assign(banner.style,{position:'fixed',left:'0',bottom:'0',right:'0',
        padding:'18px 24px',background:'#14212d',color:'white',font:'bold 23px Arial',
        zIndex:'99999',pointerEvents:'none'});
      const point=document.createElement('div'); point.id='evidence-point';
      Object.assign(point.style,{position:'fixed',left:(x-17)+'px',top:(y-17)+'px',
        width:'34px',height:'34px',border:'5px solid '+color,borderRadius:'50%',
        boxSizing:'border-box',zIndex:'99998',pointerEvents:'none'});
      document.body.append(banner,point);
    }""", {"message":message,"x":x,"y":y,"color":color})


def main():
    cfg = next(c for c in freeze() if c["task"] == TASK and c["seed"] == SEED)
    rows = [json.loads(line) for line in (ROOT/"results"/"phase_b.jsonl").read_text().splitlines()]
    row = next(r for r in rows if r["task"] == TASK and r["seed"] == SEED)
    if not row["clean"]["round_trip_success"] or row["defect"]["round_trip_success"]:
        raise RuntimeError("Chosen trace does not show a correct decision and faulty replay")
    action = row["parsed_action"]
    correct = (action["x"]*4/3, action["y"]*4/3)
    faulty = (action["x"], action["y"])
    class Quiet(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/"site"),**kw)
        def log_message(self,*a): pass
    server = ThreadingHTTPServer(("127.0.0.1",0),Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/index.html?cfg={quote(json.dumps(cfg,separators=(',',':')))}"
    out_dir = ROOT/"figures"
    out_dir.mkdir(exist_ok=True)
    video = out_dir/f"continuous_model_click_seed{SEED}.webm"
    meta = out_dir/f"continuous_model_click_seed{SEED}.json"
    try:
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width":1200,"height":800},
                                          record_video_dir=temporary,
                                          record_video_size={"width":900,"height":600})
            page = context.new_page()
            page.goto(url)
            label(page,"Clean replay: Haiku chose Item 15",*correct,"#00c853")
            page.wait_for_timeout(1300)
            page.mouse.click(*correct)
            page.wait_for_timeout(1800)
            clean_ledger = page.evaluate("window.__ledger")
            label(page,"Resetting the same page for faulty replay",*correct,"#00c853")
            page.wait_for_timeout(1000)
            page.goto(url)
            label(page,"Faulty replay: same decision, coordinates unscaled",*faulty,"#e53935")
            page.wait_for_timeout(1300)
            page.mouse.click(*faulty)
            page.wait_for_timeout(1800)
            faulty_ledger = page.evaluate("window.__ledger")
            label(page,"Actual click: Item 10. Intended: Item 15.",*faulty,"#e53935")
            page.wait_for_timeout(1800)
            recorded_video = page.video
            page.close()
            recorded_video.save_as(str(video))
            context.close(); browser.close()
    finally:
        server.shutdown()
    record = {"video":str(video.relative_to(ROOT)),"source_decision":"results/phase_b.jsonl",
              "task":TASK,"seed":SEED,"model":row["model"],"model_reply":row["model_reply"],
              "image_action":action,"clean_css":correct,"faulty_css":faulty,
              "clean_ledger":clean_ledger,"faulty_ledger":faulty_ledger,
              "note":"One continuous local browser recording. Text and point overlays were added for clarity; the model decision was recorded in Phase B."}
    meta.write_text(json.dumps(record,indent=2)+"\n")
    print(json.dumps(record,indent=2))


if __name__=="__main__": main()
