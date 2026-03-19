"""
Squad Office — procedural pixel art Canvas renderer.
Generates a full Gather.town-style office scene with 48×48 character sprites,
detailed workstations, accessories, floating name cards, and the Agent Manager.
Rendered as a self-contained HTML/JS block embedded in Streamlit via st.components.v1.html.
"""

from __future__ import annotations
import json


# ── Agent metadata ─────────────────────────────────────────────────────────────

AGENT_DEFS = [
    {"key": "manager_agent",      "ic": "🎯", "nm_en": "Manager",      "nm_pt": "Gerente",       "variant": 0},
    {"key": "security_agent",     "ic": "🔐", "nm_en": "Security",     "nm_pt": "Segurança",     "variant": 1},
    {"key": "reliability_agent",  "ic": "🛡️", "nm_en": "Reliability",  "nm_pt": "Confiabilidade","variant": 2},
    {"key": "cost_agent",         "ic": "💰", "nm_en": "Cost",          "nm_pt": "Custo",         "variant": 3},
    {"key": "observability_agent","ic": "📡", "nm_en": "Observability", "nm_pt": "Observabilidade","variant": 4},
    {"key": "synthesizer_agent",  "ic": "🧠", "nm_en": "Synthesizer",  "nm_pt": "Sintetizador",  "variant": 5},
]


def build_squad_office_html(agent_states: dict, lang: str = "en", plan: dict | None = None) -> str:
    """
    agent_states: { agent_key: {"status": "idle|running|done|error", "count": int} }
    plan: orchestration plan snapshot dict or None
    Returns: full self-contained HTML string for st.components.v1.html
    """
    states_json = json.dumps(agent_states)
    plan_json   = json.dumps(plan or {})
    agents_json = json.dumps(AGENT_DEFS)
    lang_js     = json.dumps(lang)

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #f8f9fc; font-family: -apple-system, 'Segoe UI', sans-serif; overflow-x: hidden; }}
  #office-wrap {{ width: 100%; padding: 12px 0 8px; }}
  canvas {{ display: block; image-rendering: pixelated; image-rendering: crisp-edges; }}

  /* Manager card */
  #mgr-card {{
    margin: 0 16px 12px;
    background: #fff;
    border: 1.5px solid #e5e7eb;
    border-radius: 12px;
    padding: 12px 16px;
    display: flex; align-items: center; gap: 12px;
    transition: border-color .3s, background .3s;
    font-size: 13px;
  }}
  #mgr-card.done  {{ border-color: #16a34a; background: #f0fdf4; }}
  #mgr-card.running {{ border-color: #6366f1; background: #f5f3ff;
    box-shadow: 0 0 0 3px rgba(99,102,241,.1); animation: pulse-border 1.5s ease-in-out infinite; }}
  #mgr-card .ic {{ font-size: 1.4rem; flex-shrink: 0; }}
  #mgr-card .info {{ flex: 1; min-width: 0; }}
  #mgr-card .title {{ font-weight: 700; color: #111; }}
  #mgr-card .sub {{ font-size: 11px; color: #9ca3af; margin-top: 2px; }}
  #mgr-card .status {{ font-size: 11px; font-weight: 700; color: #6b7280; flex-shrink: 0; }}
  #mgr-card.done .status {{ color: #16a34a; }}
  #mgr-card.running .status {{ color: #6366f1; }}
  #mgr-tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }}
  .tag {{
    padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600;
  }}
  .tag-arch  {{ background: #f5f3ff; border: 1px solid #ddd6fe; color: #4338ca; }}
  .tag-comp  {{ background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }}
  .tag-cloud {{ background: #f0f9ff; border: 1px solid #bae6fd; color: #0369a1; }}
  .tag-cplx  {{ background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }}
  #mgr-briefing {{ font-size: 11px; color: #374151; margin-top: 8px; font-style: italic; }}

  /* Canvas scene */
  #scene-wrap {{ position: relative; overflow: hidden; }}
  #scene-canvas {{ width: 100%; }}

  @keyframes pulse-border {{
    0%,100% {{ box-shadow: 0 0 0 3px rgba(99,102,241,.1); }}
    50%      {{ box-shadow: 0 0 0 5px rgba(99,102,241,.2); }}
  }}
</style>
</head>
<body>
<div id="office-wrap">
  <!-- Manager card -->
  <div id="mgr-card">
    <div class="ic">🎯</div>
    <div class="info">
      <div class="title">Agent Manager <span style="font-size:10px;font-weight:400;color:#9ca3af">— Phase 0</span></div>
      <div class="sub" id="mgr-sub">Analyzes architecture · Decides agent priorities · Injects focus context</div>
      <div id="mgr-tags"></div>
      <div id="mgr-briefing" style="display:none"></div>
    </div>
    <div class="status" id="mgr-status">waiting</div>
  </div>

  <!-- Canvas scene -->
  <div id="scene-wrap">
    <canvas id="scene-canvas"></canvas>
  </div>
</div>

<script>
// ═══════════════════════════════════════════════════════
//  DATA
// ═══════════════════════════════════════════════════════
const AGENT_STATES = {states_json};
const PLAN         = {plan_json};
const AGENTS       = {agents_json};
const LANG         = {lang_js};

// ═══════════════════════════════════════════════════════
//  PALETTE
// ═══════════════════════════════════════════════════════
const P = {{
  // Skin tones
  skinLight:  0xFFD5A8, skinLightShadow: 0xD4A883,
  skinMedium: 0xC68642, skinMediumShadow: 0xB48854,
  skinDark:   0x8D5524, skinDarkShadow:  0x6B4320,
  // Hair
  hairBlack: 0x2C2018, hairBlackL: 0x3A3028, hairBlackD: 0x1A1008,
  hairBrown: 0x6B4226, hairBrownL: 0x8A6A4A, hairBrownD: 0x4A2A0A,
  hairBlond: 0xD4A017, hairBlondL: 0xE4B850, hairBlondD: 0xB48830,
  hairRed:   0xA0522D, hairRedL:   0xC05030, hairRedD:   0x903010,
  // Shirts
  shirtBlue:  0x4A7AB0, shirtBlueL:  0x5A8AC0, shirtBlueD:  0x3A6898,
  shirtGreen: 0x4A8A4A, shirtGreenL: 0x5A9A5A, shirtGreenD: 0x3A7A3A,
  shirtRed:   0xA04848, shirtRedL:   0xB85858, shirtRedD:   0x983838,
  shirtWhite: 0xE0D8CC, shirtWhiteL: 0xF0E8DC, shirtWhiteD: 0xD0C8BC,
  shirtPurp:  0x7A58A0, shirtPurpL:  0x8A68B0, shirtPurpD:  0x6A4890,
  shirtTeal:  0x3A8888, shirtTealL:  0x4A9898, shirtTealD:  0x2A7878,
  // Pants / shoes
  pants:  0x3A3A4A, pantsD: 0x2A2A3A,
  shoe:   0x2A2018, shoeL:  0x3A3028,
  // Misc
  collar: 0xF0F0F0,
  belt:   0x3A3028, beltB: 0x8A8A6A,
  // Desk
  deskTop: 0xD4B888, deskL: 0xE0CCAA, deskD: 0xC4AF8C, deskEdge: 0xB09870,
  // Monitor
  monFrame: 0x1E1E2A, monScreen: 0x0A0A1A, monOn: 0x48D1CC,
  monStand: 0x4A4A5A,
  // Chair
  chairBack: 0x2A2A3A, chairSeat: 0x323244, chairArm: 0x282838,
  // Room
  floor: 0xF0EDE8, floorLine: 0xE0DDD8,
  wall:  0xE8E4DE, wallLine: 0xD8D4CE,
  // Accessories
  mugW: 0xE0E0E0, mugR: 0xCCCCCC,
  postY: 0xFFEE55, postP: 0xFF8866,
  bookR: 0xCC4444, bookB: 0x4466AA, bookG: 0x44AA44,
  plantG: 0x44AA44, plantD: 0x2A8A2A, plantP: 0xCC6644,
  waterB: 0x88BBDD, waterC: 0x4488AA,
  photoF: 0x3A3028,
  // Name card
  cardBg: 0x14141C,
  // Status dots
  dotIdle:    0xAAAACC,
  dotRunning: 0x60B0FF,
  dotDone:    0x60F080,
  dotError:   0xFF6060,
}};

// Convert hex int to CSS color string
function hex(n) {{
  return '#' + n.toString(16).padStart(6, '0');
}}

// ═══════════════════════════════════════════════════════
//  CHARACTER VARIANTS
// ═══════════════════════════════════════════════════════
const VARIANTS = [
  // Manager: black hair, medium skin, blue shirt
  {{ hair:P.hairBlack, hairL:P.hairBlackL, hairD:P.hairBlackD, skin:P.skinMedium, skinS:P.skinMediumShadow, shirt:P.shirtBlue, shirtL:P.shirtBlueL, shirtD:P.shirtBlueD, pants:P.pants, pantsD:P.pantsD, shoe:P.shoe, shoeL:P.shoeL }},
  // Security: black hair, light skin, red shirt
  {{ hair:P.hairBlack, hairL:P.hairBlackL, hairD:P.hairBlackD, skin:P.skinLight, skinS:P.skinLightShadow, shirt:P.shirtRed,  shirtL:P.shirtRedL,  shirtD:P.shirtRedD,  pants:P.pants, pantsD:P.pantsD, shoe:P.shoe, shoeL:P.shoeL }},
  // Reliability: brown hair, medium skin, green shirt
  {{ hair:P.hairBrown, hairL:P.hairBrownL, hairD:P.hairBrownD, skin:P.skinMedium, skinS:P.skinMediumShadow, shirt:P.shirtGreen, shirtL:P.shirtGreenL, shirtD:P.shirtGreenD, pants:P.pants, pantsD:P.pantsD, shoe:P.shoe, shoeL:P.shoeL }},
  // Cost: blonde hair, light skin, white shirt
  {{ hair:P.hairBlond, hairL:P.hairBlondL, hairD:P.hairBlondD, skin:P.skinLight, skinS:P.skinLightShadow, shirt:P.shirtWhite, shirtL:P.shirtWhiteL, shirtD:P.shirtWhiteD, pants:P.pants, pantsD:P.pantsD, shoe:P.shoe, shoeL:P.shoeL }},
  // Observability: red hair, dark skin, purple shirt
  {{ hair:P.hairRed,   hairL:P.hairRedL,   hairD:P.hairRedD,   skin:P.skinDark,  skinS:P.skinDarkShadow,  shirt:P.shirtPurp, shirtL:P.shirtPurpL,  shirtD:P.shirtPurpD,  pants:P.pants, pantsD:P.pantsD, shoe:P.shoe, shoeL:P.shoeL }},
  // Synthesizer: brown hair, light skin, teal shirt
  {{ hair:P.hairBrown, hairL:P.hairBrownL, hairD:P.hairBrownD, skin:P.skinLight, skinS:P.skinLightShadow, shirt:P.shirtTeal, shirtL:P.shirtTealL,  shirtD:P.shirtTealD,  pants:P.pants, pantsD:P.pantsD, shoe:P.shoe, shoeL:P.shoeL }},
];

// ═══════════════════════════════════════════════════════
//  PIXEL DRAWING HELPERS
// ═══════════════════════════════════════════════════════
function px(ctx, x, y, color) {{
  ctx.fillStyle = hex(color);
  ctx.fillRect(x, y, 1, 1);
}}

function hspan(ctx, x1, x2, y, color) {{
  ctx.fillStyle = hex(color);
  ctx.fillRect(x1, y, x2 - x1 + 1, 1);
}}

function rect(ctx, x, y, w, h, color) {{
  ctx.fillStyle = hex(color);
  ctx.fillRect(x, y, w, h);
}}

function rrect(ctx, x, y, w, h, r, color, alpha) {{
  ctx.save();
  ctx.globalAlpha = alpha !== undefined ? alpha : 1;
  ctx.fillStyle = hex(color);
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
  ctx.restore();
}}

// ═══════════════════════════════════════════════════════
//  CHARACTER SPRITE (48×48)
// ═══════════════════════════════════════════════════════
function drawHead(ctx, c, mouth) {{
  // Hair rows 2-7
  hspan(ctx, 16, 30, 2, c.hair);
  hspan(ctx, 15, 31, 3, c.hair);
  hspan(ctx, 14, 32, 4, c.hair);
  hspan(ctx, 14, 32, 5, c.hair);
  // Hair highlights
  px(ctx,17,3,c.hairL); px(ctx,20,3,c.hairL); px(ctx,28,3,c.hairL);
  px(ctx,16,4,c.hairL); px(ctx,22,4,c.hairL); px(ctx,25,4,c.hairL); px(ctx,30,4,c.hairL);
  // Hair dark edges
  px(ctx,14,5,c.hairD); px(ctx,32,5,c.hairD);
  px(ctx,15,4,c.hairD); px(ctx,31,4,c.hairD);
  // Sideburns
  px(ctx,14,6,c.hair); px(ctx,14,7,c.hair);
  px(ctx,32,6,c.hair); px(ctx,32,7,c.hair);

  // Face rows 6-14
  hspan(ctx,15,31,6,c.skin); hspan(ctx,15,31,7,c.skin);
  hspan(ctx,15,31,8,c.skin); hspan(ctx,15,31,9,c.skin);
  hspan(ctx,16,30,10,c.skin); hspan(ctx,16,30,11,c.skin);
  hspan(ctx,17,29,12,c.skin); hspan(ctx,18,28,13,c.skin);
  hspan(ctx,19,27,14,c.skin);
  // Jaw shadow
  [16,17].forEach(i=>{{ px(ctx,i,11,c.skinS); px(ctx,i,12,c.skinS); }});
  [29,30].forEach(i=>{{ px(ctx,i,11,c.skinS); px(ctx,i,12,c.skinS); }});
  px(ctx,18,13,c.skinS); px(ctx,19,13,c.skinS);
  px(ctx,27,13,c.skinS); px(ctx,28,13,c.skinS);

  // Eyebrows
  hspan(ctx,18,20,7,c.hairD); hspan(ctx,26,28,7,c.hairD);

  // Eyes
  const pupilY = mouth === 'focused' ? 10 : 9;
  px(ctx,18,9,0xF0EDE8); px(ctx,19,pupilY,0x2A2018); px(ctx,20,9,0xF0EDE8);
  px(ctx,26,9,0xF0EDE8); px(ctx,27,pupilY,0x2A2018); px(ctx,28,9,0xF0EDE8);

  // Nose
  px(ctx,23,11,c.skinS); px(ctx,23,12,c.skinS);

  // Mouth
  if (mouth === 'smile') {{
    px(ctx,20,13,0x2A2018); px(ctx,26,13,0x2A2018);
    hspan(ctx,21,25,14,0x2A2018);
  }} else {{
    hspan(ctx,21,25,14,0x2A2018);
  }}

  // Ears
  px(ctx,14,8,c.skin); px(ctx,14,9,c.skinS);
  px(ctx,32,8,c.skin); px(ctx,32,9,c.skinS);
}}

function drawBody(ctx, c) {{
  // Neck
  hspan(ctx,20,26,15,c.skin); hspan(ctx,21,25,16,c.skin);
  px(ctx,20,15,c.skinS); px(ctx,26,15,c.skinS);
  // Collar
  hspan(ctx,17,29,17,P.collar);
  px(ctx,22,17,0xE0E0E0); px(ctx,23,17,0xE0E0E0); px(ctx,24,17,0xE0E0E0);
  // Shirt body
  for (let y=18; y<=28; y++) {{
    for (let i=13; i<=33; i++) {{
      const col = i<=15 ? c.shirtD : i>=31 ? c.shirtD : (i>=22&&i<=24) ? c.shirtL : c.shirt;
      px(ctx,i,y,col);
    }}
  }}
  // Belt
  hspan(ctx,13,33,29,c.pantsD);
  px(ctx,22,29,P.beltB); px(ctx,23,29,P.beltB); px(ctx,24,29,P.beltB);
  // Pants
  for (let y=30; y<=39; y++) {{
    for (let i=14; i<=21; i++) px(ctx,i,y,i<=15?c.pantsD:c.pants);
    for (let i=25; i<=32; i++) px(ctx,i,y,i>=31?c.pantsD:c.pants);
    px(ctx,21,y,c.pantsD); px(ctx,25,y,c.pantsD);
  }}
  // Shoes
  for (let i=13;i<=22;i++) {{ px(ctx,i,40,c.shoe); px(ctx,i,41,c.shoe); }}
  for (let i=13;i<=22;i++) px(ctx,i,42,i<=14?c.shoeL:c.shoe);
  hspan(ctx,13,22,43,c.shoeL);
  for (let i=24;i<=33;i++) {{ px(ctx,i,40,c.shoe); px(ctx,i,41,c.shoe); }}
  for (let i=24;i<=33;i++) px(ctx,i,42,i>=32?c.shoeL:c.shoe);
  hspan(ctx,24,33,43,c.shoeL);
}}

function drawArmsIdle(ctx, c) {{
  for (let y=18;y<=22;y++) {{ px(ctx,11,y,c.shirt); px(ctx,12,y,c.shirt); }}
  px(ctx,12,19,c.shirtD); px(ctx,12,20,c.shirtD);
  for (let y=23;y<=27;y++) {{ px(ctx,10,y,c.skin); px(ctx,11,y,c.skin); }}
  px(ctx,8,28,c.skin); px(ctx,9,28,c.skin); px(ctx,10,28,c.skin);
  for (let y=18;y<=22;y++) {{ px(ctx,34,y,c.shirt); px(ctx,35,y,c.shirt); }}
  px(ctx,34,19,c.shirtD); px(ctx,34,20,c.shirtD);
  for (let y=23;y<=27;y++) {{ px(ctx,35,y,c.skin); px(ctx,36,y,c.skin); }}
  px(ctx,36,28,c.skin); px(ctx,37,28,c.skin); px(ctx,38,28,c.skin);
}}

function drawArmsWorking(ctx, c, frame) {{
  for (let y=18;y<=20;y++) {{ px(ctx,11,y,c.shirt); px(ctx,12,y,c.shirt); }}
  for (let y=18;y<=20;y++) {{ px(ctx,34,y,c.shirt); px(ctx,35,y,c.shirt); }}
  if (frame===0) {{
    for (let y=21;y<=24;y++) {{ px(ctx,10,y,c.skin); px(ctx,11,y,c.skin); }}
    px(ctx,11,25,c.skin); px(ctx,12,25,c.skin); px(ctx,13,26,c.skin);
    for (let y=21;y<=24;y++) {{ px(ctx,35,y,c.skin); px(ctx,36,y,c.skin); }}
    px(ctx,34,25,c.skin); px(ctx,35,25,c.skin); px(ctx,33,26,c.skin);
  }} else {{
    for (let y=21;y<=23;y++) {{ px(ctx,10,y,c.skin); px(ctx,11,y,c.skin); }}
    px(ctx,11,24,c.skin); px(ctx,12,24,c.skin); px(ctx,13,27,c.skin);
    for (let y=21;y<=23;y++) {{ px(ctx,35,y,c.skin); px(ctx,36,y,c.skin); }}
    px(ctx,34,24,c.skin); px(ctx,35,24,c.skin); px(ctx,33,27,c.skin);
  }}
}}

function drawArmsDone(ctx, c) {{
  px(ctx,11,18,c.shirt); px(ctx,12,18,c.shirt);
  px(ctx,10,17,c.skin); px(ctx,9,16,c.skin);
  [12,11,10,9].forEach((y,i)=>px(ctx,8-i,y,c.skin));
  px(ctx,34,18,c.shirt); px(ctx,35,18,c.shirt);
  px(ctx,36,17,c.skin); px(ctx,37,16,c.skin);
  [12,11,10,9].forEach((y,i)=>px(ctx,38+i,y,c.skin));
}}

function makeCharCanvas(variant, pose, frame) {{
  const c   = VARIANTS[variant];
  const cvs = document.createElement('canvas');
  cvs.width = cvs.height = 48;
  const ctx = cvs.getContext('2d');
  ctx.imageSmoothingEnabled = false;

  const mouth = pose==='done' ? 'smile' : pose==='working' ? 'focused' : 'neutral';
  drawHead(ctx, c, mouth);
  drawBody(ctx, c);
  if (pose==='working') drawArmsWorking(ctx, c, frame||0);
  else if (pose==='done') drawArmsDone(ctx, c);
  else drawArmsIdle(ctx, c);
  return cvs;
}}

// ═══════════════════════════════════════════════════════
//  WORKSTATION (drawn into main canvas, offset x,y)
// ═══════════════════════════════════════════════════════
const CW = 128; // cell width
const CH = 152; // cell height (extra for name card)

function drawDeskBack(ctx, ox, oy, working) {{
  // Chair back
  rect(ctx, ox+38, oy+56, 52, 4, P.chairBack);
  rect(ctx, ox+39, oy+56, 50, 2, P.chairArm);
  // Armrests
  rect(ctx, ox+34, oy+60, 8, 12, P.chairBack);
  rect(ctx, ox+35, oy+60, 6, 2, P.chairArm);
  rect(ctx, ox+86, oy+60, 8, 12, P.chairBack);
  rect(ctx, ox+87, oy+60, 6, 2, P.chairArm);
  // Seat cushion
  rect(ctx, ox+42, oy+68, 44, 14, P.chairBack);
  rect(ctx, ox+44, oy+70, 40, 10, P.chairSeat);

  // Desk surface wood grain
  const deskY = oy+4;
  rect(ctx, ox+10, deskY, 108, 44, P.deskTop);
  for (let row=0; row<11; row++) {{
    const shade = row%3===0 ? P.deskL : row%3===1 ? P.deskTop : P.deskD;
    rect(ctx, ox+10, deskY+row*4, 108, 3, shade);
  }}
  rect(ctx, ox+10, deskY, 2, 44, P.deskD);
  rect(ctx, ox+116, deskY, 2, 44, P.deskD);

  // Monitor frame
  ctx.fillStyle = hex(0x1A1A22);
  ctx.beginPath(); ctx.roundRect(ox+34, oy+8, 60, 30, 2); ctx.fill();
  ctx.fillStyle = hex(P.monFrame);
  ctx.beginPath(); ctx.roundRect(ox+35, oy+9, 58, 28, 1); ctx.fill();

  // Screen
  ctx.fillStyle = hex(working ? P.monOn : P.monScreen);
  if (working) ctx.globalAlpha = 0.9;
  ctx.beginPath(); ctx.roundRect(ox+37, oy+11, 54, 24, 1); ctx.fill();
  ctx.globalAlpha = 1;

  if (working) {{
    // Screen content hint lines
    ctx.globalAlpha = 0.35;
    ctx.fillStyle = '#ffffff';
    for (let i=0;i<5;i++) {{
      const lw = 18 + ((i*11)%24);
      ctx.fillRect(ox+39, oy+13+i*4, lw, 1);
    }}
    ctx.globalAlpha = 1;
    // Glow
    ctx.globalAlpha = 0.07;
    ctx.fillStyle = hex(P.monOn);
    ctx.beginPath(); ctx.roundRect(ox+29, oy+5, 70, 38, 4); ctx.fill();
    ctx.globalAlpha = 1;
  }}

  // Reflection
  ctx.globalAlpha = 0.08;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(ox+37, oy+11, 54, 2);
  ctx.globalAlpha = 1;
  // Webcam
  rect(ctx, ox+63, oy+9, 2, 1, 0x222222);
  // Chin
  rect(ctx, ox+37, oy+35, 54, 3, P.monFrame);
  // Stand
  rect(ctx, ox+61, oy+38, 6, 5, P.monStand);
  rect(ctx, ox+62, oy+39, 4, 3, 0x5A5A6A);
  ctx.fillStyle = hex(P.monStand);
  ctx.beginPath(); ctx.roundRect(ox+52, oy+43, 24, 4, 2); ctx.fill();
  ctx.fillStyle = '#5a5a6a';
  ctx.beginPath(); ctx.roundRect(ox+54, oy+43, 20, 2, 1); ctx.fill();
}}

function drawDeskFront(ctx, ox, oy) {{
  // Desk front edge
  rect(ctx, ox+10, oy+48, 108, 6, P.deskEdge);
  ctx.globalAlpha = 0.25;
  rect(ctx, ox+10, oy+53, 108, 2, 0x000000);
  ctx.globalAlpha = 0.08;
  rect(ctx, ox+12, oy+55, 104, 2, 0x000000);
  ctx.globalAlpha = 1;

  // Keyboard
  ctx.fillStyle = hex(0x3A3A42);
  ctx.beginPath(); ctx.roundRect(ox+40, oy+48, 36, 8, 1); ctx.fill();
  rect(ctx, ox+41, oy+48, 34, 1, 0x4A4A52);
  // Keys
  for (let row=0; row<3; row++) {{
    for (let k=0; k<8; k++) {{
      rect(ctx, ox+42+k*4, oy+49+row*2, 3, 1, 0x5A5A5A);
    }}
  }}
  rect(ctx, ox+50, oy+55, 12, 1, 0x5A5A5A);

  // Mousepad
  rect(ctx, ox+80, oy+46, 16, 18, 0x2A2A3A);
  ctx.fillStyle = hex(0x3A3A42);
  ctx.beginPath(); ctx.roundRect(ox+83, oy+48, 10, 13, 3); ctx.fill();
  rect(ctx, ox+84, oy+48, 8, 2, 0x4A4A52);
  rect(ctx, ox+87, oy+48, 2, 3, 0x5A5A62);
  rect(ctx, ox+83, oy+48, 1, 13, 0x2A2A32);

  // Chair pole + casters
  rect(ctx, ox+62, oy+108, 4, 4, P.monStand);
  const cx = ox+64, cy = oy+116;
  for (let i=0;i<5;i++) {{
    const a = i/5*Math.PI*2-Math.PI/2;
    const wx = cx+Math.round(Math.cos(a)*16);
    const wy = cy+Math.round(Math.sin(a)*8);
    rect(ctx, wx-2, wy-1, 4, 3, P.monStand);
    rect(ctx, wx-1, wy+1, 2, 2, 0x5A5A6A);
  }}
}}

// ── Accessories ──────────────────────────────────────────
function drawMug(ctx, x, y) {{
  rect(ctx,x,y+2,8,8,P.mugW); rect(ctx,x,y+2,8,2,P.mugR);
  rect(ctx,x+8,y+4,3,4,P.mugR);
  ctx.globalAlpha=0.35; rect(ctx,x+2,y,1,1,0xFFFFFF);
  ctx.globalAlpha=0.25; rect(ctx,x+4,y-1,1,1,0xFFFFFF);
  ctx.globalAlpha=0.15; rect(ctx,x+3,y-2,1,1,0xFFFFFF);
  ctx.globalAlpha=1;
}}
function drawPlant(ctx, x, y) {{
  rect(ctx,x+1,y+8,8,6,P.plantP); rect(ctx,x,y+6,10,3,P.plantP);
  ctx.fillStyle=hex(P.plantG); ctx.beginPath(); ctx.arc(x+5,y+4,3,0,Math.PI*2); ctx.fill();
  ctx.fillStyle=hex(P.plantD); ctx.beginPath(); ctx.arc(x+3,y+2,2,0,Math.PI*2); ctx.fill();
  ctx.fillStyle=hex(P.plantG); ctx.beginPath(); ctx.arc(x+7,y+2,2,0,Math.PI*2); ctx.fill();
  ctx.fillStyle=hex(P.plantD); ctx.beginPath(); ctx.arc(x+5,y+1,2,0,Math.PI*2); ctx.fill();
}}
function drawPostIts(ctx, x, y) {{
  rect(ctx,x,y,7,7,P.postP);
  rect(ctx,x+3,y+2,8,8,P.postY);
  rect(ctx,x+3,y+2,8,2,0xEEDD44);
  ctx.globalAlpha=0.12; rect(ctx,x+4,y+5,5,1,0); rect(ctx,x+4,y+7,4,1,0);
  ctx.globalAlpha=1;
}}
function drawBooks(ctx, x, y) {{
  rect(ctx,x,y+4,10,3,P.bookR); rect(ctx,x,y+2,10,3,P.bookB); rect(ctx,x+1,y,8,3,P.bookG);
  ctx.globalAlpha=0.15;
  rect(ctx,x,y+4,1,3,0); rect(ctx,x,y+2,1,3,0); rect(ctx,x+1,y,1,3,0);
  ctx.globalAlpha=1;
}}
function drawWater(ctx, x, y) {{
  rect(ctx,x+1,y,4,2,P.waterC); rect(ctx,x,y+2,6,10,P.waterB);
  ctx.globalAlpha=0.5; rect(ctx,x+1,y+3,4,4,0xAADDEE); ctx.globalAlpha=1;
}}

const ACCESSORIES = [drawMug, drawPlant, drawPostIts, drawBooks, drawWater];

function drawAccessories(ctx, ox, oy, agentIndex) {{
  const seed = agentIndex * 7 + 3;
  const i1 = seed % ACCESSORIES.length;
  const i2 = (seed + 2) % ACCESSORIES.length;
  ACCESSORIES[i1](ctx, ox+14, oy+38);
  if (i2 !== i1) ACCESSORIES[i2](ctx, ox+100, oy+38);
}}

// ═══════════════════════════════════════════════════════
//  NAME CARD (drawn above cell, Y < 0 relative to cell)
// ═══════════════════════════════════════════════════════
function drawNameCard(ctx, ox, oy, agent, statusStr) {{
  const nm = LANG === 'pt' ? agent.nm_pt : agent.nm_en;
  const cardW = Math.max(90, nm.length * 8 + 52);
  const cardH = 22;
  const cardX = ox + (CW - cardW) / 2;
  const cardY = oy - 26;

  // Shadow
  ctx.globalAlpha = 0.28;
  rrect(ctx, cardX+1, cardY+2, cardW, cardH, 8, 0x000000);
  ctx.globalAlpha = 1;

  // Background
  rrect(ctx, cardX, cardY, cardW, cardH, 8, P.cardBg, 0.92);

  // Pointer triangle
  ctx.globalAlpha = 0.92;
  ctx.fillStyle = hex(P.cardBg);
  const tx = ox + CW/2;
  ctx.beginPath();
  ctx.moveTo(tx-5, cardY+cardH);
  ctx.lineTo(tx, cardY+cardH+5);
  ctx.lineTo(tx+5, cardY+cardH);
  ctx.closePath();
  ctx.fill();
  ctx.globalAlpha = 1;

  // Status dot
  const dotColor = statusStr==='running' ? P.dotRunning
    : statusStr==='done' ? P.dotDone
    : statusStr==='error' ? P.dotError
    : P.dotIdle;
  const dotX = cardX + cardW - 14;
  const dotY = cardY + cardH/2;
  if (statusStr === 'running' || statusStr === 'done') {{
    ctx.globalAlpha = 0.25;
    ctx.fillStyle = hex(dotColor);
    ctx.beginPath(); ctx.arc(dotX, dotY, 6, 0, Math.PI*2); ctx.fill();
    ctx.globalAlpha = 1;
  }}
  ctx.fillStyle = hex(dotColor);
  ctx.beginPath(); ctx.arc(dotX, dotY, 3.5, 0, Math.PI*2); ctx.fill();

  // Emoji
  ctx.font = '11px serif';
  ctx.fillText(agent.ic, cardX+6, cardY+15);

  // Name
  ctx.font = '600 11px -apple-system,system-ui,sans-serif';
  ctx.fillStyle = '#ffffff';
  ctx.fillText(nm, cardX+22, cardY+15);
}}

// ═══════════════════════════════════════════════════════
//  ROOM BACKGROUND
// ═══════════════════════════════════════════════════════
function drawRoom(ctx, W, H) {{
  // Floor
  ctx.fillStyle = hex(P.floor);
  ctx.fillRect(0, 0, W, H);
  // Floor grid lines
  ctx.strokeStyle = hex(P.floorLine);
  ctx.lineWidth = 1;
  for (let x=0; x<W; x+=32) {{
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }}
  for (let y=0; y<H; y+=32) {{
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }}
}}

// ═══════════════════════════════════════════════════════
//  MAIN RENDER
// ═══════════════════════════════════════════════════════
const SCALE  = 2;      // CSS scale (retina)
const COLS   = 3;      // agents per row (manager + 3 specialists in row 1, 2 remaining in row 2, synth in row 3)
const PAD    = 16;     // horizontal padding
const GAP    = 8;      // gap between cells

// Layout: Row 0 = manager (centered, wider)
//         Row 1 = security, reliability, cost, observability (4 cells)
//         Row 2 = synthesizer (centered)
const LAYOUTS = [
  // [col, row, agentIndex in AGENTS]
  [1, 0, 0],  // manager — row 0, center of 3
  [0, 1, 1],  // security
  [1, 1, 2],  // reliability
  [2, 1, 3],  // cost
  [3, 1, 4],  // observability
  [1.5, 2, 5], // synthesizer — centered between col 1 and 2
];
const TOTAL_COLS = 4;

let animFrame = 0;
let animTimer = null;

function render() {{
  const canvas = document.getElementById('scene-canvas');
  if (!canvas) return;

  const availW = canvas.parentElement.clientWidth || 800;
  const cellW  = Math.floor((availW - PAD*2 - GAP*(TOTAL_COLS-1)) / TOTAL_COLS);
  const cellH  = Math.round(cellW * CH / CW);
  const totalW = TOTAL_COLS * cellW + (TOTAL_COLS-1)*GAP + PAD*2;
  const totalH = 3 * cellH + 2*GAP + PAD*2 + 32; // +32 for name card overflow

  canvas.width  = totalW;
  canvas.height = totalH;
  canvas.style.width  = totalW + 'px';
  canvas.style.height = totalH + 'px';

  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, totalW, totalH);
  drawRoom(ctx, totalW, totalH);

  LAYOUTS.forEach(([col, row, agIdx]) => {{
    const agent  = AGENTS[agIdx];
    const stData = AGENT_STATES[agent.key] || {{status:'idle', count:0}};
    const status = stData.status || 'idle';
    const isRunning = status === 'running';
    const isDone    = status === 'done';
    const isError   = status === 'error';

    // Cell pixel position
    const cx = PAD + col * (cellW + GAP);
    const cy = PAD + 32 + row * (cellH + GAP); // +32 for name card top overflow

    // Cell background with status tint
    ctx.save();
    if (isRunning) {{
      rrect(ctx, cx, cy, cellW, cellH, 6, 0xF5F3FF, 0.9);
      ctx.strokeStyle = '#6366f1'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.roundRect(cx, cy, cellW, cellH, 6); ctx.stroke();
    }} else if (isDone) {{
      rrect(ctx, cx, cy, cellW, cellH, 6, 0xF0FDF4, 0.9);
      ctx.strokeStyle = '#16a34a'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.roundRect(cx, cy, cellW, cellH, 6); ctx.stroke();
    }} else if (isError) {{
      rrect(ctx, cx, cy, cellW, cellH, 6, 0xFEF2F2, 0.9);
      ctx.strokeStyle = '#dc2626'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.roundRect(cx, cy, cellW, cellH, 6); ctx.stroke();
    }} else {{
      rrect(ctx, cx, cy, cellW, cellH, 6, 0xFFFFFF, isRunning ? 1 : 0.7);
      ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.roundRect(cx, cy, cellW, cellH, 6); ctx.stroke();
    }}
    ctx.restore();

    // Scale context into cell
    ctx.save();
    ctx.translate(cx, cy);
    const scaleX = cellW / CW;
    const scaleY = cellH / CH;
    ctx.scale(scaleX, scaleY);

    // Draw workstation back layer
    drawDeskBack(ctx, 0, 8, isRunning); // shifted down 8px from cell top

    // Draw character sprite
    const pose  = isDone ? 'done' : isRunning ? 'working' : 'idle';
    const frame = isRunning ? animFrame : 0;
    const charCvs = makeCharCanvas(agent.variant, pose, frame);
    const charX = (CW - 48) / 2; // centered
    const charY = 66; // character Y in unscaled cell coords
    ctx.drawImage(charCvs, charX, charY, 48, 48);

    // Draw workstation front layer
    drawDeskFront(ctx, 0, 8);
    drawAccessories(ctx, 0, 8, agIdx);

    // Draw name card (above cell, negative Y)
    drawNameCard(ctx, 0, 8, agent, status);

    ctx.restore();

    // Finding count badge
    if (stData.count > 0) {{
      const badgeX = cx + cellW - 22;
      const badgeY = cy + 4;
      rrect(ctx, badgeX, badgeY, 20, 16, 8, 0x4F46E5, 1);
      ctx.font = 'bold 10px sans-serif';
      ctx.fillStyle = '#fff';
      ctx.textAlign = 'center';
      ctx.fillText(stData.count, badgeX+10, badgeY+11);
      ctx.textAlign = 'left';
    }}
  }});
}}

// ═══════════════════════════════════════════════════════
//  MANAGER CARD UPDATE
// ═══════════════════════════════════════════════════════
function updateManagerCard() {{
  const card   = document.getElementById('mgr-card');
  const status = document.getElementById('mgr-status');
  const tags   = document.getElementById('mgr-tags');
  const brief  = document.getElementById('mgr-briefing');
  const sub    = document.getElementById('mgr-sub');

  const mgrState = AGENT_STATES['manager_agent'] || {{}};
  const mgrStatus = mgrState.status || 'idle';

  card.className = '';
  if (mgrStatus === 'running') {{
    card.classList.add('running');
    status.textContent = LANG==='pt' ? '⏳ rodando…' : '⏳ running…';
  }} else if (mgrStatus === 'done' || Object.keys(PLAN).length > 0) {{
    card.classList.add('done');
    status.textContent = LANG==='pt' ? '✅ concluído' : '✅ done';
  }} else {{
    status.textContent = LANG==='pt' ? 'aguardando' : 'waiting';
  }}

  if (LANG === 'pt') {{
    sub.textContent = 'Analisa arquitetura · Decide prioridades · Injeta contexto de foco';
  }}

  // Plan tags
  tags.innerHTML = '';
  if (PLAN.architecture_type) {{
    tags.innerHTML += `<span class="tag tag-arch">${{PLAN.architecture_type}}</span>`;
  }}
  if (PLAN.complexity) {{
    tags.innerHTML += `<span class="tag tag-cplx">${{LANG==='pt'?'complexidade':'complexity'}}: ${{PLAN.complexity}}</span>`;
  }}
  (PLAN.compliance_flags||[]).forEach(f => {{
    tags.innerHTML += `<span class="tag tag-comp">⚑ ${{f}}</span>`;
  }});
  (PLAN.cloud_providers||[]).forEach(c => {{
    tags.innerHTML += `<span class="tag tag-cloud">☁️ ${{c}}</span>`;
  }});

  if (PLAN.manager_briefing) {{
    brief.style.display = 'block';
    brief.textContent = '💬 ' + PLAN.manager_briefing.slice(0, 200) + (PLAN.manager_briefing.length>200?'…':'');
  }}
}}

// ═══════════════════════════════════════════════════════
//  ANIMATION LOOP (for working agents)
// ═══════════════════════════════════════════════════════
function startAnimation() {{
  const hasRunning = Object.values(AGENT_STATES).some(s => s.status === 'running');
  if (hasRunning && !animTimer) {{
    animTimer = setInterval(() => {{
      animFrame = animFrame === 0 ? 1 : 0;
      render();
    }}, 350);
  }} else if (!hasRunning && animTimer) {{
    clearInterval(animTimer);
    animTimer = null;
  }}
}}

// ═══════════════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════════════
window.addEventListener('load', () => {{
  updateManagerCard();
  render();
  startAnimation();
  window.addEventListener('resize', render);
}});
</script>
</body>
</html>
"""


def build_agent_states(log: list[dict]) -> dict:
    """Convert squad log events to agent_states dict for the canvas renderer."""
    states = {}

    # Add manager
    states["manager_agent"] = {"status": "idle", "count": 0}

    for agent_def in AGENT_DEFS[1:]:  # skip manager
        key = agent_def["key"]
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
    """Convert OrchestrationPlanSnapshot to plain dict for JS."""
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
