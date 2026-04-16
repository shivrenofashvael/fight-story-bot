// ============================================================
// IRON FIST - Renderer (Sprites, Background, UI, Effects)
// ============================================================

class Renderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.W = canvas.width;
        this.H = canvas.height;
        this.floorY = this.H * 0.82;
        this.particles = [];
        this.shake = { x: 0, y: 0, intensity: 0 };
        this.time = 0;
        this.dustMotes = [];
        for (let i = 0; i < 30; i++) {
            this.dustMotes.push({
                x: Math.random() * this.W, y: Math.random() * this.H * 0.8,
                size: 0.5 + Math.random() * 1.5, speed: 5 + Math.random() * 15,
                alpha: 0.05 + Math.random() * 0.1, drift: Math.random() * Math.PI * 2
            });
        }
    }

    // ================================================================
    // SPRITE DRAWING
    // ================================================================
    drawSprite(ctx, img, frameIdx, fw, fh, x, y, scale, facing, anchorX, anchorY, hueShift) {
        if (!img) return;
        ctx.save();
        ctx.translate(x, y);
        if (facing === -1) ctx.scale(-1, 1);

        const dw = fw * scale;
        const dh = fh * scale;
        const dx = -dw * anchorX;
        const dy = -dh * anchorY;

        if (hueShift) ctx.filter = `hue-rotate(${hueShift}deg) saturate(1.3)`;
        ctx.drawImage(img, frameIdx * fw, 0, fw, fh, dx, dy, dw, dh);
        ctx.filter = 'none';
        ctx.restore();
    }

    drawFighter(ctx, fighter) {
        if (!fighter || !fighter.character) return;
        const char = fighter.character;
        const sp = char.sprite;
        const animName = fighter.spriteAnim || 'idle';
        const img = fighter.assets[`${char.id}_${animName}`];
        if (!img) return;

        const anim = sp.anims[animName];
        const frameIdx = Math.min(fighter.frameIndex || 0, anim.frames - 1);

        if (fighter.hitFlash > 0) {
            ctx.save();
            ctx.globalAlpha = 0.5 + Math.sin(this.time * 40) * 0.3;
        }

        this.drawSprite(ctx, img, frameIdx, sp.frameW, sp.frameH,
            fighter.x, fighter.y, sp.scale, fighter.facing,
            sp.anchorX, sp.anchorY, sp.hueShift);

        if (fighter.hitFlash > 0) ctx.restore();
    }

    drawGroundShadow(ctx, fighter) {
        ctx.save();
        ctx.globalAlpha = 0.25;
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.ellipse(fighter.x, this.floorY + 2, 40, 8, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    // ================================================================
    // BACKGROUND - Professional Arena
    // ================================================================
    drawBackground(ctx) {
        const W = this.W, H = this.H, t = this.time;

        // Dark gradient sky
        const sky = ctx.createLinearGradient(0, 0, 0, H);
        sky.addColorStop(0, '#020108');
        sky.addColorStop(0.2, '#0A0518');
        sky.addColorStop(0.5, '#140A22');
        sky.addColorStop(1, '#0A0614');
        ctx.fillStyle = sky;
        ctx.fillRect(0, 0, W, H);

        // Ambient light from above (arena spotlights)
        const spot1 = ctx.createRadialGradient(W*0.3, 0, 10, W*0.3, H*0.3, 400);
        spot1.addColorStop(0, 'rgba(100,60,180,0.06)');
        spot1.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = spot1;
        ctx.fillRect(0, 0, W, H);
        const spot2 = ctx.createRadialGradient(W*0.7, 0, 10, W*0.7, H*0.3, 400);
        spot2.addColorStop(0, 'rgba(180,60,60,0.06)');
        spot2.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = spot2;
        ctx.fillRect(0, 0, W, H);

        // Back wall with stone texture
        const wallTop = H * 0.12;
        const wg = ctx.createLinearGradient(0, wallTop, 0, this.floorY);
        wg.addColorStop(0, '#161020');
        wg.addColorStop(0.5, '#0E0A16');
        wg.addColorStop(1, '#0A0810');
        ctx.fillStyle = wg;
        ctx.fillRect(0, wallTop, W, this.floorY - wallTop);

        // Stone blocks
        ctx.strokeStyle = 'rgba(255,255,255,0.02)';
        ctx.lineWidth = 1;
        for (let y = wallTop; y < this.floorY; y += 40) {
            const offset = (Math.floor(y / 40) % 2) * 55;
            for (let x = offset - 55; x < W; x += 110) {
                ctx.strokeRect(x, y, 110, 40);
            }
        }

        // Pillars
        for (const px of [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]) {
            this.drawPillar(ctx, W * px, wallTop - 15, this.floorY + 5, 28);
        }

        // Chains between pillars
        ctx.strokeStyle = 'rgba(80,60,100,0.15)';
        ctx.lineWidth = 2;
        for (let i = 0; i < 5; i++) {
            const x1 = W * (0.2 * i), x2 = W * (0.2 * (i+1));
            const mid = (x1 + x2) / 2;
            ctx.beginPath();
            ctx.moveTo(x1, wallTop + 20);
            ctx.quadraticCurveTo(mid, wallTop + 60, x2, wallTop + 20);
            ctx.stroke();
        }

        // Torches with glow
        this.drawTorch(ctx, W * 0.1, wallTop + 60);
        this.drawTorch(ctx, W * 0.3, wallTop + 70);
        this.drawTorch(ctx, W * 0.7, wallTop + 70);
        this.drawTorch(ctx, W * 0.9, wallTop + 60);

        // Floor with perspective
        const fg = ctx.createLinearGradient(0, this.floorY, 0, H);
        fg.addColorStop(0, '#1E1828');
        fg.addColorStop(0.1, '#18122A');
        fg.addColorStop(1, '#060410');
        ctx.fillStyle = fg;
        ctx.fillRect(0, this.floorY, W, H - this.floorY);

        // Floor highlight line
        const floorLine = ctx.createLinearGradient(W*0.1, 0, W*0.9, 0);
        floorLine.addColorStop(0, 'rgba(60,40,100,0)');
        floorLine.addColorStop(0.3, 'rgba(100,70,160,0.4)');
        floorLine.addColorStop(0.5, 'rgba(140,100,200,0.5)');
        floorLine.addColorStop(0.7, 'rgba(100,70,160,0.4)');
        floorLine.addColorStop(1, 'rgba(60,40,100,0)');
        ctx.strokeStyle = floorLine;
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(0, this.floorY); ctx.lineTo(W, this.floorY); ctx.stroke();

        // Floor tiles
        ctx.strokeStyle = 'rgba(255,255,255,0.015)';
        ctx.lineWidth = 1;
        for (let x = 0; x < W; x += 80) {
            ctx.beginPath(); ctx.moveTo(x, this.floorY); ctx.lineTo(x, H); ctx.stroke();
        }

        // Center arena mark
        ctx.save();
        ctx.globalAlpha = 0.08 + Math.sin(t * 0.5) * 0.03;
        ctx.beginPath();
        ctx.ellipse(W/2, this.floorY + (H - this.floorY)/2, 180, 30, 0, 0, Math.PI * 2);
        ctx.strokeStyle = '#8060C0';
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.restore();

        // Dust motes
        for (const m of this.dustMotes) {
            ctx.beginPath(); ctx.arc(m.x, m.y, m.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(180,160,200,${m.alpha})`; ctx.fill();
        }
    }

    drawPillar(ctx, x, top, bot, w) {
        const g = ctx.createLinearGradient(x-w/2, 0, x+w/2, 0);
        g.addColorStop(0, '#0C0810');
        g.addColorStop(0.2, '#1A1424');
        g.addColorStop(0.4, '#22182E');
        g.addColorStop(0.5, '#2A2034');
        g.addColorStop(0.6, '#22182E');
        g.addColorStop(0.8, '#1A1424');
        g.addColorStop(1, '#0C0810');
        ctx.fillStyle = g;
        ctx.fillRect(x - w/2, top, w, bot - top);
        // Capitals
        ctx.fillStyle = '#2A2234';
        ctx.fillRect(x - w/2 - 5, top, w + 10, 10);
        ctx.fillRect(x - w/2 - 5, bot - 8, w + 10, 8);
        // Edge highlights
        ctx.strokeStyle = 'rgba(255,255,255,0.03)';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x - w/2, top); ctx.lineTo(x - w/2, bot); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x + w/2, top); ctx.lineTo(x + w/2, bot); ctx.stroke();
    }

    drawTorch(ctx, x, y) {
        const t = this.time;
        const flick = Math.sin(t*8 + x)*3 + Math.sin(t*13 + x*0.5)*2;
        const fh = 16 + flick;

        // Bracket
        ctx.fillStyle = '#3A2A1A';
        ctx.fillRect(x - 2, y, 4, 22);
        ctx.fillRect(x - 6, y - 2, 12, 5);

        // Glow
        const glow = ctx.createRadialGradient(x, y - 10, 2, x, y - 10, 80);
        glow.addColorStop(0, 'rgba(255,140,30,0.12)');
        glow.addColorStop(0.5, 'rgba(255,80,10,0.04)');
        glow.addColorStop(1, 'rgba(255,40,0,0)');
        ctx.fillStyle = glow;
        ctx.fillRect(x - 90, y - 100, 180, 180);

        // Flame
        ctx.beginPath();
        ctx.moveTo(x - 4, y);
        ctx.quadraticCurveTo(x - 6 + flick * 0.5, y - fh * 0.5, x + flick * 0.3, y - fh);
        ctx.quadraticCurveTo(x + 6 - flick * 0.5, y - fh * 0.5, x + 4, y);
        ctx.closePath();
        const fg = ctx.createLinearGradient(x, y, x, y - fh);
        fg.addColorStop(0, '#FF4400'); fg.addColorStop(0.4, '#FF8800');
        fg.addColorStop(0.7, '#FFCC00'); fg.addColorStop(1, '#FFFF80');
        ctx.fillStyle = fg; ctx.fill();
    }

    // ================================================================
    // PARTICLES
    // ================================================================
    addHitParticles(x, y, intensity) {
        const count = Math.floor(intensity * 12);
        for (let i = 0; i < count; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 100 + Math.random() * 300;
            this.particles.push({
                x, y, vx: Math.cos(angle)*speed, vy: Math.sin(angle)*speed,
                life: 0.2 + Math.random() * 0.3, maxLife: 0.2 + Math.random() * 0.3,
                size: 2 + Math.random() * 5,
                color: `hsl(${30 + Math.random() * 30},100%,${60 + Math.random() * 40}%)`,
                gravity: 400, type: 'spark'
            });
        }
    }

    addDustParticles(x, y) {
        for (let i = 0; i < 8; i++) {
            const angle = -Math.PI * 0.2 + Math.random() * -Math.PI * 0.6;
            const speed = 15 + Math.random() * 50;
            this.particles.push({
                x: x + (Math.random() - 0.5) * 30, y: y - 2,
                vx: Math.cos(angle) * speed * (Math.random() > 0.5 ? 1 : -1),
                vy: Math.sin(angle) * speed,
                life: 0.3 + Math.random() * 0.4, maxLife: 0.3 + Math.random() * 0.4,
                size: 3 + Math.random() * 4, color: 'rgba(120,100,150,0.4)',
                gravity: -20, type: 'dust'
            });
        }
    }

    updateParticles(dt) {
        for (let i = this.particles.length - 1; i >= 0; i--) {
            const p = this.particles[i];
            p.x += p.vx * dt; p.y += p.vy * dt;
            p.vy += (p.gravity || 0) * dt; p.vx *= 0.97; p.life -= dt;
            if (p.life <= 0) this.particles.splice(i, 1);
        }
    }

    drawParticles(ctx) {
        for (const p of this.particles) {
            const a = Math.max(0, p.life / p.maxLife);
            ctx.globalAlpha = a;
            ctx.fillStyle = p.color;
            ctx.beginPath(); ctx.arc(p.x, p.y, p.size * (p.type === 'spark' ? a : 1), 0, Math.PI * 2); ctx.fill();
            if (p.type === 'spark') {
                ctx.beginPath(); ctx.arc(p.x, p.y, p.size * a * 3, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(255,200,100,0.1)`; ctx.fill();
            }
        }
        ctx.globalAlpha = 1;
    }

    // ================================================================
    // SCREEN SHAKE
    // ================================================================
    triggerShake(intensity) { this.shake.intensity = Math.max(this.shake.intensity, intensity); }

    updateShake(dt) {
        if (this.shake.intensity > 0.1) {
            this.shake.x = (Math.random() - 0.5) * this.shake.intensity;
            this.shake.y = (Math.random() - 0.5) * this.shake.intensity;
            this.shake.intensity *= 0.88;
        } else { this.shake.x = 0; this.shake.y = 0; this.shake.intensity = 0; }
    }

    updateDustMotes(dt) {
        for (const m of this.dustMotes) {
            m.drift += dt * 0.5; m.x += Math.sin(m.drift) * m.speed * dt; m.y -= m.speed * dt * 0.3;
            if (m.y < -10) { m.y = this.H * 0.8; m.x = Math.random() * this.W; }
            if (m.x < -10) m.x = this.W + 10; if (m.x > this.W + 10) m.x = -10;
        }
    }

    // ================================================================
    // UI: HEALTH BARS (Premium Style)
    // ================================================================
    drawHealthBars(ctx, p1, p2) {
        const barW = 440, barH = 24, barY = 38;
        const p1x = 60, p2x = this.W - 60 - barW;

        for (const [px, fighter, align] of [[p1x, p1, 'left'], [p2x, p2, 'right']]) {
            const hp = fighter.health / fighter.maxHealth;
            const char = fighter.character;

            // Outer frame
            ctx.fillStyle = '#000';
            ctx.fillRect(px - 3, barY - 3, barW + 6, barH + 6);
            ctx.fillStyle = '#181020';
            ctx.fillRect(px, barY, barW, barH);

            // Health fill
            const fillW = barW * Math.max(0, hp);
            const hg = ctx.createLinearGradient(px, barY, px + barW, barY);
            if (hp > 0.5) {
                hg.addColorStop(0, '#00AA40'); hg.addColorStop(1, '#40FF70');
            } else if (hp > 0.25) {
                hg.addColorStop(0, '#BB7700'); hg.addColorStop(1, '#FFAA00');
            } else {
                hg.addColorStop(0, '#BB2200'); hg.addColorStop(1, '#FF4400');
            }
            ctx.fillStyle = hg;
            if (align === 'left') ctx.fillRect(px, barY, fillW, barH);
            else ctx.fillRect(px + barW - fillW, barY, fillW, barH);

            // Shine
            const sh = ctx.createLinearGradient(px, barY, px, barY + barH);
            sh.addColorStop(0, 'rgba(255,255,255,0.2)');
            sh.addColorStop(0.4, 'rgba(255,255,255,0)');
            sh.addColorStop(1, 'rgba(0,0,0,0.15)');
            ctx.fillStyle = sh;
            ctx.fillRect(px, barY, barW, barH);

            // Border
            ctx.strokeStyle = '#444';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(px - 1, barY - 1, barW + 2, barH + 2);

            // Player name
            ctx.font = 'bold 16px "Segoe UI", Arial';
            ctx.fillStyle = '#EEE';
            ctx.textAlign = align;
            const nameX = align === 'left' ? px + 4 : px + barW - 4;
            ctx.fillText(char.name, nameX, barY - 8);

            // Player tag
            ctx.font = 'bold 11px "Segoe UI", Arial';
            ctx.fillStyle = align === 'left' ? '#6090FF' : '#FF5050';
            const tagX = align === 'left' ? px + 4 : px + barW - 4;
            ctx.fillText(align === 'left' ? 'P1' : 'P2', tagX, barY - 22);
        }
        ctx.textAlign = 'left';
    }

    // ================================================================
    // UI: TITLE SCREEN
    // ================================================================
    drawTitleScreen(ctx, time) {
        const W = this.W, H = this.H;

        // Dark bg with subtle gradient
        const bg = ctx.createRadialGradient(W/2, H*0.4, 50, W/2, H*0.4, W*0.8);
        bg.addColorStop(0, '#140A20');
        bg.addColorStop(1, '#04020A');
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, W, H);

        // Decorative lines
        ctx.strokeStyle = 'rgba(200,150,50,0.08)';
        ctx.lineWidth = 1;
        for (let i = 0; i < 30; i++) {
            const y = H * 0.25 + i * 5;
            ctx.beginPath(); ctx.moveTo(W * 0.2, y); ctx.lineTo(W * 0.8, y); ctx.stroke();
        }

        // Title shadow
        ctx.save();
        ctx.font = 'bold 120px "Segoe UI", Arial';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillStyle = 'rgba(0,0,0,0.8)';
        ctx.fillText('IRON FIST', W / 2 + 4, H * 0.35 + 4);

        // Title with gold gradient
        const tg = ctx.createLinearGradient(W / 2 - 280, H * 0.25, W / 2 + 280, H * 0.45);
        tg.addColorStop(0, '#8B6914');
        tg.addColorStop(0.2, '#D4AF37');
        tg.addColorStop(0.4, '#FFD700');
        tg.addColorStop(0.5, '#FFFACD');
        tg.addColorStop(0.6, '#FFD700');
        tg.addColorStop(0.8, '#D4AF37');
        tg.addColorStop(1, '#8B6914');
        ctx.fillStyle = tg;
        ctx.fillText('IRON FIST', W / 2, H * 0.35);
        ctx.strokeStyle = '#6B4C12';
        ctx.lineWidth = 2;
        ctx.strokeText('IRON FIST', W / 2, H * 0.35);
        ctx.restore();

        // Subtitle
        ctx.font = 'bold 20px "Segoe UI", Arial';
        ctx.fillStyle = '#666';
        ctx.textAlign = 'center';
        ctx.fillText('BATTLE  OF  LEGENDS', W / 2, H * 0.48);

        // Divider
        ctx.strokeStyle = '#D4AF3730';
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(W * 0.3, H * 0.54); ctx.lineTo(W * 0.7, H * 0.54); ctx.stroke();

        // Pulsing start text
        if (Math.sin(time * 3) > -0.3) {
            ctx.font = 'bold 24px "Segoe UI", Arial';
            ctx.fillStyle = '#D4AF37';
            ctx.fillText('PRESS  ENTER  TO  START', W / 2, H * 0.66);
        }

        // Controls
        ctx.font = '13px "Segoe UI", Arial';
        ctx.fillStyle = '#444';
        ctx.fillText('P1: A/D + J/K/L   |   P2: Arrows + . , /', W / 2, H * 0.86);
        ctx.textAlign = 'left';
    }

    // ================================================================
    // UI: CHARACTER SELECT
    // ================================================================
    drawSelectScreen(ctx, state, assets) {
        const W = this.W, H = this.H;

        // Background
        const bg = ctx.createRadialGradient(W/2, H/2, 50, W/2, H/2, W*0.8);
        bg.addColorStop(0, '#100A1A');
        bg.addColorStop(1, '#04020A');
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, W, H);

        // Title
        ctx.font = 'bold 36px "Segoe UI", Arial';
        ctx.textAlign = 'center';
        const tg = ctx.createLinearGradient(W / 2 - 200, 0, W / 2 + 200, 0);
        tg.addColorStop(0, '#666'); tg.addColorStop(0.5, '#DDD'); tg.addColorStop(1, '#666');
        ctx.fillStyle = tg;
        ctx.fillText('SELECT  YOUR  FIGHTER', W / 2, 48);

        // Grid layout: 3x2
        const gridW = 960, gridH = 500;
        const gx = (W - gridW) / 2, gy = 70;
        const cellW = gridW / 3, cellH = gridH / 2;

        for (let i = 0; i < CHARACTERS.length; i++) {
            const col = i % 3, row = Math.floor(i / 3);
            const cx = gx + col * cellW + cellW / 2;
            const cy = gy + row * cellH + cellH / 2;
            const charDef = CHARACTERS[i];
            const isP1Cur = state.p1Cursor === i && state.p1Selected === null;
            const isP2Cur = state.p2Cursor === i && state.p1Selected !== null && state.p2Selected === null;
            const isP1Sel = state.p1Selected === i;
            const isP2Sel = state.p2Selected === i;

            // Cell background
            const cellBg = ctx.createLinearGradient(cx, cy - cellH/2, cx, cy + cellH/2);
            cellBg.addColorStop(0, '#0E0A16');
            cellBg.addColorStop(1, '#08060E');
            ctx.fillStyle = cellBg;
            ctx.fillRect(cx - cellW / 2 + 6, cy - cellH / 2 + 6, cellW - 12, cellH - 12);

            // Highlight borders
            if (isP1Cur || isP1Sel) {
                ctx.strokeStyle = isP1Sel ? '#4488FF' : '#4488FF88';
                ctx.lineWidth = isP1Sel ? 3 : 2;
                ctx.strokeRect(cx - cellW / 2 + 5, cy - cellH / 2 + 5, cellW - 10, cellH - 10);
                if (isP1Sel) {
                    ctx.fillStyle = 'rgba(68,136,255,0.05)';
                    ctx.fillRect(cx - cellW / 2 + 6, cy - cellH / 2 + 6, cellW - 12, cellH - 12);
                }
            }
            if (isP2Cur || isP2Sel) {
                ctx.strokeStyle = isP2Sel ? '#FF4444' : '#FF444488';
                ctx.lineWidth = isP2Sel ? 3 : 2;
                ctx.strokeRect(cx - cellW / 2 + 3, cy - cellH / 2 + 3, cellW - 6, cellH - 6);
                if (isP2Sel) {
                    ctx.fillStyle = 'rgba(255,68,68,0.05)';
                    ctx.fillRect(cx - cellW / 2 + 6, cy - cellH / 2 + 6, cellW - 12, cellH - 12);
                }
            }

            // Draw character portrait
            ctx.save();
            ctx.beginPath();
            ctx.rect(cx - cellW / 2 + 8, cy - cellH / 2 + 8, cellW - 16, cellH - 16);
            ctx.clip();
            const idleImg = assets[`${charDef.id}_idle`];
            if (idleImg) {
                const sp = charDef.sprite;
                const targetH = cellH * 0.75;
                const portraitScale = targetH / sp.frameH;
                this.drawSprite(ctx, idleImg, 0, sp.frameW, sp.frameH,
                    cx, cy + cellH * 0.28, portraitScale, 1, 0.5, 1.0, sp.hueShift);
            }
            ctx.restore();

            // Bottom gradient for text readability
            const tGrad = ctx.createLinearGradient(cx, cy + cellH * 0.05, cx, cy + cellH * 0.46);
            tGrad.addColorStop(0, 'rgba(8,6,14,0)');
            tGrad.addColorStop(1, 'rgba(8,6,14,0.95)');
            ctx.fillStyle = tGrad;
            ctx.fillRect(cx - cellW / 2 + 8, cy + cellH * 0.05, cellW - 16, cellH * 0.45);

            // Name
            ctx.font = 'bold 18px "Segoe UI", Arial';
            ctx.fillStyle = '#EEE';
            ctx.textAlign = 'center';
            ctx.fillText(charDef.name, cx, cy + cellH * 0.33);
            ctx.font = '12px "Segoe UI", Arial';
            ctx.fillStyle = '#888';
            ctx.fillText(charDef.title, cx, cy + cellH * 0.43);

            // P1/P2 badges
            if (isP1Sel) {
                ctx.fillStyle = '#4488FF';
                ctx.fillRect(cx - cellW/2 + 12, cy - cellH/2 + 12, 28, 18);
                ctx.font = 'bold 12px "Segoe UI"'; ctx.fillStyle = '#FFF';
                ctx.fillText('P1', cx - cellW/2 + 26, cy - cellH/2 + 25);
            }
            if (isP2Sel) {
                ctx.fillStyle = '#FF4444';
                ctx.fillRect(cx + cellW/2 - 40, cy - cellH/2 + 12, 28, 18);
                ctx.font = 'bold 12px "Segoe UI"'; ctx.fillStyle = '#FFF';
                ctx.fillText('P2', cx + cellW/2 - 26, cy - cellH/2 + 25);
            }
        }

        // Instructions
        ctx.font = '14px "Segoe UI", Arial';
        ctx.fillStyle = '#555';
        ctx.textAlign = 'center';
        if (state.p1Selected === null) ctx.fillText('P1: A/D to browse, J to select', W / 2, H - 30);
        else if (state.p2Selected === null) ctx.fillText('P2: Arrows to browse, . to select', W / 2, H - 30);
        else if (Math.sin(this.time * 4) > -0.3) ctx.fillText('Press ENTER to fight!', W / 2, H - 30);
        ctx.textAlign = 'left';
    }

    // ================================================================
    // UI: FIGHT TEXT / VICTORY
    // ================================================================
    drawFightText(ctx, text, progress) {
        const W = this.W, H = this.H;
        const scale = progress < 0.3 ? progress / 0.3 : (progress < 0.7 ? 1 : 1 - (progress - 0.7) / 0.3);
        const alpha = Math.min(1, scale * 1.5);
        const size = 80 + scale * 40;
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.font = `bold ${size}px "Segoe UI", Arial`;
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillStyle = '#000';
        ctx.fillText(text, W / 2 + 3, H / 2 + 3);
        const tg = ctx.createLinearGradient(W / 2 - 200, H / 2 - 50, W / 2 + 200, H / 2 + 50);
        tg.addColorStop(0, '#FF4400'); tg.addColorStop(0.5, '#FFD700'); tg.addColorStop(1, '#FF4400');
        ctx.fillStyle = tg;
        ctx.fillText(text, W / 2, H / 2);
        ctx.strokeStyle = '#AA3300';
        ctx.lineWidth = 2;
        ctx.strokeText(text, W / 2, H / 2);
        ctx.restore();
    }

    drawVictoryScreen(ctx, winner, winnerNum, time) {
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.fillRect(0, 0, this.W, this.H);
        ctx.save();
        ctx.font = 'bold 60px "Segoe UI", Arial';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillStyle = 'rgba(0,0,0,0.8)';
        ctx.fillText(`${winner.character.name}  WINS!`, this.W / 2 + 3, this.H * 0.3 + 3);
        const vg = ctx.createLinearGradient(this.W / 2 - 260, this.H * 0.2, this.W / 2 + 260, this.H * 0.4);
        vg.addColorStop(0, '#8B6914'); vg.addColorStop(0.3, '#D4AF37');
        vg.addColorStop(0.5, '#FFD700'); vg.addColorStop(0.7, '#D4AF37'); vg.addColorStop(1, '#8B6914');
        ctx.fillStyle = vg;
        ctx.fillText(`${winner.character.name}  WINS!`, this.W / 2, this.H * 0.3);
        ctx.strokeStyle = '#6B4C12'; ctx.lineWidth = 2;
        ctx.strokeText(`${winner.character.name}  WINS!`, this.W / 2, this.H * 0.3);
        ctx.font = 'bold 26px "Segoe UI", Arial';
        ctx.fillStyle = winnerNum === 1 ? '#6090FF' : '#FF5050';
        ctx.fillText(`PLAYER ${winnerNum}`, this.W / 2, this.H * 0.22);
        if (Math.sin(time * 3) > -0.3) {
            ctx.font = 'bold 20px "Segoe UI", Arial';
            ctx.fillStyle = '#999';
            ctx.fillText('Press ENTER to rematch', this.W / 2, this.H * 0.85);
        }
        ctx.restore();
    }

    drawLoadingScreen(ctx, progress) {
        ctx.fillStyle = '#04020A';
        ctx.fillRect(0, 0, this.W, this.H);
        ctx.font = 'bold 28px "Segoe UI", Arial';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#666';
        ctx.fillText('LOADING', this.W / 2, this.H / 2 - 30);
        const bw = 280, bh = 8;
        ctx.fillStyle = '#1A1020';
        ctx.fillRect(this.W / 2 - bw / 2, this.H / 2, bw, bh);
        ctx.fillStyle = '#D4AF37';
        ctx.fillRect(this.W / 2 - bw / 2, this.H / 2, bw * progress, bh);
        ctx.textAlign = 'left';
    }

    drawVignette(ctx) {
        const vig = ctx.createRadialGradient(this.W / 2, this.H / 2, this.W * 0.3, this.W / 2, this.H / 2, this.W * 0.7);
        vig.addColorStop(0, 'rgba(0,0,0,0)');
        vig.addColorStop(1, 'rgba(0,0,0,0.5)');
        ctx.fillStyle = vig;
        ctx.fillRect(0, 0, this.W, this.H);
    }

    // ================================================================
    // MAIN RENDER
    // ================================================================
    render(gameState, dt) {
        const ctx = this.ctx;
        this.time += dt;
        this.updateParticles(dt);
        this.updateShake(dt);
        this.updateDustMotes(dt);

        ctx.save();
        ctx.translate(this.shake.x, this.shake.y);

        if (gameState.state === 'loading') {
            this.drawLoadingScreen(ctx, gameState.loadProgress || 0);
        } else if (gameState.state === 'title') {
            this.drawTitleScreen(ctx, this.time);
        } else if (gameState.state === 'select') {
            this.drawSelectScreen(ctx, gameState, gameState.assets || {});
        } else if (gameState.state === 'fight' || gameState.state === 'ko' || gameState.state === 'victory') {
            this.drawBackground(ctx);
            this.drawGroundShadow(ctx, gameState.p1);
            this.drawGroundShadow(ctx, gameState.p2);
            this.drawFighter(ctx, gameState.p1);
            this.drawFighter(ctx, gameState.p2);
            this.drawParticles(ctx);
            this.drawVignette(ctx);
            this.drawHealthBars(ctx, gameState.p1, gameState.p2);
            if (gameState.fightText) this.drawFightText(ctx, gameState.fightText.text, gameState.fightText.progress);
            if (gameState.state === 'victory') this.drawVictoryScreen(ctx, gameState.winner, gameState.winnerNum, this.time);
        }

        ctx.restore();
    }
}
