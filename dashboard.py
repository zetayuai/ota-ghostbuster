"""python3 dashboard.py -> http://localhost:8765  (stdlib + ghostbuster.py)"""
import json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from ghostbuster import Agent, Fleet, make_memory

agent = Agent(Fleet(), make_memory())

PAGE = r"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>OTA GhostBuster</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#14171c;--mute:#667085;--line:#e4e7ec;--ok:#1f9d55;--bad:#d92d3a;--warn:#e08a00;--accent:#4f46e5;--code:#0f172a;--codeink:#86efac}
@media(prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#161b22;--ink:#e6edf3;--mute:#8b949e;--line:#2a313c;--ok:#3fb950;--bad:#f85149;--warn:#d29922;--accent:#818cf8;--code:#010409}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:16px}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:16px}
h1{font-size:20px;margin:0}h1 span{color:var(--mute);font-weight:400;font-size:13px;margin-left:8px}
.pills{display:flex;gap:8px;flex-wrap:wrap}.pill{border:1px solid var(--line);background:var(--card);border-radius:99px;padding:3px 10px;font-size:12px;color:var(--mute)}
.pill b{color:var(--ink)}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--ok);margin-right:6px;animation:p 1.6s infinite}
@keyframes p{50%{opacity:.3}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);margin:0 0 12px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}
.kpi .n{font-size:28px;font-weight:700}.kpi .l{color:var(--mute);font-size:12px}
.steps{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px}
.step{border:1px solid var(--line);background:var(--card);border-radius:10px;padding:10px 12px;color:var(--mute);position:relative}
.step b{display:block;color:var(--ink);font-size:13px}.step small{font-size:12px}
.step.active{border-color:var(--accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 25%,transparent)}
.step.active::after{content:"working…";position:absolute;right:10px;top:10px;font-size:11px;color:var(--accent)}
.step.done{border-color:var(--ok)}.step.done::after{content:"✓";position:absolute;right:10px;top:8px;color:var(--ok);font-weight:700}
.main{display:grid;grid-template-columns:1.05fr 1fr;gap:12px;align-items:start}.col{display:grid;gap:12px}
.regions{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.region h3{font-size:12px;margin:0 0 6px;color:var(--mute);font-weight:600}
.devs{display:grid;grid-template-columns:repeat(5,1fr);gap:4px}
.d{height:26px;border-radius:5px;background:var(--ok);color:#fff;font-size:10px;display:flex;align-items:center;justify-content:center;border-bottom:3px solid transparent}
.d.weak{border-bottom-color:var(--warn)}.d.x{background:#6b7280;outline:2px dashed var(--bad);outline-offset:-2px}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--mute);font-size:12px;margin-top:12px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-2px;background:var(--ok)}
.log{font:12px ui-monospace,Menlo,monospace;max-height:300px;overflow:auto}
.log div{display:grid;grid-template-columns:84px 70px 1fr 70px;gap:6px;padding:3px 0;border-bottom:1px solid var(--line)}
.up{color:var(--ok)}.down{color:var(--bad)}.mute{color:var(--mute)}
.empty{text-align:center;padding:36px 16px}.empty p{color:var(--mute);max-width:420px;margin:8px auto 16px}
button{font:inherit;font-weight:600;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:8px 14px;cursor:pointer}
button.pri{background:var(--accent);border-color:var(--accent);color:#fff}button.go{background:var(--ok);border-color:var(--ok);color:#fff}
button:disabled{opacity:.5;cursor:default}
.badge{display:inline-block;border-radius:6px;padding:1px 8px;font-size:11px;font-weight:700;background:var(--bad);color:#fff;margin-right:6px}
.badge.g{background:var(--ok)}.badge.m{background:var(--accent)}
.inc h3{margin:0 0 4px;font-size:17px}.sec{margin-top:16px}.sec h4{margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute)}
.bar{display:grid;grid-template-columns:190px 1fr 54px;gap:8px;align-items:center;margin:5px 0;font-size:13px}
.track{height:12px;background:var(--line);border-radius:6px;overflow:hidden}.fill{height:100%;background:var(--mute)}.fill.hot{background:var(--bad)}
.quote{border-left:3px solid var(--accent);padding:4px 10px;margin:6px 0;color:var(--mute);font-size:13px}
pre{background:var(--code);color:var(--codeink);border-radius:8px;padding:12px;white-space:pre-wrap;word-break:break-all;margin:0;font-size:12px}
.row{display:flex;gap:8px;margin-top:10px;align-items:center;flex-wrap:wrap}
.help summary{cursor:pointer;font-weight:700}.help p{margin:8px 0}.help ul{margin:6px 0 0;padding-left:20px}.help li{margin:3px 0}
.help .cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}.help h4{margin:10px 0 2px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute)}
@media(max-width:860px){.help .cols{grid-template-columns:1fr}}
@media(max-width:860px){.main{grid-template-columns:1fr}.kpis,.steps{grid-template-columns:repeat(2,1fr)}.bar{grid-template-columns:130px 1fr 50px}}
</style>
<div class=wrap>
<header><h1>OTA GhostBuster <span>autonomous ghost-device hunter</span></h1>
<div class=pills><span class=pill id=pAgent></span><span class=pill id=pMem></span><span class=pill id=pLlm></span></div></header>
<details class="card help" open style="margin-bottom:12px"><summary>What is this page? (click to hide)</summary>
<div class=cols><div>
<h4>Main focus</h4>
<p>A bad OTA update can leave devices bricked and <b>silent</b>. Silent devices send nothing, so normal alerts never fire. This page shows an AI agent that <b>notices the silence on its own</b>, links it to the update that caused it, finds the root cause using HydraDB memory (OTA history + hardware manual), and <b>drafts an SMS rollback for your approval</b>.</p>
<h4>Try it</h4>
<ul><li>Click <b>Push bad OTA update</b> (right panel).</li><li>Watch the four steps turn green.</li><li>Read the incident, then <b>Approve</b>. Nothing is really sent in this demo.</li><li><b>Reset demo</b> starts over.</li></ul>
</div><div>
<h4>How to read it</h4>
<ul><li><b>Top pills:</b> agent status, where memory lives (HydraDB or local mock), and which LLM reasons.</li>
<li><b>Tiles:</b> fleet size, online, silent, open incidents.</li>
<li><b>Four steps:</b> Detect, Recall, Reason, Draft. A green tick means done.</li>
<li><b>Fleet map:</b> one box per device. Gray with a red dashed edge is silent. An orange underline is weak signal.</li>
<li><b>Connection log:</b> latest connect and disconnect events with signal strength.</li>
<li><b>Incident (right):</b> the root cause, then the evidence bars. A <b style="color:var(--bad)">red bar</b> is the group where almost every device went silent, which is the culprit. Below that are the manual entries recalled from HydraDB and the drafted SMS payload.</li></ul>
</div></div></details>
<section class=kpis id=kpis></section>
<section class=steps id=steps></section>
<div class=main>
 <div class=col>
  <div class=card><h2>Fleet by region</h2><div class=regions id=regions></div>
   <div class=legend><span><i></i>Online</span><span><i style="background:#6b7280;outline:2px dashed var(--bad);outline-offset:-2px"></i>Silent</span>
   <span><i style="background:transparent;border-bottom:3px solid var(--warn);border-radius:0"></i>Weak signal (≤ -100 dBm)</span></div></div>
  <div class=card><h2>Live connection log</h2><div class=log id=log></div></div>
 </div>
 <div class=col id=right></div>
</div></div>
<script>
const $=id=>document.getElementById(id);
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e};
const STEPS=[["1. Detect","Silent drops after an OTA"],["2. Recall","Manual + OTA history (HydraDB)"],["3. Reason","Correlate, find root cause"],["4. Draft","SMS rollback for approval"]];
async function post(u){await fetch(u,{method:'POST'});load()}
function render(s){
 const down=s.devices.filter(d=>d.down).length,inc=s.incidents,working=s.stage>0;
 $('pAgent').replaceChildren(Object.assign(el('span','dot')),document.createTextNode(working?'Agent investigating':'Agent scanning every 2s'));
 $('pMem').replaceChildren(document.createTextNode('Memory: '),el('b',0,s.memory==='HydraMemory'?'HydraDB':'local mock'));
 $('pLlm').replaceChildren(document.createTextNode('Reasoning: '),el('b',0,s.llm||'rule-based'));
 $('kpis').replaceChildren(...[["Devices",s.devices.length,""],["Online",s.devices.length-down,"ok"],["Silent",down,down?"bad":""],["Incidents",inc.length,inc.length?"bad":""]]
  .map(([l,n,c])=>{const k=el('div','card kpi');const v=el('div','n',n);if(c)v.style.color=`var(--${c})`;k.append(v,el('div','l',l));return k}));
 $('steps').replaceChildren(...STEPS.map(([a,b],i)=>{const done=s.done&&!working||(working&&s.stage>i+1),act=working&&s.stage===i+1;
  const e=el('div','step'+(done?' done':act?' active':''));e.append(el('b',0,a),el('small',0,b));return e}));
 const regs={};s.devices.forEach(d=>(regs[d.region]=regs[d.region]||[]).push(d));
 $('regions').replaceChildren(...Object.keys(regs).sort().map(r=>{const w=el('div','region');w.append(el('h3',0,`${r} · ${regs[r].filter(d=>d.down).length} silent`));
  const g=el('div','devs');regs[r].sort((a,b)=>a.id<b.id?-1:1).forEach(d=>{const e=el('div','d'+(d.down?' x':'')+(d.rssi<=-100?' weak':''),d.id.slice(-3));
   e.title=`${d.id}\nbootloader ${d.boot}\nsignal ${d.rssi} dBm`;g.append(e)});w.append(g);return w}));
 $('log').replaceChildren(...s.log.map(l=>{const r=el('div');r.append(el('span','mute',l.age+'s ago'),el('span',0,l.id),
  el('span',l.ev==='connected'?'up':'down',l.ev),el('span','mute',l.rssi+' dBm'));return r}));
 const R=$('right');
 if(inc.length){R.replaceChildren(...inc.map(incident))}
 else if(working){const c=el('div','card empty');c.append(el('h2',0,'Agent at work'),el('p',0,['','Silent devices detected after an OTA deployment. Checking the pattern…','Recalling the manual and deployment history from HydraDB…','Reasoning over the evidence…'][s.stage]));R.replaceChildren(c)}
 else{const c=el('div','card empty');c.append(el('h2',0,'No incidents'),el('p',0,`The agent is watching ${s.devices.length} devices and needs no prompt. Push a bad OTA update to see it detect, diagnose and draft a fix on its own.`));
  const b=el('button','pri','Push bad OTA update');b.onclick=()=>post('/inject');c.append(b);R.replaceChildren(c)}
}
function incident(i){
 const c=el('div','card inc');c.append(el('h2',0,'Incident'));
 const t=el('h3');t.append(el('span','badge','CRITICAL'),document.createTextNode(`${i.ids.length} of ${i.total} devices silent after ${i.dep}`));c.append(t);
 const w=el('div','sec');w.append(el('h4',0,'Root cause diagnosis'));w.append(el('div',0,i.diagnosis));
 const by=el('span','badge m','reasoned by '+i.source);by.style.marginTop='8px';by.style.display='inline-block';w.append(by);c.append(w);
 const e=el('div','sec');e.append(el('h4',0,'Evidence: silent devices per group'));
 i.groups.forEach(g=>{const hot=g.x/g.n>=.9,r=el('div','bar');r.append(el('span',0,g.label));const tr=el('div','track'),f=el('div','fill'+(hot?' hot':''));f.style.width=(100*g.x/g.n)+'%';tr.append(f);
  r.append(tr,el('b',0,`${g.x}/${g.n}`));e.append(r)});c.append(e);
 const m=el('div','sec');m.append(el('h4',0,'Recalled from HydraDB'));i.evidence.forEach(x=>m.append(el('div','quote',x)));c.append(m);
 const p=el('div','sec');p.append(el('h4',0,'Target patch payload: SMS rollback'),el('pre',0,i.command));
 const row=el('div','row'),pend=i.status.startsWith('pending');
 const a=el('button',pend?'go':'',pend?'Approve rollback':'✓ '+i.status);a.disabled=!pend;a.onclick=()=>post('/approve?key='+encodeURIComponent(i.key));
 const cp=el('button',0,'Copy');cp.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(i.command);cp.textContent='Copied'};
 const rs=el('button',0,'Reset demo');rs.onclick=()=>post('/reset');row.append(a,cp,rs);p.append(row);c.append(p);return c}
let fails=0;
async function load(){try{render(await (await fetch('/state')).json());fails=0}catch(e){if(++fails>2)$('pAgent').textContent='Server unreachable'}}
load();setInterval(load,1500)
</script>"""


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json"):
        self.send_response(200); self.send_header("Content-Type", ctype); self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        with agent.lock:
            if self.path == "/state": self._send(json.dumps(agent.state()).encode())
            else: self._send(PAGE.encode(), "text/html")

    def do_POST(self):
        u = urlparse(self.path)
        with agent.lock:
            if u.path == "/inject": agent.fleet.inject_bad_ota()
            elif u.path == "/approve": agent.approve(parse_qs(u.query)["key"][0])
            elif u.path == "/reset": agent.fleet, agent.incidents = Fleet(), {}
        self._send(b'{"ok":true}')

    def log_message(self, *a): pass


def loop():
    while True:
        agent.step()
        time.sleep(2)


if __name__ == "__main__":
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", 8765))), H).serve_forever()
