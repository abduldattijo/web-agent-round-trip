"""Render a compact PNG of Phase C task success from the frozen result summary."""
from __future__ import annotations

import json
from PIL import Image, ImageDraw, ImageFont

from audit import ROOT, TASKS

SOURCE=ROOT/"results"/"phase_c.summary.json"
DEST=ROOT/"figures"/"phase_c_success.png"
LABELS={"search_token":"Exact search","scaled_click":"Target click",
        "frame_feedback":"Iframe selection","hover_value":"Chart value"}
COLORS={"unverified":"#8b98a5","generic":"#447cb8","round_trip":"#268963"}


def main():
    data=json.loads(SOURCE.read_text())
    image=Image.new("RGB",(1400,850),"white")
    draw=ImageDraw.Draw(image)
    font="/System/Library/Fonts/Supplemental/Arial.ttf"
    title=ImageFont.truetype(font,34)
    normal=ImageFont.truetype(font,22)
    small=ImageFont.truetype(font,18)
    draw.text((50,35),"Did checking help the agent finish the task?",font=title,fill="#172532")
    draw.text((50,86),"Successes across 20 selected page layouts × 3 runs per policy",font=normal,fill="#526171")
    start_y=150
    for index,task in enumerate(TASKS):
        y=start_y+index*155
        draw.text((50,y),LABELS[task],font=normal,fill="#172532")
        for j,policy in enumerate(("unverified","generic","round_trip")):
            bar_y=y+36+j*32
            value=data["by_task"][task][policy]["successes"]
            draw.text((55,bar_y),policy.replace("_"," ").title(),font=small,fill="#3b4855")
            draw.rounded_rectangle((220,bar_y,1120,bar_y+21),radius=8,fill="#eef1f4")
            if value:
                draw.rounded_rectangle((220,bar_y,220+900*value/60,bar_y+21),radius=8,fill=COLORS[policy])
            draw.text((1140,bar_y-3),f"{value}/60",font=normal,fill="#172532")
    draw.line((50,786,1350,786),fill="#d3dbe2",width=2)
    draw.text((50,800),"Deliberately injected faults; checks could detect a failure without repairing it.",
              font=small,fill="#526171")
    DEST.parent.mkdir(exist_ok=True)
    image.save(DEST)
    print(DEST)


if __name__=="__main__":main()
