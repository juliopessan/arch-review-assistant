"""
Squad Office v3 — Pixel Agents-inspired Canvas renderer.
Fixes: character placement, manager walk-between-desks, 9 agents.
"""
from __future__ import annotations
import json

AGENT_DEFS = [
    {"key": "manager_agent",         "ic": "🎯", "nm_en": "Manager",         "nm_pt": "Gerente",          "variant": 0},
    {"key": "security_agent",        "ic": "🔐", "nm_en": "Security",        "nm_pt": "Segurança",        "variant": 1},
    {"key": "reliability_agent",     "ic": "🛡️", "nm_en": "Reliability",     "nm_pt": "Confiabilidade",   "variant": 2},
    {"key": "cost_agent",            "ic": "💰", "nm_en": "Cost",             "nm_pt": "Custo",            "variant": 3},
    {"key": "observability_agent",   "ic": "📡", "nm_en": "Observability",   "nm_pt": "Observabilidade",  "variant": 4},
    {"key": "scalability_agent",     "ic": "📈", "nm_en": "Scalability",     "nm_pt": "Escalabilidade",   "variant": 5},
    {"key": "performance_agent",     "ic": "⚡", "nm_en": "Performance",     "nm_pt": "Performance",      "variant": 0},
    {"key": "maintainability_agent", "ic": "🔧", "nm_en": "Maintainability", "nm_pt": "Manutenibilidade", "variant": 2},
    {"key": "synthesizer_agent",     "ic": "🧠", "nm_en": "Synthesizer",     "nm_pt": "Sintetizador",     "variant": 4},
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
body{{background:#1a1628;font-family:-apple-system,'Segoe UI',sans-serif;overflow:hidden}}
#wrap{{width:100%;display:flex;flex-direction:column}}

/* Manager card */
#mgr{{background:#14102a;border:1px solid #3d3560;border-radius:8px;
  padding:10px 14px;display:flex;align-items:flex-start;gap:10px;font-size:12px;
  margin:8px 8px 0;transition:all .3s}}
#mgr.done{{border-color:#22c55e;background:#0d2218}}
#mgr.running{{border-color:#818cf8;background:#1a1838;
  box-shadow:0 0 14px rgba(129,140,248,.3);animation:glow 2s ease-in-out infinite}}
.mic{{font-size:1.1rem;flex-shrink:0}}
.minfo{{flex:1;min-width:0}}
.mttl{{font-weight:700;color:#e2e8f0;font-size:12px}}
.msub{{font-size:10px;color:#64748b;margin-top:1px}}
.mst{{font-size:10px;font-weight:700;color:#475569;flex-shrink:0}}
#mgr.done .mst{{color:#22c55e}} #mgr.running .mst{{color:#818cf8}}
#tags{{display:flex;gap:4px;flex-wrap:wrap;margin-top:5px}}
.tag{{padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600}}
.ta{{background:#1e1b4b;color:#a5b4fc}} .tc{{background:#2d0f0f;color:#fca5a5}}
.tl{{background:#082a3b;color:#7dd3fc}} .tx{{background:#052e1a;color:#86efac}}
#brief{{font-size:10px;color:#94a3b8;margin-top:5px;font-style:italic;display:none}}

canvas{{display:block;width:100%;image-rendering:pixelated;image-rendering:crisp-edges}}
@keyframes glow{{0%,100%{{box-shadow:0 0 8px rgba(129,140,248,.2)}}50%{{box-shadow:0 0 22px rgba(129,140,248,.45)}}}}
</style></head><body>
<div id="wrap">
  <div id="mgr">
    <div class="mic">🎯</div>
    <div class="minfo">
      <div class="mttl">Agent Manager <span style="font-size:9px;font-weight:400;color:#475569">— Phase 0</span></div>
      <div class="msub" id="sub">Analyzes architecture · Sets priorities · Injects focus</div>
      <div id="tags"></div><div id="brief"></div>
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

// ── Palette ───────────────────────────────────────────────────────────────────
const P={{
  flA:0x1e1a2e, flB:0x241f38, flLine:0x14102a,
  wall:0x100d20, wallT:0x1a1628,
  desk:0x3d3560, deskT:0x4a4070, deskE:0x2a2438,
  dW:0x5a4a30, dWL:0x6a5a3a, dWD:0x4a3a22,
  mF:0x1a1628, mS:0x08080f, mOn:0x00d4ff, mSt:0x2a2438,
  chB:0x1a1628, chS:0x201d3a, chA:0x242038,
  sL:0xffcba4, sLS:0xe8a882, sM:0xc68642, sMS:0xa86a2a, sD:0x8d5524, sDS:0x6b3a14,
  hBk:0x1a1008, hBr:0x4a2a0a, hBl:0xc89010, hRd:0x902010,
  tBlu:0x3b82f6, tGrn:0x22c55e, tRed:0xef4444, tPrp:0xa855f7, tAmb:0xf59e0b, tTel:0x14b8a6,
  pt:0x1e293b, sh:0x0f172a, shL:0x1e293b,
  card:0x0f0a1e,
  dI:0x475569, dR:0x60a5fa, dD:0x4ade80, dE:0xf87171, dW2:0xfbbf24,
  spark:0xffd700,
}};

const VAR=[
  [P.sM,P.sMS,P.hBk,P.tBlu], [P.sL,P.sLS,P.hBk,P.tRed],
  [P.sM,P.sMS,P.hBr,P.tGrn], [P.sL,P.sLS,P.hBl,P.tAmb],
  [P.sD,P.sDS,P.hRd,P.tPrp], [P.sL,P.sLS,P.hBr,P.tTel],
];

function hx(n){{return '#'+n.toString(16).padStart(6,'0')}}
function px(c,x,y,n){{c.fillStyle=hx(n);c.fillRect(x,y,1,1)}}
function hs(c,x1,x2,y,n){{c.fillStyle=hx(n);c.fillRect(x1,y,x2-x1+1,1)}}
function bx(c,x,y,w,h,n){{c.fillStyle=hx(n);c.fillRect(x,y,w,h)}}
function rr(c,x,y,w,h,r,n,a){{
  c.save();if(a!==undefined)c.globalAlpha=a;
  c.fillStyle=hx(n);c.beginPath();c.roundRect(x,y,w,h,r);c.fill();c.restore();
}}

// ── 16×24 sprite ─────────────────────────────────────────────────────────────
function mkSprite(vi,pose,frame){{
  const [skin,skinS,hair,shirt]=VAR[vi%VAR.length];
  const cv=document.createElement('canvas');cv.width=16;cv.height=24;
  const c=cv.getContext('2d');c.imageSmoothingEnabled=false;
  // hair
  hs(c,5,10,0,hair);hs(c,4,11,1,hair);hs(c,4,11,2,hair);
  [6,7,8,9].forEach(y=>hs(c,4,11,y,skin));
  [10,11].forEach(y=>hs(c,5,10,y,skin));
  hs(c,6,9,12,skin);
  px(c,4,5,skinS);px(c,11,5,skinS);
  hs(c,5,6,2,hair);hs(c,9,10,2,hair);
  const ey=pose==='working'?4:3;
  px(c,5,ey,0xf0ede8);px(c,6,ey,0x1a1008);px(c,9,ey,0xf0ede8);px(c,10,ey,0x1a1008);
  px(c,7,5,skinS);
  if(pose==='done'){{px(c,5,6,0x1a1008);px(c,9,6,0x1a1008);hs(c,6,8,7,0x1a1008)}}
  else hs(c,6,9,6,0x1a1008);
  px(c,4,8,skin);px(c,11,8,skin);
  // body
  hs(c,6,9,8,0xf0f0f0);
  for(let y=9;y<=15;y++)for(let i=3;i<=12;i++)
    px(c,i,y,i<=4||i>=11?0x1e293b:(i===7||i===8)?shirt+0x101010:shirt);
  hs(c,3,12,16,0x1e293b);px(c,7,16,0x8a8a5a);px(c,8,16,0x8a8a5a);
  // legs
  for(let y=17;y<=20;y++){{hs(c,4,6,y,P.pt);hs(c,9,11,y,P.pt);}}
  // arms by pose
  if(pose==='done'){{
    px(c,3,9,shirt);px(c,12,9,shirt);
    px(c,2,8,skin);px(c,1,7,skin);px(c,13,8,skin);px(c,14,7,skin);
  }}else if(pose==='working'){{
    px(c,3,10,shirt);px(c,12,10,shirt);
    const off=frame%2===0?0:1;
    px(c,2,11+off,skin);px(c,13,11-off,skin);
  }}else if(pose==='walking'){{
    const sw=Math.round(Math.sin(frame/3*Math.PI));
    px(c,3,10+sw,shirt);px(c,12,10-sw,shirt);
    px(c,2,12+sw,skin);px(c,13,12-sw,skin);
  }}else{{
    px(c,3,10,shirt);px(c,12,10,shirt);
    px(c,3,11,skin);px(c,12,11,skin);
  }}
  // shoes
  bx(c,3,21,4,2,P.sh);bx(c,9,21,4,2,P.sh);
  hs(c,3,6,22,P.shL);hs(c,9,12,22,P.shL);
  return cv;
}}

// ── Desk (drawn at pixel coords, fixed size) ──────────────────────────────────
const DW=96, DH=64; // desk pixel dimensions

function drawDesk(ctx,x,y,active,agIdx){{
  // surface
  bx(ctx,x,y,DW,DH*0.5,P.dW);
  for(let r=0;r<6;r++)bx(ctx,x,y+r*5,DW,4,r%3===0?P.dWL:r%3===1?P.dW:P.dWD);
  bx(ctx,x,y,2,DH*0.5,P.dWD);bx(ctx,x+DW-2,y,2,DH*0.5,P.dWD);
  // monitor
  ctx.fillStyle=hx(0x141020);ctx.beginPath();ctx.roundRect(x+DW*0.2,y-20,DW*0.6,18,2);ctx.fill();
  ctx.fillStyle=hx(P.mF);ctx.beginPath();ctx.roundRect(x+DW*0.21,y-19,DW*0.58,16,1);ctx.fill();
  const sc=active?P.mOn:P.mS;
  ctx.fillStyle=hx(sc);ctx.beginPath();ctx.roundRect(x+DW*0.23,y-18,DW*0.54,13,1);ctx.fill();
  if(active){{
    ctx.globalAlpha=0.28;ctx.fillStyle='#fff';
    for(let i=0;i<4;i++)ctx.fillRect(x+DW*0.25,y-16+i*3,8+((i*9)%20),1);
    ctx.globalAlpha=0.07;ctx.fillStyle=hx(P.mOn);
    ctx.beginPath();ctx.roundRect(x+DW*0.12,y-26,DW*0.76,32,4);ctx.fill();
    ctx.globalAlpha=1;
  }}
  ctx.globalAlpha=0.08;ctx.fillStyle='#fff';ctx.fillRect(x+DW*0.23,y-18,DW*0.54,2);ctx.globalAlpha=1;
  // stand
  bx(ctx,x+DW*0.45,y-2,DW*0.1,4,P.mSt);
  ctx.fillStyle=hx(P.mSt);ctx.beginPath();ctx.roundRect(x+DW*0.32,y+2,DW*0.36,3,1);ctx.fill();
  // desk front
  bx(ctx,x,y+DH*0.5,DW,5,P.dWD);
  // keyboard
  ctx.fillStyle=hx(0x2a2438);ctx.beginPath();ctx.roundRect(x+DW*0.22,y+DH*0.5+1,DW*0.4,6,1);ctx.fill();
  ctx.globalAlpha=0.5;ctx.fillStyle='#555';
  for(let r=0;r<2;r++)for(let k=0;k<7;k++)ctx.fillRect(x+DW*0.23+k*5,y+DH*0.5+2+r*2,4,1);
  ctx.globalAlpha=1;
  // mouse
  ctx.fillStyle=hx(0x2a2438);ctx.beginPath();ctx.roundRect(x+DW*0.7,y+DH*0.5,8,11,3);ctx.fill();
  bx(ctx,x+DW*0.7,y+DH*0.5,8,3,0x3a3448);
  // chair back (behind char)
  bx(ctx,x+DW*0.2,y+DH*0.6,DW*0.6,5,P.chB);
  bx(ctx,x+DW*0.15,y+DH*0.72,DW*0.7,3,P.chB);
  bx(ctx,x+DW*0.15,y+DH*0.6,6,14,P.chA);
  bx(ctx,x+DW*0.85-6,y+DH*0.6,6,14,P.chA);
  // accessory
  const s=(agIdx*7+3)%5;
  if(s===0){{bx(ctx,x+6,y+DH*0.45-8,7,8,0xd0d0d0);bx(ctx,x+13,y+DH*0.45-5,2,4,0xaaa);ctx.globalAlpha=.3;bx(ctx,x+8,y+DH*0.45-10,1,2,0xffffff);ctx.globalAlpha=1;}}
  else if(s===1){{bx(ctx,x+6,y+DH*0.45-5,8,5,0x8b4513);ctx.fillStyle='#228b22';ctx.beginPath();ctx.arc(x+10,y+DH*0.45-8,4,0,Math.PI*2);ctx.fill();}}
  else if(s===2){{bx(ctx,x+6,y+DH*0.45-8,8,8,0xffee55);bx(ctx,x+4,y+DH*0.45-6,6,6,0xff8866);}}
  else if(s===3){{[0x4466aa,0xcc4444,0x44aa44].forEach((col,i)=>{{ctx.fillStyle=hx(col);ctx.fillRect(x+5+i*4,y+DH*0.45-9,3,9);}});}}
  else{{bx(ctx,x+6,y+DH*0.45-11,2,2,0x4488aa);ctx.fillStyle='#88bbdd';ctx.beginPath();ctx.roundRect(x+5,y+DH*0.45-9,4,9,1);ctx.fill();}}
}}

// ── Speech bubble ────────────────────────────────────────────────────────────
function drawBubble(ctx,x,y,text,color){{
  const w=Math.max(32,text.length*5+14),h=16;
  const bx2=x-w/2,by2=y-h-6;
  rr(ctx,bx2+1,by2+1,w,h,5,0x000000,0.3);
  rr(ctx,bx2,by2,w,h,5,color,0.95);
  ctx.fillStyle=hx(color);ctx.globalAlpha=0.95;
  ctx.beginPath();ctx.moveTo(x-3,by2+h);ctx.lineTo(x,by2+h+4);ctx.lineTo(x+3,by2+h);ctx.closePath();ctx.fill();
  ctx.globalAlpha=1;
  ctx.font='bold 8px monospace';ctx.fillStyle='#fff';ctx.textAlign='center';ctx.fillText(text,x,by2+11);ctx.textAlign='left';
}}

// ── Name card ────────────────────────────────────────────────────────────────
function drawCard(ctx,cx,cy,cw,agent,status,count){{
  const nm=LANG==='pt'?agent.nm_pt:agent.nm_en;
  const cW=Math.max(70,nm.length*6+42),cH=20;
  const cX=cx+(cw-cW)/2,cY=cy-cH-5;
  rr(ctx,cX+1,cY+2,cW,cH,6,0,0.2);
  rr(ctx,cX,cY,cW,cH,6,P.card,0.93);
  ctx.save();ctx.globalAlpha=0.93;ctx.fillStyle=hx(P.card);
  const tx=cx+cw/2;
  ctx.beginPath();ctx.moveTo(tx-3,cY+cH);ctx.lineTo(tx,cY+cH+4);ctx.lineTo(tx+3,cY+cH);ctx.closePath();ctx.fill();ctx.restore();
  const dc=status==='running'?P.dR:status==='done'?P.dD:status==='error'?P.dE:P.dI;
  const dx=cX+cW-11,dy=cY+cH/2;
  if(status==='running'||status==='done'){{ctx.save();ctx.globalAlpha=.18;ctx.fillStyle=hx(dc);ctx.beginPath();ctx.arc(dx,dy,7,0,Math.PI*2);ctx.fill();ctx.restore();}}
  ctx.fillStyle=hx(dc);ctx.beginPath();ctx.arc(dx,dy,3,0,Math.PI*2);ctx.fill();
  if(count>0){{rr(ctx,cX+cW-26,cY+2,16,12,4,0x4f46e5,1);ctx.font='bold 8px sans-serif';ctx.fillStyle='#fff';ctx.textAlign='center';ctx.fillText(count,cX+cW-18,cY+11);ctx.textAlign='left';}}
  ctx.font='10px serif';ctx.fillText(agent.ic,cX+4,cY+13);
  ctx.font='600 9px -apple-system,sans-serif';ctx.fillStyle='#e2e8f0';ctx.fillText(nm,cX+18,cY+13);
}}

// ── Sparkles ──────────────────────────────────────────────────────────────────
function drawSparkles(ctx,cx,cy,t){{
  for(let i=0;i<6;i++){{
    const a=i/6*Math.PI*2+t*0.04,r=16+Math.sin(t*0.08+i)*5;
    const alpha=0.5+Math.sin(t*0.1+i)*0.4;
    ctx.save();ctx.globalAlpha=alpha;ctx.fillStyle=hx(i%2?P.spark:P.dD);
    ctx.fillRect(Math.round(cx+Math.cos(a)*r)-1,Math.round(cy+Math.sin(a)*r)-1,2,2);ctx.restore();
  }}
}}

// ── Floor ────────────────────────────────────────────────────────────────────
const TILE=32;
function drawFloor(ctx,W,H){{
  for(let ty=0;ty<Math.ceil(H/TILE)+1;ty++)for(let tx=0;tx<Math.ceil(W/TILE)+1;tx++){{
    ctx.fillStyle=hx((tx+ty)%2===0?P.flA:P.flB);ctx.fillRect(tx*TILE,ty*TILE,TILE,TILE);
    ctx.strokeStyle=hx(P.flLine);ctx.lineWidth=0.4;ctx.strokeRect(tx*TILE+.5,ty*TILE+.5,TILE-1,TILE-1);
  }}
}}

// ── Layout ────────────────────────────────────────────────────────────────────
// [startCol, endCol, row, agentIdx]
const LAYOUT=[
  [1,2,0,0],  // Manager     (center 2 cols, row 0)
  [0,0,1,1],  // Security
  [1,1,1,2],  // Reliability
  [2,2,1,3],  // Cost
  [3,3,1,4],  // Observability
  [0,0,2,5],  // Scalability
  [1,2,2,6],  // Performance (wider)
  [3,3,2,7],  // Maintainability
  [1,2,3,8],  // Synthesizer (center 2 cols, row 3)
];
const NCOLS=4, NROWS=4;
const PAD=8, VPAD=28, CTOP=24;

// ── Agent class ───────────────────────────────────────────────────────────────
// Agents live in SCENE pixel coords (not cell-relative).
// The desk seat is stored so the manager can walk to any desk.

// ── Agent-specific funny think-bubbles ────────────────────────────────────────
const BUBBLES = {{
  manager_agent: {{
    idle:       ['Coffee time ☕','Reading CVs...','Org chart?','Team sync?','Slack: 47 msgs'],
    delegating: ['Your problem now!','Go get em!','I believe in you','On it! 👉','Deploy! 🚀'],
    done:       ['Nailed it 🎯','My work here...','Easy peasy','Call me maybe?','Mic drop 🎤'],
    error:      ['This is fine 🔥','Blame intern','Reboot? 🔄','...meeting?','LGTM? No?'],
  }},
  security_agent: {{
    idle:       ['Port scanning...','sus 👀','Zero trust. Even me.','Audit log: clean','Coffee = pwd?'],
    working:    ['SQL injection?!','JWT what?! 😱','No HTTPS?!','Rate limits pls','CVE incoming...','Credentials in ENV?!','Auth bypass?!','OWASP top 1!','This scares me','No salt?! 😰'],
    done:       ['Patched. Maybe.','Firewall: ✅','Sleeping better','Still scared tho','Call pen-tester!'],
    error:      ['Exploit found 💀','We are so hacked','Pwned. Literally.','Pack your bags','RUN'],
  }},
  reliability_agent: {{
    idle:       ['Uptime: 99.9%?','SPOF dreams...','5 nines plz','Ping...','Pong? Hello?'],
    working:    ['Single DB? Bold.','No failover? 😬','Circuit? Broken.','Retry storm ahead','One AZ?? WHY','No health check!','SLA: 50% lol','Domino effect 👀','It will fall...','Chaos monkey: me'],
    done:       ['Still standing!','Resilient! ish.','SLA: restored','PagerDuty: quiet','Touch wood 🪵'],
    error:      ['Cascading... 💥','It fell. Called it.','3am incident!','RTO: ∞','Alert! Alert!'],
  }},
  cost_agent: {{
    idle:       ['Checking bill...','AWS got ya 💸','Reserved? Nope','Idle EC2s...','Budget? LOL'],
    working:    ['$$$$ per month?!','Over-provisioned!','Data egress... 😭','No auto-scale?!','t3.large for cron?','NAT gateway tax','Orphan volumes 👻','Unused snapshots','Reserved > on-demand','Right-sizing needed'],
    done:       ['40% cheaper now','CFO is happy 📉','Saved: $12k/mo','AWS credits used','FinOps > DevOps'],
    error:      ['Bill too high 💀','Cloud broke','Burn rate: 🚀','AWS called us','Budget: deleted'],
  }},
  observability_agent: {{
    idle:       ['tail -f /dev/null','grep -r panic .','cat logs/*.log','Grafana loading','No dashboard 😔'],
    working:    ['No traces? 😤','Logs: raw JSON?!','Alert fatigue!','Missing metrics!','3am + no runbook','Correlation ID?','Blind spot here!','stdout only? smh','No health endpoint','Dashboard: empty'],
    done:       ['Tracing: done!','On-call: informed','Dashboards: ✅','SLO defined!','Runbook written'],
    error:      ['Alert storm! 🚨','On-call is asleep','Logs: /dev/null','Unknown unknowns','PagerDuty: RIP'],
  }},
  scalability_agent: {{
    idle:       ['Load test? Nah','10x traffic?','Stateful... hmm','Sharding? Later.','HPA enabled?'],
    working:    ['Single thread!','Shared state 😱','No queue? Bold.','DB writes: bottleneck','Session in RAM?!','Fan-out explosion','Sync all the way!','Connection pool: full','Vertical only? rly','No cache layer?!'],
    done:       ['10x ready! Kinda.','Horizontal: ✅','Stateless: done','Sharded! Finally','Queue added ✅'],
    error:      ['Thundering herd!','Connection storm','DB: on fire 🔥','Traffic 10x: down','Melted. Literally.'],
  }},
  performance_agent: {{
    idle:       ['p99: unknown 🤷','N+1 is fine... no','Cache hit: 0%','Latency? vibes','Profiler needed'],
    working:    ['N+1 query!! 😤','No cache layer!','Sync call: 3s?!','Cold start: pain','DB index? Never','Waterfall chain!','No CDN for static!','Chatty API 💬','CPU: 100% on what','Serialization: slow'],
    done:       ['p99: 42ms ✅','Cache: 94% hit!','Lazy loaded!','Index added 🚀','Latency: tamed'],
    error:      ['Timeout: 30s 💀','OOM: forever','CPU pegged 📈','GC storm! ☠️','Users left. Bye.'],
  }},
  maintainability_agent: {{
    idle:       ['git blame... me','TODO: fix later','Tech debt = ∞','Bus factor: 1','Docs? git log'],
    working:    ['Shared DB!! 😱','No interfaces?!','God class found','Circular deps!','Deploy: manual?!','No feature flags','Monolith in disguise','Test coverage: 4%','Friday deploys?!','12 env vars: WHAT'],
    done:       ['Refactored! ish','ADR written ✅','Bus factor: 2!','Docs: updated 📚','CI/CD: fixed'],
    error:      ['Prod is config.js','Tech debt won','Nobody knows this','Rollback: impossible','YOLO deploy: oops'],
  }},
  synthesizer_agent: {{
    idle:       ['Connecting dots...','Pattern detected','Reading all notes','Cross-ref time!','Thinking... 🤔'],
    working:    ['Root cause!','This explains that!','Classic anti-pattern','I see it now...','Ooh, they overlap!','Systemic issue!','The plot thickens','Risk: compounding','Good catch team!','Connecting 7 inputs'],
    done:       ['Story: complete!','Synthesis: done ✅','TLDR: fix the DB','Final boss: defeated','Shipped! 🚢'],
    error:      ['Mixed signals...','Contradiction found','Too much to parse','Findings: chaotic','404: conclusion'],
  }},
}};

function getBubble(agentKey, state) {{
  const pool = BUBBLES[agentKey];
  if (!pool) return null;
  const msgs = pool[state] || pool['working'] || ['...'];
  return msgs[Math.floor(Math.random() * msgs.length)];
}}

class Agent{{
  constructor(def,seatX,seatY,cellCX,cellCY,variant){{
    this.def=def; this.variant=variant;
    this.seatX=seatX; this.seatY=seatY;
    this.x=seatX; this.y=seatY+40;
    this.targetX=seatX; this.targetY=seatY;
    this.state='walking';
    this.frame=0; this.tick=0; this.speed=2.2;
    this.bubble=null; this.status='idle'; this.count=0;
    this.visitQueue=[]; this.visitPause=0;
    this.idleMsgInterval = 80 + Math.floor(Math.random()*80); // stagger idle bubbles
  }}

  walkTo(tx,ty){{this.targetX=tx;this.targetY=ty;this.state='walking';}}

  _bubble(state,color,ttl){{
    const txt=getBubble(this.def.key,state);
    if(txt)this.bubble={{text:txt,color:color,ttl:ttl}};
  }}

  update(externalStatus,count,isManager){{
    this.tick++; this.count=count;
    const prev=this.status; this.status=externalStatus;

    // Walk towards target
    if(this.state==='walking'||isManager&&this.visitQueue.length>0){{
      if(isManager&&this.state!=='walking'&&this.visitQueue.length>0&&this.visitPause<=0){{
        const next=this.visitQueue.shift();
        this.targetX=next.x; this.targetY=next.y; this.state='walking';
        this._bubble('delegating',P.dR,90);
      }}
      const dx=this.targetX-this.x, dy=this.targetY-this.y;
      const dist=Math.sqrt(dx*dx+dy*dy);
      if(dist<this.speed){{
        this.x=this.targetX; this.y=this.targetY;
        if(this.visitQueue.length===0){{
          this.state=externalStatus==='running'?'working':'sitting';
        }}else{{
          this.visitPause=40;
          this.state='sitting';
        }}
      }}else{{
        this.x+=dx/dist*this.speed; this.y+=dy/dist*this.speed;
      }}
    }}

    if(this.visitPause>0)this.visitPause--;

    // State transitions
    if(this.state==='sitting'&&externalStatus==='running'){{
      this.state='working';
      this._bubble('working',P.dR,110);
    }}
    if(this.state==='working'){{
      if(this.tick%8===0)this.frame=(this.frame+1)%4;
      // Random working thoughts every ~10s (staggered per agent)
      if(this.tick%160===0)this._bubble('working',P.dR,65);
      if(externalStatus==='done'){{
        this.state='done';
        this._bubble('done',P.dD,220);
      }}
      if(externalStatus==='error'){{
        this.state='error';
        this._bubble('error',P.dE,220);
      }}
    }}
    if(this.state==='done'&&this.tick%6===0)this.frame=(this.frame+1)%4;
    // Idle thoughts (staggered so all agents don't talk at once)
    if(this.state==='sitting'&&this.tick%this.idleMsgInterval===0){{
      this._bubble('idle',P.dI,45);
    }}

    if(this.bubble){{this.bubble.ttl--;if(this.bubble.ttl<=0)this.bubble=null;}}
  }}

  draw(ctx,t){{
    // Draw at scene coords directly (no extra zoom multiply)
    const sx=Math.round(this.x), sy=Math.round(this.y);
    const SPW=32, SPH=48; // display size of sprite

    let pose='idle';
    if(this.state==='walking')pose='walking';
    else if(this.state==='working')pose='working';
    else if(this.state==='done')pose='done';

    const sprite=mkSprite(this.variant,pose,this.frame);
    ctx.imageSmoothingEnabled=false;
    ctx.drawImage(sprite,sx-SPW/2,sy-SPH,SPW,SPH);

    // shadow
    ctx.fillStyle='rgba(0,0,0,0.3)';
    ctx.beginPath();ctx.ellipse(sx,sy,SPW*0.35,4,0,0,Math.PI*2);ctx.fill();

    if(this.state==='done')drawSparkles(ctx,sx,sy-SPH*0.5,t);

    if(this.bubble){{
      const alpha=Math.min(1,this.bubble.ttl/15);
      ctx.save();ctx.globalAlpha=alpha;
      drawBubble(ctx,sx,sy-SPH,this.bubble.text,this.bubble.color);
      ctx.restore();
    }}
  }}
}}

// ── Scene ─────────────────────────────────────────────────────────────────────
let agents=[], sceneW=0, sceneH=0, rafId=null;

function initScene(){{
  const cv=document.getElementById('cv'); if(!cv)return;
  const avail=cv.parentElement.clientWidth||780;
  const cellW=Math.floor((avail-PAD*2-3)/NCOLS); // 3px tolerance
  const cellH=Math.round(cellW*0.92); // taller cells = more room for desk+character
  sceneW=avail;
  sceneH=NROWS*(cellH+VPAD)+PAD*2+CTOP+20;
  cv.width=sceneW; cv.height=sceneH;
  cv.style.width=sceneW+'px'; cv.style.height=sceneH+'px';

  // Build cell layout
  cellLayout=LAYOUT.map(([sc,ec,row,ai])=>{{
    const span=ec-sc+1;
    const cx=PAD+sc*cellW;
    const cy=PAD+CTOP+row*(cellH+VPAD);
    const cw=span*cellW+(span-1)*3;
    // Desk center within cell (upper 45% of cell)
    const deskCX=cx+cw/2;
    const deskCY=cy+cellH*0.28;
    // Seat: below desk front edge
    const seatX=cx+cw/2;
    const seatY=cy+cellH*0.62;
    return {{sc,ec,row,ai,cx,cy,cw,ch:cellH,deskCX,deskCY,seatX,seatY}};
  }});

  agents=cellLayout.map(cl=>{{
    const def=AGENTS[cl.ai];
    return {{
      agent: new Agent(def,cl.seatX,cl.seatY,cl.cx,cl.cy,def.variant),
      ...cl
    }};
  }});
}}

// After squad starts: queue manager to walk desk-to-desk delivering tasks
function triggerManagerWalk(){{
  const managerEntry=agents.find(a=>a.ai===0);
  if(!managerEntry)return;
  const mgr=managerEntry.agent;
  // Queue visits to each specialist desk (skip own desk)
  const visits=agents
    .filter(a=>a.ai!==0&&a.ai!==8) // skip manager + synthesizer
    .map(a=>{{return{{x:a.seatX,y:a.seatY}}}});
  // Return to own seat last
  visits.push({{x:managerEntry.seatX,y:managerEntry.seatY}});
  mgr.visitQueue.push(...visits);
}}

let managerWalkTriggered=false;

// ── Render loop ───────────────────────────────────────────────────────────────
function loop(t){{
  const cv=document.getElementById('cv');if(!cv)return;
  const ctx=cv.getContext('2d');ctx.imageSmoothingEnabled=false;
  ctx.clearRect(0,0,sceneW,sceneH);
  drawFloor(ctx,sceneW,sceneH);

  // Top wall strip
  bx(ctx,0,0,sceneW,CTOP*0.8,P.wall);
  bx(ctx,0,0,sceneW,3,P.wallT);

  // Check if manager should start walking
  const mgrRunning=(STATES['manager_agent']||{{}}).status==='running';
  if(mgrRunning&&!managerWalkTriggered){{
    managerWalkTriggered=true;
    setTimeout(triggerManagerWalk,800);
  }}
  if(!mgrRunning&&(STATES['manager_agent']||{{}}).status==='idle')managerWalkTriggered=false;

  // ── PASS 1: update state + draw cell bg, desk, name card, status label ────
  agents.forEach(({{agent,ai,cx,cy,cw,ch,deskCX,deskCY}})=>{{
    const sd=STATES[agent.def.key]||{{status:'idle',count:0}};
    const status=sd.status||'idle';
    const count=sd.count||0;
    const isRun=status==='running',isDone=status==='done',isErr=status==='error';
    const isManager=ai===0;

    // Always update state (must happen every frame)
    agent.update(status,count,isManager);

    // Cell background
    const bg=isRun?0x1a1838:isDone?0x0a2010:isErr?0x200808:0x16122a;
    const bc=isRun?0x818cf8:isDone?0x22c55e:isErr?0xf87171:0x3d3560;
    rr(ctx,cx,cy,cw,ch,6,bg,0.88);
    ctx.strokeStyle=hx(bc);ctx.lineWidth=isRun||isDone||isErr?1.5:0.7;
    ctx.beginPath();ctx.roundRect(cx,cy,cw,ch,6);ctx.stroke();

    // Running glow pulse
    if(isRun){{
      ctx.save();ctx.globalAlpha=0.07+Math.sin(t*0.003)*0.04;
      ctx.fillStyle=hx(0x818cf8);ctx.beginPath();ctx.roundRect(cx,cy,cw,ch,6);ctx.fill();ctx.restore();
    }}

    // Desk (upper portion of cell, always inside own cell)
    const deskDrawX=cx+cw/2-DW/2;
    const deskDrawY=cy+ch*0.08;
    drawDesk(ctx,deskDrawX,deskDrawY,isRun||isDone,ai);

    // Name card (above cell top)
    drawCard(ctx,cx,cy,cw,agent.def,status,count);

    // Status label (bottom of cell)
    const lbl=isRun?'🔄 running':isDone?'✅ done':isErr?'❌ error':'⏸ idle';
    ctx.font='7px sans-serif';
    ctx.fillStyle=hx(isRun?0x818cf8:isDone?0x22c55e:isErr?0xf87171:0x3d3560);
    ctx.textAlign='center';ctx.fillText(lbl,cx+cw/2,cy+ch-4);ctx.textAlign='left';
  }});

  // ── PASS 2: draw ALL characters on top of ALL cells ───────────────────────
  // This guarantees the Manager (and any walking agent) is never buried
  // under another cell's background when crossing cell boundaries.
  agents.forEach(({{agent}})=>{{
    agent.draw(ctx,t);
  }});

  rafId=requestAnimationFrame(loop);
}}

// ── Manager card update ───────────────────────────────────────────────────────
function updateMgr(){{
  const card=document.getElementById('mgr'),stEl=document.getElementById('mst');
  const tags=document.getElementById('tags'),brief=document.getElementById('brief');
  const sub=document.getElementById('sub');
  const ms=(STATES['manager_agent']||{{}}).status||'idle';
  card.className='';
  if(ms==='running'){{card.classList.add('running');stEl.textContent=LANG==='pt'?'⏳ rodando…':'⏳ running…';}}
  else if(ms==='done'||Object.keys(PLAN).length>0){{card.classList.add('done');stEl.textContent=LANG==='pt'?'✅ concluído':'✅ done';}}
  else stEl.textContent=LANG==='pt'?'aguardando':'waiting';
  if(LANG==='pt')sub.textContent='Analisa arquitetura · Decide prioridades · Injeta contexto de foco';
  tags.innerHTML='';
  if(PLAN.architecture_type)tags.innerHTML+=`<span class="tag ta">${{PLAN.architecture_type}}</span>`;
  if(PLAN.complexity)tags.innerHTML+=`<span class="tag tx">${{LANG==='pt'?'complexidade':'complexity'}}: ${{PLAN.complexity}}</span>`;
  (PLAN.compliance_flags||[]).forEach(f=>tags.innerHTML+=`<span class="tag tc">⚑ ${{f}}</span>`);
  (PLAN.cloud_providers||[]).forEach(p=>tags.innerHTML+=`<span class="tag tl">☁️ ${{p}}</span>`);
  if(PLAN.manager_briefing){{brief.style.display='block';brief.textContent='💬 '+PLAN.manager_briefing.slice(0,180);}}
}}

// ── Boot ──────────────────────────────────────────────────────────────────────
window.addEventListener('load',()=>{{
  updateMgr();
  initScene();
  rafId=requestAnimationFrame(loop);

  // Notify parent iframe of actual content height so Streamlit can size correctly
  function reportHeight(){{
    const h = document.getElementById('wrap').scrollHeight + 4;
    window.parent.postMessage({{type:'streamlit:setFrameHeight', height:h}}, '*');
  }}
  // Report after first paint and on resize
  setTimeout(reportHeight, 200);
  window.addEventListener('resize',()=>{{
    if(rafId)cancelAnimationFrame(rafId);
    initScene();
    rafId=requestAnimationFrame(loop);
    setTimeout(reportHeight, 100);
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
