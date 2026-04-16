// ============================================================
// IRON FIST - Character Definitions (Sprite-Based)
// ============================================================

const CHARACTERS = [
    {
        id: 'striker',
        name: 'STRIKER',
        title: 'The Enforcer',
        stats: { health: 100, speed: 4.0, power: 1.1, defense: 1.0 },
        sprite: {
            folder: 'assets/sprites/fighter_yellowman',
            frameW: 500, frameH: 412,
            scale: 0.55,
            anchorX: 0.5, anchorY: 1.0,
            anims: {
                idle:     { file: 'idle.png', frames: 10, fps: 8 },
                walk:     { file: 'walk.png', frames: 8, fps: 10 },
                punch:    { file: 'punch.png', frames: 8, fps: 14 },
                kick:     { file: 'kick.png', frames: 8, fps: 12 },
                uppercut: { file: 'uppercut.png', frames: 8, fps: 11 },
                hit:      { file: 'hit.png', frames: 5, fps: 10 },
                ko:       { file: 'ko.png', frames: 10, fps: 8 },
                victory:  { file: 'victory.png', frames: 10, fps: 6 }
            }
        }
    },
    {
        id: 'bruiser',
        name: 'BRUISER',
        title: 'The Knockout King',
        stats: { health: 120, speed: 3.4, power: 1.3, defense: 1.15 },
        sprite: {
            folder: 'assets/sprites/fighter_boxer',
            frameW: 653, frameH: 667,
            scale: 0.38,
            anchorX: 0.5, anchorY: 1.0,
            anims: {
                idle:     { file: 'idle.png', frames: 8, fps: 8 },
                walk:     { file: 'walk.png', frames: 8, fps: 10 },
                punch:    { file: 'punch.png', frames: 8, fps: 14 },
                kick:     { file: 'kick.png', frames: 8, fps: 12 },
                uppercut: { file: 'uppercut.png', frames: 8, fps: 11 },
                hit:      { file: 'hit.png', frames: 5, fps: 10 },
                ko:       { file: 'ko.png', frames: 8, fps: 8 },
                victory:  { file: 'victory.png', frames: 8, fps: 6 }
            }
        }
    },
    {
        id: 'viper',
        name: 'VIPER',
        title: 'The Serpent',
        stats: { health: 90, speed: 4.6, power: 1.15, defense: 0.9 },
        sprite: {
            folder: 'assets/sprites/fighter_yellowman',
            frameW: 500, frameH: 412,
            scale: 0.55,
            anchorX: 0.5, anchorY: 1.0,
            hueShift: 90,
            anims: {
                idle:     { file: 'idle.png', frames: 10, fps: 8 },
                walk:     { file: 'walk.png', frames: 8, fps: 10 },
                punch:    { file: 'punch.png', frames: 8, fps: 14 },
                kick:     { file: 'kick.png', frames: 8, fps: 12 },
                uppercut: { file: 'uppercut.png', frames: 8, fps: 11 },
                hit:      { file: 'hit.png', frames: 5, fps: 10 },
                ko:       { file: 'ko.png', frames: 10, fps: 8 },
                victory:  { file: 'victory.png', frames: 10, fps: 6 }
            }
        }
    },
    {
        id: 'titan',
        name: 'TITAN',
        title: 'The Colossus',
        stats: { health: 130, speed: 3.0, power: 1.4, defense: 1.2 },
        sprite: {
            folder: 'assets/sprites/fighter_boxer',
            frameW: 653, frameH: 667,
            scale: 0.38,
            anchorX: 0.5, anchorY: 1.0,
            hueShift: 200,
            anims: {
                idle:     { file: 'idle.png', frames: 8, fps: 8 },
                walk:     { file: 'walk.png', frames: 8, fps: 10 },
                punch:    { file: 'punch.png', frames: 8, fps: 14 },
                kick:     { file: 'kick.png', frames: 8, fps: 12 },
                uppercut: { file: 'uppercut.png', frames: 8, fps: 11 },
                hit:      { file: 'hit.png', frames: 5, fps: 10 },
                ko:       { file: 'ko.png', frames: 8, fps: 8 },
                victory:  { file: 'victory.png', frames: 8, fps: 6 }
            }
        }
    },
    {
        id: 'blaze',
        name: 'BLAZE',
        title: 'The Inferno',
        stats: { health: 95, speed: 4.3, power: 1.25, defense: 0.95 },
        sprite: {
            folder: 'assets/sprites/fighter_yellowman',
            frameW: 500, frameH: 412,
            scale: 0.55,
            anchorX: 0.5, anchorY: 1.0,
            hueShift: 180,
            anims: {
                idle:     { file: 'idle.png', frames: 10, fps: 8 },
                walk:     { file: 'walk.png', frames: 8, fps: 10 },
                punch:    { file: 'punch.png', frames: 8, fps: 14 },
                kick:     { file: 'kick.png', frames: 8, fps: 12 },
                uppercut: { file: 'uppercut.png', frames: 8, fps: 11 },
                hit:      { file: 'hit.png', frames: 5, fps: 10 },
                ko:       { file: 'ko.png', frames: 10, fps: 8 },
                victory:  { file: 'victory.png', frames: 10, fps: 6 }
            }
        }
    },
    {
        id: 'phantom',
        name: 'PHANTOM',
        title: 'The Shadow',
        stats: { health: 105, speed: 3.8, power: 1.2, defense: 1.05 },
        sprite: {
            folder: 'assets/sprites/fighter_boxer',
            frameW: 653, frameH: 667,
            scale: 0.38,
            anchorX: 0.5, anchorY: 1.0,
            hueShift: 100,
            anims: {
                idle:     { file: 'idle.png', frames: 8, fps: 8 },
                walk:     { file: 'walk.png', frames: 8, fps: 10 },
                punch:    { file: 'punch.png', frames: 8, fps: 14 },
                kick:     { file: 'kick.png', frames: 8, fps: 12 },
                uppercut: { file: 'uppercut.png', frames: 8, fps: 11 },
                hit:      { file: 'hit.png', frames: 5, fps: 10 },
                ko:       { file: 'ko.png', frames: 8, fps: 8 },
                victory:  { file: 'victory.png', frames: 8, fps: 6 }
            }
        }
    }
];

// Attack configs: hitbox relative to character center (scaled pixels)
// hitFrame = which frame the hit activates on (0-indexed)
const ATTACK_DATA = {
    punch:    { damage: 8,  knockback: 10, hitFrame: 4, hitbox: { x: 50, y: -90, w: 70, h: 60 } },
    kick:     { damage: 12, knockback: 16, hitFrame: 4, hitbox: { x: 55, y: -50, w: 80, h: 60 } },
    uppercut: { damage: 18, knockback: 22, hitFrame: 4, hitbox: { x: 40, y: -120, w: 65, h: 80 } }
};
