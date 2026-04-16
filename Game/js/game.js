// ============================================================
// IRON FIST - Game Engine (Assets, Fighter, Input, States, Loop)
// ============================================================

// ================================================================
// ASSET LOADER
// ================================================================
class AssetLoader {
    constructor() { this.images = {}; this.loaded = 0; this.total = 0; }

    loadImage(key, src) {
        this.total++;
        return new Promise(resolve => {
            const img = new Image();
            img.onload = () => { this.images[key] = img; this.loaded++; resolve(img); };
            img.onerror = () => { console.warn('Failed to load:', src); this.loaded++; resolve(null); };
            img.src = src;
        });
    }

    async loadAll() {
        const promises = [];
        const srcToKey = {};
        for (const char of CHARACTERS) {
            for (const [animName, animData] of Object.entries(char.sprite.anims)) {
                const src = `${char.sprite.folder}/${animData.file}`;
                const key = `${char.id}_${animName}`;
                if (srcToKey[src]) {
                    // Reuse already-loaded image for hue-shifted variants
                    this.total++;
                    const origKey = srcToKey[src];
                    promises.push(new Promise(resolve => {
                        const check = () => {
                            if (this.images[origKey]) {
                                this.images[key] = this.images[origKey];
                                this.loaded++;
                                resolve();
                            } else setTimeout(check, 10);
                        };
                        check();
                    }));
                } else {
                    srcToKey[src] = key;
                    promises.push(this.loadImage(key, src));
                }
            }
        }
        await Promise.all(promises);
    }

    get(key) { return this.images[key]; }
    get progress() { return this.total > 0 ? this.loaded / this.total : 0; }
}

// ================================================================
// AUDIO MANAGER
// ================================================================
class AudioManager {
    constructor() {
        this.ctx = null; this.enabled = true;
        try { this.ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) { this.enabled = false; }
    }
    resume() { if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume(); }

    _noise(dur, vol, freq) {
        if (!this.enabled) return;
        const c = this.ctx, o = c.createOscillator(), g = c.createGain();
        o.connect(g); g.connect(c.destination);
        o.frequency.setValueAtTime(freq, c.currentTime);
        o.frequency.exponentialRampToValueAtTime(freq*0.3, c.currentTime+dur);
        g.gain.setValueAtTime(vol, c.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, c.currentTime+dur);
        o.type = 'sawtooth'; o.start(c.currentTime); o.stop(c.currentTime+dur);
    }

    playHit(power) {
        if (!this.enabled) return;
        this._noise(0.12, 0.25*power, 150);
        const c = this.ctx, n = c.sampleRate*0.08;
        const buf = c.createBuffer(1, n, c.sampleRate);
        const d = buf.getChannelData(0);
        for (let i = 0; i < n; i++) d[i] = (Math.random()*2-1)*(1-i/n);
        const s = c.createBufferSource(), g = c.createGain();
        s.buffer = buf; s.connect(g); g.connect(c.destination);
        g.gain.setValueAtTime(0.18*power, c.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, c.currentTime+0.08);
        s.start(c.currentTime);
    }

    playSwing() { if (this.enabled) this._noise(0.15, 0.08, 300); }

    playSelect() {
        if (!this.enabled) return;
        const c = this.ctx, o = c.createOscillator(), g = c.createGain();
        o.connect(g); g.connect(c.destination);
        o.frequency.setValueAtTime(500, c.currentTime);
        o.frequency.setValueAtTime(700, c.currentTime+0.06);
        g.gain.setValueAtTime(0.1, c.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, c.currentTime+0.12);
        o.type = 'square'; o.start(c.currentTime); o.stop(c.currentTime+0.12);
    }

    playKO() { if (this.enabled) for (let i=0;i<3;i++) setTimeout(()=>this._noise(0.3,0.2,100-i*20), i*100); }

    playFight() {
        if (!this.enabled) return;
        const c = this.ctx, o = c.createOscillator(), g = c.createGain();
        o.connect(g); g.connect(c.destination);
        o.frequency.setValueAtTime(250, c.currentTime);
        o.frequency.linearRampToValueAtTime(500, c.currentTime+0.15);
        g.gain.setValueAtTime(0.15, c.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, c.currentTime+0.3);
        o.type = 'sawtooth'; o.start(c.currentTime); o.stop(c.currentTime+0.3);
    }
}

// ================================================================
// INPUT HANDLER
// ================================================================
class InputHandler {
    constructor() {
        this.keys = {};
        window.addEventListener('keydown', e => { this.keys[e.code] = true; e.preventDefault(); });
        window.addEventListener('keyup', e => { this.keys[e.code] = false; e.preventDefault(); });
    }
    isDown(code) { return !!this.keys[code]; }
    consume(code) { const v = !!this.keys[code]; this.keys[code] = false; return v; }
}

// ================================================================
// FIGHTER CLASS (Sprite-Based)
// ================================================================
class Fighter {
    constructor(charDef, playerNum, assets) {
        this.character = charDef;
        this.playerNum = playerNum;
        this.assets = assets;
        this.maxHealth = charDef.stats.health;
        this.health = this.maxHealth;
        this.x = 0; this.y = 0; this.vx = 0;
        this.facing = playerNum === 1 ? 1 : -1;
        this.state = 'idle';
        this.spriteAnim = 'idle';
        this.animTime = 0;
        this.frameIndex = 0;
        this.hitFlash = 0;
        this.canAct = true;
        this.hitRegistered = false;
    }

    reset(x, y, facing) {
        this.health = this.maxHealth;
        this.x = x; this.y = y; this.facing = facing;
        this.vx = 0; this.state = 'idle'; this.spriteAnim = 'idle';
        this.animTime = 0; this.frameIndex = 0;
        this.hitFlash = 0; this.canAct = true; this.hitRegistered = false;
    }

    startAttack(type) {
        if (!this.canAct || this.state === 'hit' || this.state === 'ko') return;
        if (this.state === 'punch' || this.state === 'kick' || this.state === 'uppercut') return;
        this.state = type;
        this.spriteAnim = type;
        this.animTime = 0;
        this.frameIndex = 0;
        this.hitRegistered = false;
        this.canAct = false;
    }

    takeHit(damage, knockback, attacker) {
        const def = this.character.stats.defense || 1;
        const pow = attacker.character.stats.power || 1;
        const actualDmg = Math.round(damage * pow / def);
        this.health = Math.max(0, this.health - actualDmg);
        this.vx = -this.facing * knockback * 2;
        this.hitFlash = 0.15;

        if (this.health <= 0) {
            this.state = 'ko'; this.spriteAnim = 'ko';
        } else {
            this.state = 'hit'; this.spriteAnim = 'hit';
        }
        this.animTime = 0; this.frameIndex = 0; this.canAct = false;
    }

    getHitbox() {
        const atkData = ATTACK_DATA[this.state];
        if (!atkData || this.hitRegistered) return null;
        if (this.frameIndex !== atkData.hitFrame) return null;
        const hb = atkData.hitbox;
        return {
            x: this.x + hb.x * this.facing - hb.w / 2,
            y: this.y + hb.y,
            w: hb.w, h: hb.h,
            damage: atkData.damage,
            knockback: atkData.knockback
        };
    }

    getBodyBox() {
        return { x: this.x - 25, y: this.y - 160, w: 50, h: 160 };
    }

    update(dt, moveDir, opponent) {
        this.animTime += dt;
        this.hitFlash = Math.max(0, this.hitFlash - dt);

        const anim = this.character.sprite.anims[this.spriteAnim];
        if (!anim) return;
        const frameDur = 1 / anim.fps;
        const totalDur = anim.frames * frameDur;

        // Update frame index
        if (this.state === 'ko') {
            // Stop at last frame
            this.frameIndex = Math.min(Math.floor(this.animTime / frameDur), anim.frames - 1);
        } else if (this.state === 'idle' || this.state === 'walk' || this.state === 'victory') {
            // Loop
            this.frameIndex = Math.floor(this.animTime / frameDur) % anim.frames;
        } else {
            // Play once then return to idle
            this.frameIndex = Math.floor(this.animTime / frameDur);
            if (this.frameIndex >= anim.frames) {
                this.state = 'idle'; this.spriteAnim = 'idle';
                this.animTime = 0; this.frameIndex = 0; this.canAct = true;
            } else {
                this.frameIndex = Math.min(this.frameIndex, anim.frames - 1);
            }
        }

        // Movement (only when idle or walking)
        if (this.canAct && this.state !== 'ko') {
            if (moveDir !== 0) {
                const speed = this.character.stats.speed * 60;
                this.vx = moveDir * speed;
                if (this.state !== 'punch' && this.state !== 'kick' && this.state !== 'uppercut') {
                    this.state = 'walk'; this.spriteAnim = 'walk';
                }
            } else if (this.state === 'walk') {
                this.state = 'idle'; this.spriteAnim = 'idle';
                this.animTime = 0;
            }
        }

        // Physics
        this.x += this.vx * dt;
        this.vx *= 0.85;

        // Face opponent
        if (opponent && this.state !== 'ko' && this.state !== 'hit') {
            if (this.state !== 'punch' && this.state !== 'kick' && this.state !== 'uppercut') {
                this.facing = opponent.x > this.x ? 1 : -1;
            }
        }

        // Stage bounds
        this.x = Math.max(40, Math.min(1240, this.x));

        // Push apart
        if (opponent) {
            const dist = Math.abs(this.x - opponent.x);
            if (dist < 50) {
                const push = (50 - dist) / 2;
                if (this.x < opponent.x) { this.x -= push; opponent.x += push; }
                else { this.x += push; opponent.x -= push; }
            }
        }
    }
}

// ================================================================
// COLLISION
// ================================================================
function boxOverlap(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

// ================================================================
// GAME STATE MACHINE
// ================================================================
class Game {
    constructor() {
        this.canvas = document.getElementById('gameCanvas');
        this.renderer = new Renderer(this.canvas);
        this.audio = new AudioManager();
        this.input = new InputHandler();
        this.assets = new AssetLoader();
        this.lastTime = 0;

        this.state = 'loading';
        this.stateTime = 0;
        this.loadProgress = 0;

        this.p1Cursor = 0; this.p2Cursor = 1;
        this.p1Selected = null; this.p2Selected = null;
        this.p1 = null; this.p2 = null;
        this.winner = null; this.winnerNum = 0;
        this.fightText = null;
        this.menuCooldown = { p1: 0, p2: 0 };

        this.loadAssets();
    }

    async loadAssets() {
        await this.assets.loadAll();
        this.state = 'title';
    }

    goToSelect() {
        this.state = 'select'; this.stateTime = 0;
        this.p1Cursor = 0; this.p2Cursor = Math.min(1, CHARACTERS.length-1);
        this.p1Selected = null; this.p2Selected = null;
    }

    goToFight() {
        this.state = 'fight'; this.stateTime = 0;
        const floorY = this.renderer.floorY;
        this.p1 = new Fighter(CHARACTERS[this.p1Selected], 1, this.assets.images);
        this.p2 = new Fighter(CHARACTERS[this.p2Selected], 2, this.assets.images);
        this.p1.reset(350, floorY, 1);
        this.p2.reset(930, floorY, -1);
        this.winner = null; this.winnerNum = 0;
        this.fightText = { text: 'FIGHT!', progress: 0, duration: 1.2 };
        this.audio.playFight();
    }

    goToKO(winner, winnerNum) {
        this.state = 'ko'; this.stateTime = 0;
        this.winner = winner; this.winnerNum = winnerNum;
        this.fightText = { text: 'K.O.', progress: 0, duration: 1.5 };
        this.audio.playKO();
        this.renderer.triggerShake(20);
    }

    goToVictory() {
        this.state = 'victory'; this.stateTime = 0;
        if (this.winner) {
            this.winner.state = 'victory'; this.winner.spriteAnim = 'victory';
            this.winner.animTime = 0; this.winner.canAct = false;
        }
    }

    // ---- UPDATE PER STATE ----
    updateTitle(dt) {
        if (this.input.consume('Enter') || this.input.consume('Space')) {
            this.audio.resume(); this.audio.playSelect(); this.goToSelect();
        }
    }

    updateSelect(dt) {
        const cd = 0.18;
        this.menuCooldown.p1 = Math.max(0, this.menuCooldown.p1 - dt);
        this.menuCooldown.p2 = Math.max(0, this.menuCooldown.p2 - dt);

        if (this.p1Selected === null) {
            if (this.menuCooldown.p1 <= 0) {
                if (this.input.isDown('KeyD') || this.input.isDown('KeyA')) {
                    const dir = this.input.isDown('KeyD') ? 1 : -1;
                    this.p1Cursor = (this.p1Cursor + dir + CHARACTERS.length) % CHARACTERS.length;
                    this.menuCooldown.p1 = cd;
                }
            }
            if (this.input.consume('KeyJ')) { this.p1Selected = this.p1Cursor; this.audio.playSelect(); }
        }

        if (this.p1Selected !== null && this.p2Selected === null) {
            if (this.menuCooldown.p2 <= 0) {
                if (this.input.isDown('ArrowRight') || this.input.isDown('ArrowLeft')) {
                    const dir = this.input.isDown('ArrowRight') ? 1 : -1;
                    this.p2Cursor = (this.p2Cursor + dir + CHARACTERS.length) % CHARACTERS.length;
                    this.menuCooldown.p2 = cd;
                }
            }
            if (this.input.consume('Numpad4') || this.input.consume('Numpad1') || this.input.consume('Period')) {
                this.p2Selected = this.p2Cursor; this.audio.playSelect();
            }
        }

        if (this.p1Selected !== null && this.p2Selected !== null) {
            if (this.input.consume('Enter') || this.input.consume('Space')) this.goToFight();
        }

        if (this.input.consume('Escape')) {
            if (this.p2Selected !== null) this.p2Selected = null;
            else if (this.p1Selected !== null) this.p1Selected = null;
            else { this.state = 'title'; this.stateTime = 0; }
        }
    }

    updateFight(dt) {
        if (this.fightText) {
            this.fightText.progress += dt / this.fightText.duration;
            if (this.fightText.progress >= 1) this.fightText = null;
            if (this.fightText && this.fightText.text === 'FIGHT!' && this.fightText.progress < 0.5) return;
        }

        // P1 input
        let p1Move = 0;
        if (this.input.isDown('KeyA')) p1Move = -1;
        if (this.input.isDown('KeyD')) p1Move = 1;
        if (this.input.consume('KeyJ')) { this.p1.startAttack('punch'); this.audio.playSwing(); }
        if (this.input.consume('KeyK')) { this.p1.startAttack('kick'); this.audio.playSwing(); }
        if (this.input.consume('KeyL')) { this.p1.startAttack('uppercut'); this.audio.playSwing(); }

        // P2 input
        let p2Move = 0;
        if (this.input.isDown('ArrowLeft')) p2Move = -1;
        if (this.input.isDown('ArrowRight')) p2Move = 1;
        if (this.input.consume('Numpad4') || this.input.consume('Numpad1') || this.input.consume('Period')) { this.p2.startAttack('punch'); this.audio.playSwing(); }
        if (this.input.consume('Numpad5') || this.input.consume('Numpad2') || this.input.consume('Comma')) { this.p2.startAttack('kick'); this.audio.playSwing(); }
        if (this.input.consume('Numpad6') || this.input.consume('Numpad3') || this.input.consume('Slash')) { this.p2.startAttack('uppercut'); this.audio.playSwing(); }

        this.p1.update(dt, p1Move, this.p2);
        this.p2.update(dt, p2Move, this.p1);

        // Hit detection P1 -> P2
        const p1Hit = this.p1.getHitbox();
        if (p1Hit && boxOverlap(p1Hit, this.p2.getBodyBox())) {
            this.p1.hitRegistered = true;
            this.p2.takeHit(p1Hit.damage, p1Hit.knockback, this.p1);
            this.audio.playHit(p1Hit.damage / 10);
            this.renderer.addHitParticles((this.p1.x+this.p2.x)/2, p1Hit.y+p1Hit.h/2, p1Hit.damage/8);
            this.renderer.triggerShake(p1Hit.damage * 0.6);
            this.renderer.addDustParticles(this.p2.x, this.renderer.floorY);
            if (this.p2.health <= 0) { this.goToKO(this.p1, 1); return; }
        }

        // Hit detection P2 -> P1
        const p2Hit = this.p2.getHitbox();
        if (p2Hit && boxOverlap(p2Hit, this.p1.getBodyBox())) {
            this.p2.hitRegistered = true;
            this.p1.takeHit(p2Hit.damage, p2Hit.knockback, this.p2);
            this.audio.playHit(p2Hit.damage / 10);
            this.renderer.addHitParticles((this.p1.x+this.p2.x)/2, p2Hit.y+p2Hit.h/2, p2Hit.damage/8);
            this.renderer.triggerShake(p2Hit.damage * 0.6);
            this.renderer.addDustParticles(this.p1.x, this.renderer.floorY);
            if (this.p1.health <= 0) { this.goToKO(this.p2, 2); return; }
        }
    }

    updateKO(dt) {
        this.p1.update(dt, 0, null);
        this.p2.update(dt, 0, null);
        if (this.fightText) {
            this.fightText.progress += dt / this.fightText.duration;
            if (this.fightText.progress >= 1) this.fightText = null;
        }
        if (this.stateTime > 2.0) this.goToVictory();
    }

    updateVictory(dt) {
        if (this.winner) {
            this.winner.animTime += dt;
            const anim = this.winner.character.sprite.anims['victory'];
            if (anim) this.winner.frameIndex = Math.floor(this.winner.animTime / (1/anim.fps)) % anim.frames;
        }
        if (this.input.consume('Enter') || this.input.consume('Space')) this.goToSelect();
    }

    // ---- MAIN LOOP ----
    update(dt) {
        this.stateTime += dt;
        if (this.state === 'loading') { this.loadProgress = this.assets.progress; return; }
        switch (this.state) {
            case 'title': this.updateTitle(dt); break;
            case 'select': this.updateSelect(dt); break;
            case 'fight': this.updateFight(dt); break;
            case 'ko': this.updateKO(dt); break;
            case 'victory': this.updateVictory(dt); break;
        }
    }

    getGameState() {
        return {
            state: this.state, loadProgress: this.loadProgress,
            p1: this.p1, p2: this.p2,
            p1Cursor: this.p1Cursor, p2Cursor: this.p2Cursor,
            p1Selected: this.p1Selected, p2Selected: this.p2Selected,
            winner: this.winner, winnerNum: this.winnerNum,
            fightText: this.fightText,
            assets: this.assets.images
        };
    }

    gameLoop(timestamp) {
        const dt = Math.min((timestamp - this.lastTime) / 1000, 0.05);
        this.lastTime = timestamp;
        this.update(dt);
        this.renderer.render(this.getGameState(), dt);
        requestAnimationFrame(t => this.gameLoop(t));
    }

    start() {
        this.lastTime = performance.now();
        requestAnimationFrame(t => this.gameLoop(t));
    }
}

// ================================================================
// INIT
// ================================================================
window.addEventListener('load', () => {
    window._game = new Game();
    window._game.start();
});
