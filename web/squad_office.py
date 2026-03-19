"""
Squad Office — procedural Canvas renderer for Streamlit.
Clean rewrite: uniform grid, offscreen canvas per cell, correct VW:VH scaling.
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

    # Use %% for literal { } inside the f-string JS block
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#eeebe4;font-family:-apple-system,'Segoe UI',sans-serif}}
#wrap{{width:100%;padding:10px}}
#mgr{{margin-bottom:10px;background:#fff;border:1.5px solid #e5e7eb;border-radius:10px;
  padding:10px 14px;display:flex;align-items:flex-start;gap:10px;font-size:13px;
  transition:border-color .3s,background .3s}}
#mgr.done{{border-color:#16a34a;background:#f0fdf4}}
#mgr.running{{border-color:#6366f1;background:#f5f3ff;
  box-shadow:0 0 0 3px rgba(99,102,241,.12);animation:pulse 1.6s ease-in-out infinite}}
.mic{{font-size:1.25rem;flex-shrink:0;padding-top:2px}}
.minfo{{flex:1;min-width:0}}
.mttl{{font-weight:700;color:#111;font-size:13px}}
.msub{{font-size:11px;color:#9ca3af;margin-top:2px}}
.mst{{font-size:11px;font-weight:700;color:#6b7280;flex-shrink:0}}
#mgr.done .mst{{color:#16a34a}}
#mgr.running .mst{{color:#6366f1}}
#tags{{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}}
.tag{{padding:2px 7px;border-radius:5px;font-size:11px;font-weight:600}}
.ta{{background:#f5f3ff;border:1px solid #ddd6fe;color:#4338ca}}
.tc{{background:#fef2f2;border:1px solid #fecaca;color:#991b1b}}
.tl{{background:#f0f9ff;border:1px solid #bae6fd;color:#0369a1}}
.tx{{background:#f0fdf4;border:1px solid #bbf7d0;color:#166534}}
#brief{{font-size:11px;color:#374151;margin-top:7px;font-style:italic;display:none}}
canvas{{display:block;width:100%;image-rendering:pixelated;image-rendering:crisp-edges}}
@keyframes pulse{{0%,100%{{box-shadow:0 0 0 3px rgba(99,102,241,.12)}}50%{{box-shadow:0 0 0 6px rgba(99,102,241,.22)}}}}
</style></head><body>
<div id="wrap">
  <div id="mgr">
    <div class="mic">🎯</div>
    <div class="minfo">
      <div class="mttl">Agent Manager <span style="font-size:10px;font-weight:400;color:#9ca3af">— Phase 0</span></div>
      <div class="msub" id="sub">Analyzes architecture · Decides agent priorities · Injects focus context</div>
      <div id="tags"></div>
      <div id="brief"></div>
    </div>
    <div class="mst" id="mst">waiting</div>
  </div>
  <canvas id="cv"></canvas>
</div>
<script>
const STATES={states_json};
const PLAN={plan_json};
const AGENTS={agents_json};
const LANG={lang_js};

// Palette
const P={{
  sL:0xFFD5A8,sLS:0xD4A883,sM:0xC68642,sMS:0xB48854,sD:0x8D5524,sDS:0x6B4320,
  hBk:0x2C2018,hBkL:0x3A3028,hBkD:0x1A1008,
  hBr:0x6B4226,hBrL:0x8A6A4A,hBrD:0x4A2A0A,
  hBl:0xD4A017,hBlL:0xE4B850,hBlD:0xB48830,
  hRd:0xA0522D,hRdL:0xC05030,hRdD:0x903010,
  sBlue:0x4A7AB0,sBluL:0x5A8AC0,sBluD:0x3A6898,
  sGrn:0x4A8A4A,sGrnL:0x5A9A5A,sGrnD:0x3A7A3A,
  sRed:0xA04848,sRedL:0xB85858,sRedD:0x983838,
  sWht:0xE0D8CC,sWhtL:0xF0E8DC,sWhtD:0xD0C8BC,
  sPrp:0x7A58A0,sPrpL:0x8A68B0,sPrpD:0x6A4890,
  sTel:0x3A8888,sTelL:0x4A9898,sTelD:0x2A7878,
  pt:0x3A3A4A,ptD:0x2A2A3A,sh:0x2A2018,shL:0x3A3028,
  col:0xF0F0F0,bltB:0x8A8A6A,
  dT:0xD4B888,dL:0xE0CCAA,dD:0xC4AF8C,dE:0xB09870,
  mF:0x1E1E2A,mS:0x0A0A1A,mOn:0x48D1CC,mSt:0x4A4A5A,
  chB:0x2A2A3A,chS:0x323244,chA:0x282838,
  fl:0xEEEBE4,flL:0xE0DDD6,
  mugW:0xE0E0E0,mugR:0xCCCCCC,
  pY:0xFFEE55,pP:0xFF8866,
  bkR:0xCC4444,bkB:0x4466AA,bkG:0x44AA44,
  plG:0x44AA44,plD:0x2A8A2A,plP:0xCC6644,
  wB:0x88BBDD,wC:0x4488AA,
  card:0x14141C,
  dI:0xAAAACC,dRun:0x60B0FF,dDone:0x60F080,dErr:0xFF6060,
}};

// Character variants [hair, hairL, hairD, skin, skinS, shirt, shirtL, shirtD]
const VAR=[
  [P.hBk,P.hBkL,P.hBkD,P.sM,P.sMS,P.sBlue,P.sBluL,P.sBluD],
  [P.hBk,P.hBkL,P.hBkD,P.sL,P.sLS,P.sRed, P.sRedL,P.sRedD],
  [P.hBr,P.hBrL,P.hBrD,P.sM,P.sMS,P.sGrn, P.sGrnL,P.sGrnD],
  [P.hBl,P.hBlL,P.hBlD,P.sL,P.sLS,P.sWht, P.sWhtL,P.sWhtD],
  [P.hRd,P.hRdL,P.hRdD,P.sD,P.sDS,P.sPrp, P.sPrpL,P.sPrpD],
  [P.hBr,P.hBrL,P.hBrD,P.sL,P.sLS,P.sTel, P.sTelL,P.sTelD],
];

function col(n){{return '#'+n.toString(16).padStart(6,'0')}}
function px(c,x,y,n){{c.fillStyle=col(n);c.fillRect(x,y,1,1)}}
function hs(c,x1,x2,y,n){{c.fillStyle=col(n);c.fillRect(x1,y,x2-x1+1,1)}}
function bx(c,x,y,w,h,n){{c.fillStyle=col(n);c.fillRect(x,y,w,h)}}
function rr(c,x,y,w,h,r,n,a){{
  c.save();if(a!==undefined)c.globalAlpha=a;
  c.fillStyle=col(n);c.beginPath();c.roundRect(x,y,w,h,r);c.fill();c.restore();
}}

// 48x48 character
function mkChar(vi,pose,frame){{
  const [hair,hairL,hairD,skin,skinS,shirt,shirtL,shirtD]=VAR[vi];
  const cv=document.createElement('canvas');cv.width=cv.height=48;
  const c=cv.getContext('2d');c.imageSmoothingEnabled=false;
  // hair
  hs(c,16,30,2,hair);hs(c,15,31,3,hair);hs(c,14,32,4,hair);hs(c,14,32,5,hair);
  [17,22,28].forEach(x=>px(c,x,3,hairL));[16,25,30].forEach(x=>px(c,x,4,hairL));
  px(c,14,5,hairD);px(c,32,5,hairD);px(c,15,4,hairD);px(c,31,4,hairD);
  px(c,14,6,hair);px(c,14,7,hair);px(c,32,6,hair);px(c,32,7,hair);
  // face
  [6,7,8,9].forEach(y=>hs(c,15,31,y,skin));
  [10,11].forEach(y=>hs(c,16,30,y,skin));
  hs(c,17,29,12,skin);hs(c,18,28,13,skin);hs(c,19,27,14,skin);
  [16,17].forEach(i=>{{px(c,i,11,skinS);px(c,i,12,skinS)}});
  [29,30].forEach(i=>{{px(c,i,11,skinS);px(c,i,12,skinS)}});
  hs(c,18,20,7,hairD);hs(c,26,28,7,hairD);
  const ey=pose==='working'?10:9;
  px(c,18,9,0xF0EDE8);px(c,19,ey,0x2A2018);px(c,20,9,0xF0EDE8);
  px(c,26,9,0xF0EDE8);px(c,27,ey,0x2A2018);px(c,28,9,0xF0EDE8);
  px(c,23,11,skinS);px(c,23,12,skinS);
  if(pose==='done'){{px(c,20,13,0x2A2018);px(c,26,13,0x2A2018);hs(c,21,25,14,0x2A2018)}}
  else hs(c,21,25,14,0x2A2018);
  px(c,14,8,skin);px(c,14,9,skinS);px(c,32,8,skin);px(c,32,9,skinS);
  // neck/collar/shirt
  hs(c,20,26,15,skin);hs(c,21,25,16,skin);px(c,20,15,skinS);px(c,26,15,skinS);
  hs(c,17,29,17,P.col);
  for(let y=18;y<=28;y++)
    for(let i=13;i<=33;i++)
      px(c,i,y,i<=15?shirtD:i>=31?shirtD:(i>=22&&i<=24)?shirtL:shirt);
  // belt
  hs(c,13,33,29,P.ptD);[22,23,24].forEach(x=>px(c,x,29,P.bltB));
  // pants
  for(let y=30;y<=39;y++){{
    for(let i=14;i<=21;i++)px(c,i,y,i<=15?P.ptD:P.pt);
    for(let i=25;i<=32;i++)px(c,i,y,i>=31?P.ptD:P.pt);
    px(c,21,y,P.ptD);px(c,25,y,P.ptD);
  }}
  // shoes
  for(let i=13;i<=22;i++){{px(c,i,40,P.sh);px(c,i,41,P.sh);px(c,i,42,i<=14?P.shL:P.sh)}}
  hs(c,13,22,43,P.shL);
  for(let i=24;i<=33;i++){{px(c,i,40,P.sh);px(c,i,41,P.sh);px(c,i,42,i>=32?P.shL:P.sh)}}
  hs(c,24,33,43,P.shL);
  // arms
  if(pose==='done'){{
    [18].forEach(y=>{{px(c,11,y,shirt);px(c,12,y,shirt);px(c,34,y,shirt);px(c,35,y,shirt)}});
    [[10,17],[9,16],[8,13],[7,11]].forEach(([x,y])=>{{px(c,x,y,skin);px(c,47-x+1,y,skin)}});
  }}else if(pose==='working'){{
    [18,19,20].forEach(y=>{{px(c,11,y,shirt);px(c,12,y,shirt);px(c,34,y,shirt);px(c,35,y,shirt)}});
    const ys=frame===0?[21,22,23,24]:[21,22,23];
    ys.forEach(y=>{{px(c,10,y,skin);px(c,11,y,skin);px(c,35,y,skin);px(c,36,y,skin)}});
  }}else{{
    [18,19,20,21,22].forEach(y=>{{px(c,11,y,shirt);px(c,12,y,shirt);px(c,34,y,shirt);px(c,35,y,shirt)}});
    px(c,12,19,shirtD);px(c,34,19,shirtD);
    [23,24,25,26,27].forEach(y=>{{px(c,10,y,skin);px(c,11,y,skin);px(c,35,y,skin);px(c,36,y,skin)}});
    [8,9,10].forEach(x=>px(c,x,28,skin));[36,37,38].forEach(x=>px(c,x,28,skin));
  }}
  return cv;
}}

// Virtual workstation dimensions (all desk drawing uses these coords)
const VW=128,VH=160;
// Y zones:
//  8-60:  desk top + monitor
//  60-68: desk front + keyboard
//  68-90: chair back
//  90-138: character (48px)
// 138-160: casters

function drawDesk(c,working){{
  // Chair back
  bx(c,28,68,72,5,P.chB);bx(c,29,68,70,2,P.chA);
  bx(c,24,73,10,14,P.chB);bx(c,25,73,8,2,P.chA);
  bx(c,94,73,10,14,P.chB);bx(c,95,73,8,2,P.chA);
  bx(c,32,87,64,18,P.chB);bx(c,34,89,60,14,P.chS);
  // Desk surface
  bx(c,4,8,120,52,P.dT);
  for(let r=0;r<13;r++)bx(c,4,8+r*4,120,3,r%3===0?P.dL:r%3===1?P.dT:P.dD);
  bx(c,4,8,2,52,P.dD);bx(c,122,8,2,52,P.dD);
  // Monitor
  c.fillStyle=col(0x1A1A22);c.beginPath();c.roundRect(20,10,88,40,3);c.fill();
  c.fillStyle=col(P.mF);c.beginPath();c.roundRect(21,11,86,38,2);c.fill();
  c.fillStyle=col(working?P.mOn:P.mS);c.globalAlpha=working?.92:1;
  c.beginPath();c.roundRect(23,13,82,32,1);c.fill();c.globalAlpha=1;
  if(working){{
    c.globalAlpha=0.28;c.fillStyle='#fff';
    for(let i=0;i<7;i++)bx(c,25,15+i*4,20+((i*11)%44),1,0xFFFFFF);
    c.globalAlpha=0.07;c.fillStyle=col(P.mOn);
    c.beginPath();c.roundRect(14,6,100,52,6);c.fill();c.globalAlpha=1;
  }}
  c.globalAlpha=0.08;c.fillStyle='#fff';bx(c,23,13,82,2,0xFFFFFF);c.globalAlpha=1;
  bx(c,63,11,2,1,0x222222); // webcam
  bx(c,23,45,82,4,P.mF);    // chin
  bx(c,56,49,16,8,P.mSt);bx(c,58,50,12,6,0x5A5A6A); // stand neck
  c.fillStyle=col(P.mSt);c.beginPath();c.roundRect(40,57,48,5,2);c.fill();
  c.fillStyle='#5a5a6a';c.beginPath();c.roundRect(42,57,44,3,1);c.fill();
  // Desk front
  bx(c,4,60,120,8,P.dE);
  c.globalAlpha=0.18;bx(c,4,67,120,2,0x000000);c.globalAlpha=1;
  // Keyboard
  c.fillStyle=col(0x3A3A42);c.beginPath();c.roundRect(26,61,60,8,1);c.fill();
  bx(c,27,61,58,1,0x4A4A52);
  for(let r=0;r<3;r++)for(let k=0;k<11;k++)bx(c,28+k*5,62+r*2,4,1,0x5A5A5A);
  bx(c,36,67,28,1,0x5A5A5A);
  // Mouse + pad
  bx(c,90,59,24,18,0x2A2A3A);
  c.fillStyle=col(0x3A3A42);c.beginPath();c.roundRect(93,61,16,14,3);c.fill();
  bx(c,94,61,14,3,0x4A4A52);bx(c,100,61,2,4,0x5A5A62);bx(c,93,61,1,14,0x2A2A32);
  // Accessories
  const acc=[drawMug,drawPlant,drawPostIts,drawBooks,drawWater];
  const seed=VAR.indexOf(VAR[0]); // will be passed as agIdx below
  // (called separately)
  // Casters
  bx(c,58,142,12,6,P.mSt);
  for(let i=0;i<5;i++){{
    const a=i/5*Math.PI*2-Math.PI/2;
    const wx=64+Math.round(Math.cos(a)*18),wy=152+Math.round(Math.sin(a)*7);
    bx(c,wx-3,wy-1,6,3,P.mSt);bx(c,wx-1,wy+1,2,2,0x5A5A6A);
  }}
}}

function drawAcc(c,agIdx){{
  const pool=[drawMug,drawPlant,drawPostIts,drawBooks,drawWater];
  const s=agIdx*7+3;
  pool[s%pool.length](c,6,48);
  const i2=(s+2)%pool.length;
  if(i2!==s%pool.length)pool[i2](c,104,48);
}}
function drawMug(c,x,y){{
  bx(c,x,y+2,9,8,P.mugW);bx(c,x,y+2,9,2,P.mugR);bx(c,x+9,y+4,3,4,P.mugR);
  c.globalAlpha=.3;bx(c,x+2,y,1,1,0xFFFFFF);c.globalAlpha=1;
}}
function drawPlant(c,x,y){{
  bx(c,x+1,y+8,8,6,P.plP);bx(c,x,y+6,10,3,P.plP);
  c.fillStyle=col(P.plG);c.beginPath();c.arc(x+5,y+4,3,0,Math.PI*2);c.fill();
  c.fillStyle=col(P.plD);c.beginPath();c.arc(x+3,y+2,2,0,Math.PI*2);c.fill();
  c.fillStyle=col(P.plG);c.beginPath();c.arc(x+7,y+2,2,0,Math.PI*2);c.fill();
}}
function drawPostIts(c,x,y){{
  bx(c,x,y,7,7,P.pP);bx(c,x+3,y+2,8,8,P.pY);bx(c,x+3,y+2,8,2,0xEEDD44);
  c.globalAlpha=.12;bx(c,x+4,y+5,5,1,0);bx(c,x+4,y+7,4,1,0);c.globalAlpha=1;
}}
function drawBooks(c,x,y){{
  bx(c,x,y+4,10,3,P.bkR);bx(c,x,y+2,10,3,P.bkB);bx(c,x+1,y,8,3,P.bkG);
  c.globalAlpha=.15;bx(c,x,y+4,1,3,0);bx(c,x,y+2,1,3,0);c.globalAlpha=1;
}}
function drawWater(c,x,y){{
  bx(c,x+1,y,4,2,P.wC);bx(c,x,y+2,6,10,P.wB);
  c.globalAlpha=.45;bx(c,x+1,y+3,4,4,0xAADDEE);c.globalAlpha=1;
}}

// Name card — screen-pixel space
function drawCard(ctx,cx,cy,cw,agent,status){{
  const nm=LANG==='pt'?agent.nm_pt:agent.nm_en;
  const cW=Math.max(78,nm.length*7+44),cH=20;
  const cX=cx+(cw-cW)/2,cY=cy-cH-6;
  rr(ctx,cX+1,cY+2,cW,cH,7,0x000000,.18);
  rr(ctx,cX,cY,cW,cH,7,P.card,.93);
  ctx.save();ctx.globalAlpha=.93;ctx.fillStyle=col(P.card);
  const tx=cx+cw/2;
  ctx.beginPath();ctx.moveTo(tx-4,cY+cH);ctx.lineTo(tx,cY+cH+5);ctx.lineTo(tx+4,cY+cH);ctx.closePath();ctx.fill();
  ctx.restore();
  const dc=status==='running'?P.dRun:status==='done'?P.dDone:status==='error'?P.dErr:P.dI;
  const dx=cX+cW-12,dy=cY+cH/2;
  if(status==='running'||status==='done'){{ctx.save();ctx.globalAlpha=.2;ctx.fillStyle=col(dc);ctx.beginPath();ctx.arc(dx,dy,7,0,Math.PI*2);ctx.fill();ctx.restore()}}
  ctx.fillStyle=col(dc);ctx.beginPath();ctx.arc(dx,dy,3.5,0,Math.PI*2);ctx.fill();
  ctx.font='11px serif';ctx.fillText(agent.ic,cX+5,cY+14);
  ctx.font='600 11px -apple-system,sans-serif';ctx.fillStyle='#fff';ctx.fillText(nm,cX+20,cY+14);
}}

// Floor grid
function drawFloor(ctx,W,H){{
  ctx.fillStyle=col(P.fl);ctx.fillRect(0,0,W,H);
  ctx.strokeStyle=col(P.flL);ctx.lineWidth=0.5;
  for(let x=0;x<W;x+=32){{ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke()}}
  for(let y=0;y<H;y+=32){{ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke()}}
}}

// Grid layout: [startCol, endCol, row, agentIdx]
const LAYOUT=[
  [1,2,0,0],[0,0,1,1],[1,1,1,2],[2,2,1,3],[3,3,1,4],[1,2,2,5]
];
const NCOLS=4,PAD=12,GAP=8,CTOP=32;

let aF=0,aT=null;

function render(){{
  const cv=document.getElementById('cv');
  if(!cv)return;
  const aw=cv.parentElement.clientWidth||760;
  const cW=Math.floor((aw-PAD*2-GAP*(NCOLS-1))/NCOLS);
  const cH=Math.round(cW*VH/VW);
  const TW=NCOLS*cW+(NCOLS-1)*GAP+PAD*2;
  const TH=3*cH+2*GAP+PAD*2+CTOP;
  cv.width=TW;cv.height=TH;cv.style.width=TW+'px';cv.style.height=TH+'px';
  const ctx=cv.getContext('2d');ctx.imageSmoothingEnabled=false;
  ctx.clearRect(0,0,TW,TH);drawFloor(ctx,TW,TH);

  LAYOUT.forEach(([sc,ec,row,ai])=>{{
    const agent=AGENTS[ai];
    const sd=STATES[agent.key]||{{status:'idle',count:0}};
    const s=sd.status||'idle';
    const run=s==='running',done=s==='done',err=s==='error';
    const span=ec-sc+1;
    const cx=PAD+sc*(cW+GAP),cy=PAD+CTOP+row*(cH+GAP);
    const cw=span*cW+(span-1)*GAP,ch=cH;

    // Cell bg
    const bg=run?0xF5F3FF:done?0xF0FDF4:err?0xFEF2F2:0xFFFFFF;
    const bga=run||done||err?.93:.8;
    const bc=run?'#6366f1':done?'#16a34a':err?'#dc2626':'#e5e7eb';
    rr(ctx,cx,cy,cw,ch,8,bg,bga);
    ctx.strokeStyle=bc;ctx.lineWidth=run||done||err?1.5:1;
    ctx.beginPath();ctx.roundRect(cx,cy,cw,ch,8);ctx.stroke();

    // Render workstation to offscreen canvas at VW×VH, then scale-blit
    const off=document.createElement('canvas');off.width=VW;off.height=VH;
    const oc=off.getContext('2d');oc.imageSmoothingEnabled=false;
    drawDesk(oc,run);
    drawAcc(oc,ai);
    // Character at y=35% of VH
    const charY=Math.round(VH*.34),charX=(VW-48)/2;
    const pose=done?'done':run?'working':'idle';
    oc.drawImage(mkChar(agent.variant,pose,aF),charX,charY,48,48);
    // Blit to screen
    ctx.drawImage(off,cx,cy,cw,ch);

    // Name card (screen space, no clip)
    drawCard(ctx,cx,cy,cw,agent,s);

    // Badge
    if(sd.count>0){{
      const bx2=cx+cw-22,by2=cy+5;
      rr(ctx,bx2,by2,18,15,7,0x4F46E5,1);
      ctx.font='bold 9px sans-serif';ctx.fillStyle='#fff';
      ctx.textAlign='center';ctx.fillText(sd.count,bx2+9,by2+10);ctx.textAlign='left';
    }}
  }});
}}

// Manager card
function updateMgr(){{
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
  if(PLAN.manager_briefing){{brief.style.display='block';brief.textContent='💬 '+PLAN.manager_briefing.slice(0,200)}}
}}

function startAnim(){{
  const r=Object.values(STATES).some(s=>s.status==='running');
  if(r&&!aT){{aT=setInterval(()=>{{aF=aF?0:1;render()}},380)}}
  else if(!r&&aT){{clearInterval(aT);aT=null}}
}}

window.addEventListener('load',()=>{{updateMgr();render();startAnim();window.addEventListener('resize',render)}});
</script></body></html>"""
    return html


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
