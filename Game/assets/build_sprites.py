#!/usr/bin/env python3
"""
Convert Yellow Man grid sheets + Boxer individual frames into
optimized horizontal sprite strips for the IRON FIST game engine.
"""
from PIL import Image
import os, glob

OUT = os.path.dirname(__file__) + '/sprites'

def find_bbox(frames):
    """Find tight bounding box across all frames."""
    minx, miny = 9999, 9999
    maxx, maxy = 0, 0
    for f in frames:
        bb = f.getbbox()
        if bb:
            minx = min(minx, bb[0]); miny = min(miny, bb[1])
            maxx = max(maxx, bb[2]); maxy = max(maxy, bb[3])
    pad = 8
    return (max(0, minx-pad), max(0, miny-pad), maxx+pad, maxy+pad)

def crop_and_strip(frames, max_frames=None, sample_step=1):
    """Crop frames to tight bbox and create horizontal strip."""
    if sample_step > 1:
        frames = frames[::sample_step]
    if max_frames and len(frames) > max_frames:
        # Evenly sample to max_frames
        step = len(frames) / max_frames
        frames = [frames[int(i * step)] for i in range(max_frames)]

    bbox = find_bbox(frames)
    fw = bbox[2] - bbox[0]
    fh = bbox[3] - bbox[1]

    strip = Image.new('RGBA', (fw * len(frames), fh), (0,0,0,0))
    for i, f in enumerate(frames):
        cropped = f.crop(bbox)
        strip.paste(cropped, (i * fw, 0))

    return strip, fw, fh, len(frames)

def load_grid_sheet(path, cell_w=600, cell_h=600):
    """Load a grid spritesheet and return list of frame Images."""
    img = Image.open(path).convert('RGBA')
    cols = img.width // cell_w
    rows = img.height // cell_h
    frames = []
    for r in range(rows):
        for c in range(cols):
            frame = img.crop((c*cell_w, r*cell_h, (c+1)*cell_w, (r+1)*cell_h))
            if frame.getbbox():  # Skip empty frames
                frames.append(frame)
    return frames

def load_frame_dir(path):
    """Load individual PNGs from a directory, sorted."""
    files = sorted(glob.glob(os.path.join(path, '*.png')))
    return [Image.open(f).convert('RGBA') for f in files]

def build_yellowman():
    """Build Yellow Man sprite strips from grid sheets."""
    base = OUT + '/yellowman-stableimage/yellowman/spritesheet'
    out_dir = OUT + '/fighter_yellowman'
    os.makedirs(out_dir, exist_ok=True)

    # Animation mapping: game_anim -> (sheet_file, max_frames, fps)
    anims = {
        'idle':     ('normal idle.png', 10, 8),
        'walk':     ('normal run.png', 8, 10),
        'punch':    ('light punch.png', 8, 14),
        'kick':     ('stand high kick.png', 8, 12),
        'uppercut': ('high punch.png', 8, 11),
        'hit':      ('body hit.png', 5, 10),
        'ko':       ('knockdown.png', 10, 8),
        'victory':  ('idle.png', 10, 6),
    }

    info = {}
    for anim_name, (sheet_file, max_f, fps) in anims.items():
        path = os.path.join(base, sheet_file)
        if not os.path.exists(path):
            print(f"  SKIP {anim_name}: {sheet_file} not found")
            continue

        # Stand high kick has 610px wide cells, others 600
        cell_w = 610 if 'high kick' in sheet_file else 600
        frames = load_grid_sheet(path, cell_w, 600)
        strip, fw, fh, nf = crop_and_strip(frames, max_frames=max_f)

        out_path = os.path.join(out_dir, f'{anim_name}.png')
        strip.save(out_path, optimize=True)
        info[anim_name] = {'frames': nf, 'fw': fw, 'fh': fh, 'fps': fps}
        print(f"  {anim_name}: {nf} frames @ {fw}x{fh} -> {out_path}")

    return info

def build_boxer():
    """Build Boxer sprite strips from individual frame PNGs."""
    base = OUT + '/boxer-opengameart/Boxer Game Sprite OGA'
    out_dir = OUT + '/fighter_boxer'
    os.makedirs(out_dir, exist_ok=True)

    # Animation mapping: game_anim -> (subfolder_path, max_frames, fps)
    anims = {
        'idle':     ('1-Idle', 8, 8),
        'walk':     ('2-Walk/1-Forward', 8, 10),
        'punch':    ('3-Punch/1-JabRight', 8, 14),
        'kick':     ('3-Punch/2-JabLeft', 8, 12),
        'uppercut': ('3-Punch/3-Uppercut', 8, 11),
        'hit':      ('5-Hurt/1-Hurt', 5, 10),
        'ko':       ('6-KO', 8, 8),
        'victory':  ('1-Idle', 8, 6),
    }

    info = {}
    for anim_name, (sub_path, max_f, fps) in anims.items():
        full_path = os.path.join(base, sub_path)
        if not os.path.isdir(full_path):
            print(f"  SKIP {anim_name}: {sub_path} not found")
            continue

        frames = load_frame_dir(full_path)
        if not frames:
            print(f"  SKIP {anim_name}: no frames")
            continue

        strip, fw, fh, nf = crop_and_strip(frames, max_frames=max_f)

        out_path = os.path.join(out_dir, f'{anim_name}.png')
        strip.save(out_path, optimize=True)
        info[anim_name] = {'frames': nf, 'fw': fw, 'fh': fh, 'fps': fps}
        print(f"  {anim_name}: {nf} frames @ {fw}x{fh} -> {out_path}")

    return info

if __name__ == '__main__':
    print("=== Building Yellow Man ===")
    ym_info = build_yellowman()
    print(f"\nYellow Man summary: fw={ym_info['idle']['fw']}, fh={ym_info['idle']['fh']}")

    print("\n=== Building Boxer ===")
    bx_info = build_boxer()
    print(f"\nBoxer summary: fw={bx_info['idle']['fw']}, fh={bx_info['idle']['fh']}")

    print("\n=== DONE ===")
    print("\nYellow Man config:")
    for k, v in ym_info.items():
        print(f"  {k}: {{ file: '{k}.png', frames: {v['frames']}, fps: {v['fps']} }}")
    print("\nBoxer config:")
    for k, v in bx_info.items():
        print(f"  {k}: {{ file: '{k}.png', frames: {v['frames']}, fps: {v['fps']} }}")
