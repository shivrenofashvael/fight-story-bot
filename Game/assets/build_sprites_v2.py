#!/usr/bin/env python3
"""
Build sprite strips with UNIFORM frame size per character.
Each character gets one consistent frameW x frameH across ALL animations.
"""
from PIL import Image
import os, glob, json

OUT = os.path.dirname(__file__) + '/sprites'

def find_bbox(frames):
    minx, miny = 9999, 9999
    maxx, maxy = 0, 0
    for f in frames:
        bb = f.getbbox()
        if bb:
            minx = min(minx, bb[0]); miny = min(miny, bb[1])
            maxx = max(maxx, bb[2]); maxy = max(maxy, bb[3])
    return (minx, miny, maxx, maxy)

def load_grid_sheet(path, cell_w=600, cell_h=600):
    img = Image.open(path).convert('RGBA')
    cols = img.width // cell_w
    rows = img.height // cell_h
    frames = []
    for r in range(rows):
        for c in range(cols):
            frame = img.crop((c*cell_w, r*cell_h, (c+1)*cell_w, (r+1)*cell_h))
            if frame.getbbox():
                frames.append(frame)
    return frames

def load_frame_dir(path):
    files = sorted(glob.glob(os.path.join(path, '*.png')))
    return [Image.open(f).convert('RGBA') for f in files]

def sample_frames(frames, max_frames):
    if len(frames) <= max_frames:
        return frames
    step = len(frames) / max_frames
    return [frames[int(i * step)] for i in range(max_frames)]

def build_character(name, anim_sources, load_fn, out_dir):
    """
    1. Load all animations and find per-anim bboxes
    2. Compute a unified frame size (max width/height across all anims)
    3. Center each frame in the unified cell and build strips
    """
    os.makedirs(out_dir, exist_ok=True)

    # Phase 1: Load all frames and find bboxes
    all_anims = {}
    all_bboxes = {}
    for anim_name, (source, max_f, fps) in anim_sources.items():
        raw_frames = load_fn(source)
        if not raw_frames:
            print(f"  SKIP {anim_name}: no frames")
            continue
        frames = sample_frames(raw_frames, max_f)
        bbox = find_bbox(frames)
        all_anims[anim_name] = (frames, max_f, fps)
        all_bboxes[anim_name] = bbox

    # Phase 2: Find global frame size
    # We want uniform height (character stands same height in all anims)
    # Width can vary but we'll use the max to be safe
    max_w = 0
    max_h = 0
    # Use the bottom-anchored approach: measure from bottom of original frame
    for anim_name, bbox in all_bboxes.items():
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_w = max(max_w, w)
        max_h = max(max_h, h)

    # Add padding
    pad = 10
    fw = max_w + pad * 2
    fh = max_h + pad * 2

    print(f"  Unified frame size: {fw}x{fh}")

    # Phase 3: Build strips with unified frame size
    # Anchor: bottom-center of each frame aligns with bottom-center of cell
    info = {}
    for anim_name, (frames, max_f, fps) in all_anims.items():
        bbox = all_bboxes[anim_name]
        cropped_frames = [f.crop(bbox) for f in frames]
        cw = bbox[2] - bbox[0]
        ch = bbox[3] - bbox[1]

        strip = Image.new('RGBA', (fw * len(cropped_frames), fh), (0,0,0,0))
        for i, cf in enumerate(cropped_frames):
            # Bottom-center align
            dx = (fw - cw) // 2
            dy = fh - ch  # align to bottom
            strip.paste(cf, (i * fw + dx, dy))

        out_path = os.path.join(out_dir, f'{anim_name}.png')
        strip.save(out_path, optimize=True)
        info[anim_name] = {'frames': len(cropped_frames), 'fps': fps}
        print(f"  {anim_name}: {len(cropped_frames)}f -> {out_path}")

    return {'fw': fw, 'fh': fh, 'anims': info}


def main():
    # === YELLOW MAN ===
    ym_base = OUT + '/yellowman-stableimage/yellowman/spritesheet'
    ym_anims = {
        'idle':     (ym_base + '/normal idle.png', 10, 8),
        'walk':     (ym_base + '/normal run.png', 8, 10),
        'punch':    (ym_base + '/light punch.png', 8, 14),
        'kick':     (ym_base + '/stand high kick.png', 8, 12),
        'uppercut': (ym_base + '/high punch.png', 8, 11),
        'hit':      (ym_base + '/body hit.png', 5, 10),
        'ko':       (ym_base + '/knockdown.png', 10, 8),
        'victory':  (ym_base + '/idle.png', 10, 6),
    }

    def load_ym(path):
        cell_w = 610 if 'high kick' in path else 600
        return load_grid_sheet(path, cell_w, 600)

    print("=== YELLOW MAN ===")
    ym = build_character('yellowman', ym_anims, load_ym, OUT + '/fighter_yellowman')

    # === BOXER ===
    bx_base = OUT + '/boxer-opengameart/Boxer Game Sprite OGA'
    bx_anims = {
        'idle':     (bx_base + '/1-Idle', 8, 8),
        'walk':     (bx_base + '/2-Walk/1-Forward', 8, 10),
        'punch':    (bx_base + '/3-Punch/1-JabRight', 8, 14),
        'kick':     (bx_base + '/3-Punch/2-JabLeft', 8, 12),
        'uppercut': (bx_base + '/3-Punch/3-Uppercut', 8, 11),
        'hit':      (bx_base + '/5-Hurt/1-Hurt', 5, 10),
        'ko':       (bx_base + '/6-KO', 8, 8),
        'victory':  (bx_base + '/1-Idle', 8, 6),
    }

    print("\n=== BOXER ===")
    bx = build_character('boxer', bx_anims, load_frame_dir, OUT + '/fighter_boxer')

    # Print config for characters.js
    print("\n\n=== CONFIG FOR characters.js ===")
    print(f"// Yellow Man: frameW={ym['fw']}, frameH={ym['fh']}")
    for k, v in ym['anims'].items():
        print(f"//   {k}: {{ file: '{k}.png', frames: {v['frames']}, fps: {v['fps']} }}")
    print(f"// Boxer: frameW={bx['fw']}, frameH={bx['fh']}")
    for k, v in bx['anims'].items():
        print(f"//   {k}: {{ file: '{k}.png', frames: {v['frames']}, fps: {v['fps']} }}")

if __name__ == '__main__':
    main()
