"""
Squad Office v2 — Pixel Agents-inspired Canvas renderer.

State machine: idle → walk → sit → type/read/think → done/error
Game loop: requestAnimationFrame @ 60fps
Sprites: 16×24 procedural pixel art, 4-direction walk (down-facing for seated)
Tile floor: 16×16 tiles with desk furniture
Speech bubbles: float above character head
Inspired by: github.com/pablodelucca/pixel-agents
"""
from __future__ import annotations
import json

AGENT_DEFS = [
    {"key": "manager_agent",       "ic": "🎯", "nm_en": "Manager",       "nm_pt": "Gerente",        "variant": 0},
    {"key": "security_agent",      "ic": "🔐", "nm_en": "Security",      "nm_pt": "Segurança",      "variant": 1},
    {"key": "reliability_agent",   "ic": "🛡️", "nm_en": "Reliability",   "nm_pt": "Confiabilidade", "variant": 2},
    {"key": "cost_agent",          "ic": "💰", "nm_en": "Cost",           "nm_pt": "Custo",          "variant": 3},
    {"key": "observability_agent", "ic": "📡", "nm_en": "Observability",  "nm_pt": "Observabilidade","variant": 4},
    {"key": "synthesizer_agent",   "ic": "🧠", "nm_en": "Synthesizer",   "nm_pt": "Sintetizador",   "variant": 5},
]


def build_squad_office_html(agent_states: dict, lang: str = "en", plan: dict | None = None) -> str:
    states_json = json.dumps(agent_states)
    plan_json   = json.dumps(plan or {})
    agents_json = json.dumps(AGENT_DEFS)
    lang_js     = json.dumps(lang)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#2a2438;font-family:-apple-system,'Segoe UI',sans-serif;overflow:hidden}}
#wrap{{width:100%;display:flex;flex-direction:column;gap:0}}

/* Manager card */
#mgr{{background:#1e1a2e;border:1px solid #3d3560;border-radius:8px;
  padding:10px 14px;display:flex;align-items:flex-start;gap:10px;font-size:12px;
  margin:8px 8px 0;transition:all .3s}}
#mgr.done{{border-color:#22c55e;background:#0f2a1a}}
#mgr.running{{border-color:#818cf8;background:#1e1b38;
  box-shadow:0 0 12px rgba(129,140,248,.25);animation:glowpulse 2s ease-in-out infinite}}
.mic{{font-size:1.1rem;flex-shrink:0}}
.minfo{{flex:1;min-width:0}}
.mttl{{font-weight:700;color:#e2e8f0;font-size:12px}}
.msub{{font-size:10px;color:#64748b;margin-top:1px}}
.mst{{font-size:10px;font-weight:700;color:#475569;flex-shrink:0}}
#mgr.done .mst{{color:#22c55e}} #mgr.running .mst{{color:#818cf8}}
#tags{{display:flex;gap:4px;flex-wrap:wrap;margin-top:5px}}
.tag{{padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600}}
.ta{{background:#312e6b;color:#a5b4fc}} .tc{{background:#3b1515;color:#fca5a5}}
.tl{{background:#0c2a3b;color:#7dd3fc}} .tx{{background:#0a2e1a;color:#86efac}}
#brief{{font-size:10px;color:#94a3b8;margin-top:5px;font-style:italic;display:none}}

/* Canvas */
#cv{{display:block;width:100%;image-rendering:pixelated;image-rendering:crisp-edges;
  cursor:default}}

@keyframes glowpulse{{
  0%,100%{{box-shadow:0 0 8px rgba(129,140,248,.2)}}
  50%{{box-shadow:0 0 20px rgba(129,140,248,.4)}}
}}
</style></head><body>
<div id="wrap">
  <div id="mgr">
    <div class="mic">🎯</div>
    <div class="minfo">
      <div class="mttl">Agent Manager <span style="font-size:9px;font-weight:400;color:#475569">— Phase 0</span></div>
      <div class="msub" id="sub">Analyzes architecture · Sets priorities · Injects focus</div>
      <div id="tags"></div>
      <div id="brief"></div>
    </div>
    <div class="mst" id="mst">waiting</div>
  </div>
  <canvas id="cv"></canvas>
</div>
<script>
// ═══════════════════════════════════════════════════════════════════════════════
//  DATA
// ═══════════════════════════════════════════════════════════════════════════════
const STATES = {states_json};
const PLAN   = {plan_json};
const AGENTS = {agents_json};
const LANG   = {lang_js};

// ═══════════════════════════════════════════════════════════════════════════════
//  PALETTE — dark office theme
// ═══════════════════════════════════════════════════════════════════════════════
const P = {{
  // Floor tiles
  floorA: 0x2d2640, floorB: 0x322b45, floorLine: 0x1e1a2e,
  // Walls
  wall: 0x1a1628, wallTop: 0x251f38, wallLight: 0x2d2640,
  // Desk
  desk: 0x3d3560, deskTop: 0x4a4070, deskEdge: 0x2a2438,
  deskWood: 0x5a4a30, deskWoodL: 0x6a5a3a, deskWoodD: 0x4a3a22,
  // Monitor
  monFrame: 0x1a1628, monScreen: 0x0a0a14, monOn: 0x00d4ff,
  monStand: 0x2a2438,
  // Chair
  chairBack: 0x1e1a2e, chairSeat: 0x252040, chairArm: 0x2a2438,
  // Skin tones
  sL: 0xffcba4, sLS: 0xe8a882,
  sM: 0xc68642, sMS: 0xa86a2a,
  sD: 0x8d5524, sDS: 0x6b3a14,
  // Hair
  hBk: 0x1a1008, hBr: 0x4a2a0a, hBl: 0xc89010, hRd: 0x902010, hWh: 0xd0c8b8,
  // Shirt colors (bright for dark bg contrast)
  tBlue: 0x3b82f6, tGreen: 0x22c55e, tRed: 0xef4444,
  tPurp: 0xa855f7, tAmb: 0xf59e0b, tTeal: 0x14b8a6,
  // Pants / shoes
  pt: 0x1e293b, sh: 0x0f172a, shL: 0x1e293b,
  // Name card
  card: 0x0f0a1e,
  // Status colors
  dotI: 0x475569, dotR: 0x60a5fa, dotD: 0x4ade80, dotE: 0xf87171,
  dotW: 0xfbbf24,
  // Speech bubble
  bubble: 0xf0f9ff, bubbleB: 0x0ea5e9,
  // Particle
  sparkle: 0xffd700,
}};

function hx(n){{return '#'+n.toString(16).padStart(6,'0')}}
function px(c,x,y,col){{c.fillStyle=hx(col);c.fillRect(x,y,1,1)}}
function hs(c,x1,x2,y,col){{c.fillStyle=hx(col);c.fillRect(x1,y,x2-x1+1,1)}}
function bx(c,x,y,w,h,col){{c.fillStyle=hx(col);c.fillRect(x,y,w,h)}}
function rr(c,x,y,w,h,r,col,a){{
  c.save();if(a!==undefined)c.globalAlpha=a;
  c.fillStyle=hx(col);c.beginPath();c.roundRect(x,y,w,h,r);c.fill();c.restore();
}}

// ═══════════════════════════════════════════════════════════════════════════════
//  CHARACTER VARIANTS  [skin, skinS, hair, shirt]
// ═══════════════════════════════════════════════════════════════════════════════
const VAR = [
  [P.sM, P.sMS, P.hBk, P.tBlue],   // Manager  — medium/black/blue
  [P.sL, P.sLS, P.hBk, P.tRed],    // Security — light/black/red
  [P.sM, P.sMS, P.hBr, P.tGreen],  // Reliability
  [P.sL, P.sLS, P.hBl, P.tAmb],    // Cost
  [P.sD, P.sDS, P.hRd, P.tPurp],   // Observability
  [P.sL, P.sLS, P.hBr, P.tTeal],   // Synthesizer
];

// ─── 16×24 character sprite ──────────────────────────────────────────────────
// Pixel Agents uses top-down sprites; we keep our front-facing
// but add proper walk frames (leg movement) and work-state animations
function mkSprite(vi, state, frame) {{
  const [skin,skinS,hair,shirt] = VAR[vi];
  const cv = document.createElement('canvas');
  cv.width=16; cv.height=24;
  const c = cv.getContext('2d');
  c.imageSmoothingEnabled=false;

  // HEAD (y 0-6)
  hs(c,5,10,0,hair); hs(c,4,11,1,hair); hs(c,4,11,2,hair);
  px(c,4,1,hair); px(c,11,1,hair);
  hs(c,4,11,3,skin); hs(c,4,11,4,skin); hs(c,4,11,5,skin);
  hs(c,5,10,6,skin);
  // jaw shadow
  px(c,4,5,skinS); px(c,11,5,skinS);
  // eyes
  const ey = state==='working'?4:3;
  px(c,5,ey,0xf0ede8); px(c,6,ey,0x1a1008); px(c,9,ey,0xf0ede8); px(c,10,ey,0x1a1008);
  // eyebrows
  if(state!=='done') {{hs(c,5,6,2,hair); hs(c,9,10,2,hair)}}
  // nose
  px(c,7,5,skinS);
  // mouth
  if(state==='done'){{px(c,5,6,0x1a1008);px(c,9,6,0x1a1008);hs(c,6,8,7,0x1a1008)}}
  else hs(c,6,9,6,0x1a1008);

  // NECK + COLLAR (y 7-8)
  hs(c,6,9,7,skin); hs(c,5,10,8,0xf0f0f0);

  // BODY / SHIRT (y 9-16)
  for(let y=9;y<=16;y++) {{
    for(let i=3;i<=12;i++) {{
      px(c,i,y, i<=4?0x1e293b : i>=11?0x1e293b : (i===7||i===8)?shirt+0x101010 : shirt);
    }}
  }}
  // shirt pocket
  if(state!=='idle') {{ bx(c,4,11,3,2,shirt-0x202020||0); }}

  // BELT (y 17)
  hs(c,3,12,17,0x1e293b); px(c,7,17,0x8a8a5a); px(c,8,17,0x8a8a5a);

  // LEGS/PANTS (y 18-21)
  const legOff = state==='working' ? (frame%2===0?0:1) : 0;
  for(let y=18;y<=21;y++) {{
    hs(c,4,6,y,P.pt); hs(c,9,11,y,P.pt);
    if(y===19) {{
      if(state==='working') {{
        // typing: arms forward
        px(c,2,y+legOff,skin); px(c,3,y,skin); px(c,12,y,skin); px(c,13,y-legOff,skin);
      }} else if(state==='done') {{
        // arms raised
        px(c,1,y-2,skin); px(c,2,y-3,skin); px(c,13,y-2,skin); px(c,14,y-3,skin);
      }} else {{
        // idle arms at sides
        px(c,3,y,skin); px(c,12,y,skin);
        px(c,3,y+1,skin); px(c,12,y+1,skin);
      }}
    }}
  }}

  // WALK ANIMATION — leg swing
  if(state==='walking') {{
    const swing = Math.sin(frame/3*Math.PI)*2;
    bx(c,4,18,3,4,P.pt);
    bx(c,9,18,3,4,P.pt);
    // left leg forward/back
    bx(c,4,18+Math.round(swing),3,4,P.pt);
    bx(c,9,18-Math.round(swing),3,4,P.pt);
  }}

  // SHOES (y 22-23)
  bx(c,3,22,4,2,P.sh); bx(c,9,22,4,2,P.sh);
  hs(c,3,6,23,P.shL); hs(c,9,12,23,P.shL);

  return cv;
}}

// ═══════════════════════════════════════════════════════════════════════════════
//  TILE FLOOR RENDERER (16×16 tiles)
// ═══════════════════════════════════════════════════════════════════════════════
const TILE = 32; // display pixels per tile

function drawFloor(ctx, cols, rows) {{
  for(let ty=0;ty<rows;ty++) {{
    for(let tx=0;tx<cols;tx++) {{
      const isDark = (tx+ty)%2===0;
      ctx.fillStyle = hx(isDark?P.floorA:P.floorB);
      ctx.fillRect(tx*TILE,ty*TILE,TILE,TILE);
      // subtle tile border
      ctx.strokeStyle = hx(P.floorLine);
      ctx.lineWidth = 0.5;
      ctx.strokeRect(tx*TILE+0.5,ty*TILE+0.5,TILE-1,TILE-1);
    }}
  }}
}}

function drawWall(ctx, x, y, w, h) {{
  bx(ctx,x,y,w,h,P.wall);
  // wall top highlight
  bx(ctx,x,y,w,3,P.wallTop);
  // baseboard
  bx(ctx,x,y+h-4,w,4,P.wallLight);
  // wall trim lines
  ctx.globalAlpha=0.15; ctx.strokeStyle='#fff'; ctx.lineWidth=1;
  for(let i=0;i<Math.floor(w/48);i++) {{
    ctx.beginPath(); ctx.moveTo(x+i*48,y); ctx.lineTo(x+i*48,y+h); ctx.stroke();
  }}
  ctx.globalAlpha=1;
}}

// ─── Draw a full desk workstation at pixel coords x,y ────────────────────────
// Desk spans ~3 tiles wide, 2 tiles tall
function drawDesk(ctx, x, y, active, agentIdx) {{
  // desk surface (wood-look in dark)
  ctx.fillStyle = hx(P.deskWood);
  ctx.beginPath(); ctx.roundRect(x, y, TILE*3, TILE*0.7, 4); ctx.fill();
  // wood grain
  ctx.globalAlpha=0.18;
  for(let i=0;i<6;i++) {{
    ctx.fillStyle=i%2?'#ffffff':'#000000';
    ctx.fillRect(x+4+i*14,y+2,8,TILE*0.7-4);
  }}
  ctx.globalAlpha=1;
  // desk edge (3D front)
  bx(ctx,x,y+Math.round(TILE*0.7),TILE*3,6,P.deskWoodD);

  // monitor base
  bx(ctx,x+TILE-4,y-3,8,4,P.monStand);
  // monitor outer
  ctx.fillStyle=hx(P.monFrame);
  ctx.beginPath(); ctx.roundRect(x+TILE-12, y-30, 40, 28, 3); ctx.fill();
  // screen
  const screenCol = active ? P.monOn : P.monScreen;
  ctx.fillStyle=hx(screenCol);
  ctx.beginPath(); ctx.roundRect(x+TILE-10, y-28, 36, 22, 2); ctx.fill();
  if(active) {{
    // screen glow
    ctx.globalAlpha=0.12; ctx.fillStyle=hx(P.monOn);
    ctx.beginPath(); ctx.roundRect(x+TILE-18,y-36,52,38,6); ctx.fill();
    ctx.globalAlpha=1;
    // screen content lines
    ctx.globalAlpha=0.4; ctx.fillStyle='#ffffff';
    for(let i=0;i<5;i++) ctx.fillRect(x+TILE-8,y-26+i*4,14+((i*7)%18),1);
    ctx.globalAlpha=1;
  }}
  // webcam dot
  ctx.fillStyle='#333'; ctx.beginPath(); ctx.arc(x+TILE+8,y-30,1.5,0,Math.PI*2); ctx.fill();

  // keyboard
  ctx.fillStyle=hx(0x2a2438);
  ctx.beginPath(); ctx.roundRect(x+TILE*0.6, y+6, 36, 8, 1); ctx.fill();
  // keys hint
  ctx.globalAlpha=0.6; ctx.fillStyle='#555';
  for(let r=0;r<2;r++) for(let k=0;k<7;k++) ctx.fillRect(x+TILE*0.6+2+k*5,y+7+r*3,4,2);
  ctx.globalAlpha=1;

  // mouse
  ctx.fillStyle=hx(0x2a2438);
  ctx.beginPath(); ctx.roundRect(x+TILE*1.9,y+4,10,14,4); ctx.fill();

  // chair
  ctx.fillStyle=hx(P.chairBack);
  ctx.beginPath(); ctx.roundRect(x+TILE-4,y+TILE*0.7+6,TILE+8,8,2); ctx.fill();
  bx(ctx,x+TILE-8,y+TILE*0.7+10,8,14,P.chairArm);
  bx(ctx,x+TILE+TILE,y+TILE*0.7+10,8,14,P.chairArm);
  ctx.fillStyle=hx(P.chairSeat);
  ctx.beginPath(); ctx.roundRect(x+TILE-6,y+TILE*0.7+18,TILE+12,10,2); ctx.fill();

  // desk accessories (deterministic by agentIdx)
  _drawAccessory(ctx, x, y, agentIdx);
}}

function _drawAccessory(ctx,x,y,i) {{
  const seed = (i*7+3)%5;
  if(seed===0) {{ // mug
    ctx.fillStyle='#c8c8c8'; ctx.beginPath(); ctx.roundRect(x+6,y+2,10,10,1); ctx.fill();
    ctx.fillStyle='#999'; ctx.fillRect(x+16,y+4,3,5);
    ctx.globalAlpha=0.3; ctx.fillStyle='#fff';
    ctx.fillRect(x+8,y,1,2); ctx.fillRect(x+10,y-1,1,2); ctx.globalAlpha=1;
  }} else if(seed===1) {{ // plant
    ctx.fillStyle='#8b4513'; ctx.beginPath(); ctx.roundRect(x+4,y+4,10,8,1); ctx.fill();
    ctx.fillStyle='#228b22'; ctx.beginPath(); ctx.arc(x+9,y+2,5,0,Math.PI*2); ctx.fill();
    ctx.fillStyle='#1a6b1a'; ctx.beginPath(); ctx.arc(x+7,y,3,0,Math.PI*2); ctx.fill();
  }} else if(seed===2) {{ // post-its
    ctx.fillStyle='#ffee55'; ctx.fillRect(x+4,y+2,10,10);
    ctx.fillStyle='#ff8866'; ctx.fillRect(x+2,y+4,8,8);
    ctx.globalAlpha=0.15; ctx.fillStyle='#000';
    [4,6,8].forEach(l=>ctx.fillRect(x+5,y+l,6,1)); ctx.globalAlpha=1;
  }} else if(seed===3) {{ // books
    [0x4466aa,0xcc4444,0x44aa44].forEach((col,i)=>{{
      ctx.fillStyle=hx(col); ctx.fillRect(x+4+i*4,y+0,3,12);
    }});
  }} else {{ // water bottle
    ctx.fillStyle='#4488aa'; ctx.fillRect(x+8,y+0,2,2);
    ctx.fillStyle='#88bbdd'; ctx.beginPath(); ctx.roundRect(x+7,y+2,4,12,1); ctx.fill();
    ctx.globalAlpha=0.4; ctx.fillStyle='#fff'; ctx.fillRect(x+8,y+3,2,4); ctx.globalAlpha=1;
  }}
}}

// ═══════════════════════════════════════════════════════════════════════════════
//  SPEECH BUBBLE (Pixel Agents style)
// ═══════════════════════════════════════════════════════════════════════════════
function drawBubble(ctx, x, y, text, color) {{
  const w = Math.max(40, text.length*5+16);
  const h = 18;
  const bx2 = x - w/2, by2 = y - h - 8;
  // shadow
  rr(ctx,bx2+1,by2+1,w,h,6,0x000000,0.3);
  // bg
  rr(ctx,bx2,by2,w,h,6,color,0.95);
  // pointer
  ctx.fillStyle=hx(color); ctx.globalAlpha=0.95;
  ctx.beginPath(); ctx.moveTo(x-4,by2+h); ctx.lineTo(x,by2+h+5); ctx.lineTo(x+4,by2+h);
  ctx.closePath(); ctx.fill(); ctx.globalAlpha=1;
  // text
  ctx.font='bold 9px monospace'; ctx.fillStyle='#fff';
  ctx.textAlign='center'; ctx.fillText(text,x,by2+12); ctx.textAlign='left';
}}

// ═══════════════════════════════════════════════════════════════════════════════
//  NAME CARD (dark floating card above desk)
// ═══════════════════════════════════════════════════════════════════════════════
function drawCard(ctx, cx, cy, cw, agent, status, findingCount) {{
  const nm  = LANG==='pt'?agent.nm_pt:agent.nm_en;
  const cW  = Math.max(72, nm.length*6+44);
  const cH  = 20;
  const cX  = cx+(cw-cW)/2;
  const cY  = cy-cH-6;

  // shadow
  rr(ctx,cX+1,cY+2,cW,cH,6,0x000000,0.4);
  // bg
  rr(ctx,cX,cY,cW,cH,6,P.card,0.95);
  // pointer
  ctx.save(); ctx.globalAlpha=0.95; ctx.fillStyle=hx(P.card);
  const tx=cx+cw/2;
  ctx.beginPath();ctx.moveTo(tx-3,cY+cH);ctx.lineTo(tx,cY+cH+4);ctx.lineTo(tx+3,cY+cH);
  ctx.closePath();ctx.fill();ctx.restore();

  // status dot
  const dc = status==='running'?P.dotR:status==='done'?P.dotD:status==='error'?P.dotE:P.dotI;
  const dx=cX+cW-11, dy=cY+cH/2;
  if(status==='running'){{
    ctx.save();ctx.globalAlpha=0.2;ctx.fillStyle=hx(dc);
    ctx.beginPath();ctx.arc(dx,dy,7,0,Math.PI*2);ctx.fill();ctx.restore();
  }}
  ctx.fillStyle=hx(dc);ctx.beginPath();ctx.arc(dx,dy,3,0,Math.PI*2);ctx.fill();

  // finding badge
  if(findingCount>0) {{
    const badgeX=cX+cW-26;
    rr(ctx,badgeX,cY+2,16,12,4,0x4f46e5,1);
    ctx.font='bold 8px sans-serif';ctx.fillStyle='#fff';
    ctx.textAlign='center';ctx.fillText(findingCount,badgeX+8,cY+11);ctx.textAlign='left';
  }}

  // emoji + name
  ctx.font='10px serif'; ctx.fillText(agent.ic,cX+4,cY+13);
  ctx.font='600 9px -apple-system,sans-serif'; ctx.fillStyle='#e2e8f0';
  ctx.fillText(nm,cX+18,cY+13);
}}

// ═══════════════════════════════════════════════════════════════════════════════
//  SPARKLE PARTICLES (done state)
// ═══════════════════════════════════════════════════════════════════════════════
function drawSparkles(ctx, cx, cy, t) {{
  const n=6;
  for(let i=0;i<n;i++) {{
    const a = (i/n)*Math.PI*2+t*0.04;
    const r = 18+Math.sin(t*0.08+i)*6;
    const sx=cx+Math.cos(a)*r, sy=cy+Math.sin(a)*r;
    const alpha=0.6+Math.sin(t*0.1+i)*0.4;
    ctx.save();ctx.globalAlpha=alpha;
    ctx.fillStyle=hx(i%2?P.sparkle:P.dotD);
    ctx.fillRect(Math.round(sx)-1,Math.round(sy)-1,2,2);
    ctx.restore();
  }}
}}

// ═══════════════════════════════════════════════════════════════════════════════
//  AGENT STATE MACHINE  (inspired by Pixel Agents: idle→walk→sit→work→done)
// ═══════════════════════════════════════════════════════════════════════════════
class Agent {{
  constructor(def, deskX, deskY, variant) {{
    this.def     = def;
    this.variant = variant;
    this.deskX   = deskX;   // desk center X in pixels
    this.deskY   = deskY;   // desk Y in pixels
    this.x       = deskX;
    this.y       = deskY + 80; // spawn below desk
    this.targetX = deskX;
    this.targetY = deskY + 40; // seat position
    this.state   = 'walking'; // idle|walking|sitting|working|done|error
    this.frame   = 0;
    this.tick    = 0;
    this.speed   = 1.5;
    this.bubble  = null;  // {{text, color, ttl}}
    this.status  = 'idle';
    this.count   = 0;
  }}

  update(externalStatus, count) {{
    this.tick++;
    this.count = count;

    const prev = this.status;
    this.status = externalStatus;

    // Walk to seat on spawn
    if(this.state==='walking') {{
      const dx=this.targetX-this.x, dy=this.targetY-this.y;
      const dist=Math.sqrt(dx*dx+dy*dy);
      if(dist<this.speed) {{
        this.x=this.targetX; this.y=this.targetY;
        this.state = 'sitting';
      }} else {{
        this.x+=dx/dist*this.speed;
        this.y+=dy/dist*this.speed;
      }}
    }}

    // Transition to work state
    if(this.state==='sitting' && externalStatus==='running') {{
      this.state='working';
      this.bubble={{text:'Analyzing...', color:P.dotR, ttl:120}};
    }}

    // Working animation
    if(this.state==='working') {{
      if(this.tick%8===0) this.frame=(this.frame+1)%4;
      // Occasional thought bubbles
      if(this.tick%180===0) {{
        const msgs=['...','hmm','!','🔍'];
        this.bubble={{text:msgs[Math.floor(Math.random()*msgs.length)],color:P.dotR,ttl:60}};
      }}
      if(externalStatus==='done') {{
        this.state='done';
        this.bubble={{text:'Done! ✓', color:P.dotD, ttl:200}};
      }}
      if(externalStatus==='error') {{
        this.state='error';
        this.bubble={{text:'Error!', color:P.dotE, ttl:200}};
      }}
    }}

    if(this.state==='done' && this.tick%6===0) this.frame=(this.frame+1)%4;

    // Idle bob when sitting and waiting
    if(this.state==='sitting' && this.tick%60===0) {{
      this.bubble={{text:'...', color:P.dotI, ttl:40}};
    }}

    // Tick down bubble
    if(this.bubble) {{ this.bubble.ttl--; if(this.bubble.ttl<=0) this.bubble=null; }}
  }}

  draw(ctx, zoom, cardY) {{
    const zx=Math.round(this.x*zoom), zy=Math.round(this.y*zoom);

    // Determine pose for sprite
    let pose='idle';
    if(this.state==='walking') pose='walking';
    else if(this.state==='working') pose='working';
    else if(this.state==='done') pose='done';

    const sprite = mkSprite(this.variant, pose, this.frame);
    const sw=16*zoom, sh=24*zoom;
    ctx.imageSmoothingEnabled=false;
    ctx.drawImage(sprite, zx-sw/2, zy-sh, sw, sh);

    // Shadow
    ctx.fillStyle='rgba(0,0,0,0.25)';
    ctx.beginPath();ctx.ellipse(zx,zy,sw*0.4,sh*0.08,0,0,Math.PI*2);ctx.fill();

    // Sparkles for done
    if(this.state==='done') drawSparkles(ctx,zx,zy-sh*0.5,this.tick);

    // Speech bubble
    if(this.bubble) {{
      const alpha = Math.min(1, this.bubble.ttl/20);
      ctx.save(); ctx.globalAlpha=alpha;
      drawBubble(ctx,zx,zy-sh,this.bubble.text,this.bubble.color);
      ctx.restore();
    }}
  }}
}}

// ═══════════════════════════════════════════════════════════════════════════════
//  SCENE LAYOUT
// ═══════════════════════════════════════════════════════════════════════════════
// Grid: 4 columns, 3 rows of desks
// Row 0 (top): Manager (center, cols 1-2)
// Row 1: Security, Reliability, Cost, Observability
// Row 2 (bottom): Synthesizer (center, cols 1-2)

// [startCol, endCol, row, agentIdx]
const LAYOUT = [
  [1,2, 0, 0],  // Manager
  [0,0, 1, 1],  // Security
  [1,1, 1, 2],  // Reliability
  [2,2, 1, 3],  // Cost
  [3,3, 1, 4],  // Observability
  [1,2, 2, 5],  // Synthesizer
];

const NCOLS=4, NROWS=3;
const PAD=12, VPAD=40, CARDSPACE=38;

let agents=[];
let sceneW=0, sceneH=0;
let zoom=2; // pixel zoom (2x = each canvas pixel = 2 screen pixels)
let rafId=null;

// ═══════════════════════════════════════════════════════════════════════════════
//  INIT & GAME LOOP
// ═══════════════════════════════════════════════════════════════════════════════
function initScene() {{
  const cv=document.getElementById('cv');
  const avail=cv.parentElement.clientWidth||760;

  // Each desk unit = 3 tiles wide, 2 tiles tall
  const deskUnitW = 3*TILE;
  const deskUnitH = 2*TILE;
  const cellW = Math.floor((avail - PAD*2) / NCOLS);
  const cellH = Math.round(cellW * deskUnitH / deskUnitW) + 20;

  sceneW = avail;
  sceneH = NROWS*cellH + (NROWS-1)*VPAD + PAD*2 + CARDSPACE;

  cv.width  = sceneW;
  cv.height = sceneH;
  cv.style.width  = sceneW+'px';
  cv.style.height = sceneH+'px';

  // Create agents
  agents = LAYOUT.map(([sc,ec,row,ai]) => {{
    const span = ec-sc+1;
    const deskCX = PAD + sc*cellW + (span*cellW)/2;
    const deskTY = PAD + CARDSPACE + row*(cellH+VPAD) + cellH*0.4;
    const ag = new Agent(AGENTS[ai], deskCX, deskTY, AGENTS[ai].variant);
    return {{agent:ag, sc,ec,row,ai, cellW:span*cellW, cellH, cx:PAD+sc*cellW, cy:PAD+CARDSPACE+row*(cellH+VPAD)}};
  }});
}}

function loop(t) {{
  const cv=document.getElementById('cv');
  if(!cv) return;
  const ctx=cv.getContext('2d');
  ctx.imageSmoothingEnabled=false;
  ctx.clearRect(0,0,sceneW,sceneH);

  // Floor
  drawFloor(ctx, Math.ceil(sceneW/TILE)+1, Math.ceil(sceneH/TILE)+1);

  // Top wall strip
  drawWall(ctx,0,0,sceneW,VPAD*0.7);

  agents.forEach(({{agent,sc,ec,row,ai,cellW,cellH,cx,cy}}) => {{
    const sd  = STATES[agent.def.key]||{{status:'idle',count:0}};
    const status = sd.status||'idle';
    const count  = sd.count||0;

    // Update state machine
    agent.update(status,count);

    // Cell background (dark panel)
    const isRun=status==='running', isDone=status==='done', isErr=status==='error';
    const bg  = isRun?0x1e1b38:isDone?0x0f2a1a:isErr?0x2a0f0f:0x1e1a2e;
    const bord= isRun?0x818cf8:isDone?0x22c55e:isErr?0xf87171:0x3d3560;
    rr(ctx,cx,cy,cellW,cellH,6,bg,0.85);
    ctx.strokeStyle=hx(bord); ctx.lineWidth=isRun||isDone||isErr?1.5:0.8;
    ctx.beginPath();ctx.roundRect(cx,cy,cellW,cellH,6);ctx.stroke();

    // Running glow
    if(isRun) {{
      ctx.save(); ctx.globalAlpha=0.08+Math.sin(t*0.003)*0.04;
      ctx.fillStyle=hx(0x818cf8);
      ctx.beginPath();ctx.roundRect(cx,cy,cellW,cellH,6);ctx.fill();
      ctx.restore();
    }}

    // Desk
    const deskX = cx + cellW*0.05;
    const deskY = cy + cellH*0.18;
    drawDesk(ctx, deskX, deskY, isRun||isDone, ai);

    // Character
    agent.draw(ctx, 2, cy);

    // Name card (above cell)
    drawCard(ctx, cx, cy, cellW, agent.def, status, count);

    // Phase label (small, below cell border)
    const phaseLbl = isRun?'🔄 running':isDone?'✅ done':isErr?'❌ error':'⏸ idle';
    ctx.font='8px -apple-system,sans-serif';
    ctx.fillStyle=hx(isRun?0x818cf8:isDone?0x22c55e:isErr?0xf87171:0x475569);
    ctx.textAlign='center';
    ctx.fillText(phaseLbl, cx+cellW/2, cy+cellH-4);
    ctx.textAlign='left';
  }});

  rafId = requestAnimationFrame(loop);
}}

// ═══════════════════════════════════════════════════════════════════════════════
//  MANAGER CARD UPDATE
// ═══════════════════════════════════════════════════════════════════════════════
function updateMgr() {{
  const card=document.getElementById('mgr');
  const stEl=document.getElementById('mst');
  const tags=document.getElementById('tags');
  const brief=document.getElementById('brief');
  const sub=document.getElementById('sub');
  const ms=(STATES['manager_agent']||{{}}).status||'idle';
  card.className='';
  if(ms==='running'){{card.classList.add('running');stEl.textContent=LANG==='pt'?'⏳ rodando…':'⏳ running…'}}
  else if(ms==='done'||Object.keys(PLAN).length>0){{card.classList.add('done');stEl.textContent=LANG==='pt'?'✅ concluído':'✅ done'}}
  else stEl.textContent=LANG==='pt'?'aguardando':'waiting';
  if(LANG==='pt')sub.textContent='Analisa arquitetura · Decide prioridades · Injeta contexto de foco';
  tags.innerHTML='';
  if(PLAN.architecture_type)tags.innerHTML+=`<span class="tag ta">${{PLAN.architecture_type}}</span>`;
  if(PLAN.complexity)tags.innerHTML+=`<span class="tag tx">${{LANG==='pt'?'complexidade':'complexity'}}: ${{PLAN.complexity}}</span>`;
  (PLAN.compliance_flags||[]).forEach(f=>tags.innerHTML+=`<span class="tag tc">⚑ ${{f}}</span>`);
  (PLAN.cloud_providers||[]).forEach(p=>tags.innerHTML+=`<span class="tag tl">☁️ ${{p}}</span>`);
  if(PLAN.manager_briefing){{brief.style.display='block';brief.textContent='💬 '+PLAN.manager_briefing.slice(0,180)}}
}}

// ═══════════════════════════════════════════════════════════════════════════════
//  BOOT
// ═══════════════════════════════════════════════════════════════════════════════
window.addEventListener('load',()=>{{
  updateMgr();
  initScene();
  rafId=requestAnimationFrame(loop);
  window.addEventListener('resize',()=>{{
    if(rafId) cancelAnimationFrame(rafId);
    initScene();
    rafId=requestAnimationFrame(loop);
  }});
}});
</script></body></html>"""


def build_agent_states(log: list[dict]) -> dict:
    states = {"manager_agent": {"status": "idle", "count": 0}}
    for agent_def in AGENT_DEFS[1:]:
        key  = agent_def["key"]
        evts = [v for v in log if v.get("agent") == key]
        if any(v["event"] == "error" for v in evts):
            states[key] = {"status": "error", "count": 0}
        elif any(v["event"] == "done" for v in evts):
            count = next((v.get("count", 0) for v in evts if v["event"] == "done"), 0)
            states[key] = {"status": "done", "count": count}
        elif any(v["event"] == "start" for v in evts):
            states[key] = {"status": "running", "count": 0}
        else:
            states[key] = {"status": "idle", "count": 0}
    return states


def build_plan_dict(plan) -> dict:
    if plan is None:
        return {}
    return {
        "architecture_type": plan.architecture_type,
        "complexity":        plan.complexity,
        "top_risks":         plan.top_risks,
        "compliance_flags":  plan.compliance_flags,
        "cloud_providers":   plan.cloud_providers,
        "manager_briefing":  plan.manager_briefing,
        "active_agents":     plan.active_agents,
        "skipped_agents":    plan.skipped_agents,
    }
