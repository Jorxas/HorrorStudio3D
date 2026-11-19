"""contact sheet of PNG files: python tools/demo_sheet.py out.png cols w img1 img2 ... (labels = file stems)"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
out, cols, w = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); files = sys.argv[4:]
ims = [Image.open(f).convert('RGB') for f in files]; h = int(w * ims[0].height / ims[0].width)
rows = (len(ims) + cols - 1) // cols; sheet = Image.new('RGB', (cols * w, rows * h), (20, 20, 20))
for i, im in enumerate(ims):
    t = im.resize((w, h)); d = ImageDraw.Draw(t); d.rectangle((0, 0, w, 14), fill=(0, 0, 0)); d.text((3, 1), Path(files[i]).stem, fill=(255, 255, 0)); sheet.paste(t, ((i % cols) * w, (i // cols) * h))
sheet.save(out); print(out, sheet.size)
