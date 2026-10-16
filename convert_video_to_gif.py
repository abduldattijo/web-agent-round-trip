"""Convert the continuous browser WebM to a compact GIF for sharing."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from audit import ROOT

SOURCE = ROOT / "figures" / "continuous_model_click_seed12.webm"
DEST = ROOT / "figures" / "continuous_model_click_seed12.gif"


def main():
    ffmpeg = shutil.which("ffmpeg") or str(Path.home() / "Library/Caches/ms-playwright/ffmpeg-1013/ffmpeg-mac")
    with tempfile.TemporaryDirectory() as temporary:
        pattern = Path(temporary) / "frame_%03d.png"
        subprocess.run([ffmpeg,"-hide_banner","-loglevel","error","-y","-i",str(SOURCE),
                        "-r","3",str(pattern)],check=True)
        paths = sorted(Path(temporary).glob("frame_*.png"))
        if not paths:
            raise RuntimeError("No video frames were extracted")
        frames = [Image.open(path).convert("RGB") for path in paths]
        frames[0].save(DEST,save_all=True,append_images=frames[1:],duration=333,loop=0,optimize=True)
    print(f"{DEST}: {len(frames)} frames")


if __name__ == "__main__": main()
