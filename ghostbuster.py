"""OTA GhostBuster: autonomous ghost-device hunter.  python3 ghostbuster.py

[connection logs + RSSI] + [HydraDB: OTA history + bootloader manual] -> LLM reasoning -> diagnosis + SMS rollback draft

Optional env:  HYDRADB_API_KEY + HYDRADB_DATABASE  -> real HydraDB (else local mock memory)
               ANTHROPIC_API_KEY | OPENAI_API_KEY | GEMINI_API_KEY -> LLM (else rule-based reasoning)
               LLM_PROVIDER (anthropic|openai|gemini) / LLM_MODEL to override the auto-pick."""
import json, os, random, re, threading, time
from collections import defaultdict

for _l in open(os.path.join(os.path.dirname(__file__), ".env")) if os.path.exists(
        os.path.join(os.path.dirname(__file__), ".env")) else []:  # KEY=value lines; real env vars win
    _k, _, _v = _l.partition("=")
    if _v.strip() and not _l.lstrip().startswith("#"): os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))

MIN_CLUSTER, WINDOW, WEAK = 3, 3600, -100  # WEAK: rssi dBm at or below this is "weak signal"
MANUAL = [  # hardware manual + bootloader docs, ingested into memory
    "MANUAL bootloader v1 timeout bug: the flash-verify watchdog is 30s. On weak cellular signal (RSSI at or "
    "below -100 dBm) the OTA image fetch exceeds it, the bootloader hangs, and the device goes silent. The modem "
    "stays alive and still accepts SMS. Fix: SMS rollback to the previous firmware.",
    "MANUAL bootloader v2 raises the flash-verify watchdog to 120s and is not affected by the timeout bug.",
    "MANUAL SMS recovery: the cellular modem runs independently of the main MCU. The SMS command ROLLBACK <ver> "
    "makes the bootloader boot the previous firmware slot.",
    "MANUAL regional outage: if every device in one region drops at once regardless of OTA, it is a carrier "
    "problem. Do not roll back; contact the carrier.",
]


class Memory:
    """Local stand-in with the same add/search interface as HydraMemory."""

    def __init__(self): self.docs = []
    def add(self, text, **meta): self.docs.append(text)

    def search(self, query, **_):
        tok = lambda s: set(re.findall(r"[\w.\-]+", s.lower()))
        q = tok(query)
        scored = sorted(((len(q & tok(t)), t) for t in self.docs), reverse=True)
        return [t for s, t in scored if s]


class HydraMemory:
    """Real HydraDB over its public REST API. Ingest is async, so search() flushes the
    buffer and polls until the manual is indexed."""

    def __init__(self):
        import requests
        self.r, self.buf, self.n = requests, [], 0
        self.base = os.environ.get("HYDRADB_BASE_URL", "https://api.hydradb.com")
        self.h = {"Authorization": "Bearer " + os.environ["HYDRADB_API_KEY"]}
        self.tenant = os.environ["HYDRADB_DATABASE"]

    def add(self, text, **meta):
        self.n += 1
        self.buf.append(dict(id=f"ota-{self.n}-{int(time.time())}", title=text.split()[0],
                             content={"text": text}, metadata=meta, infer=False))

    def _post(self, path, **kw):
        body = self.r.post(self.base + path, headers=self.h, timeout=30, **kw).json()
        if not body.get("success"): raise RuntimeError(body.get("error") or body)
        return body.get("data") or {}

    @staticmethod
    def _text(c):
        t = c.get("chunk_content") or c.get("text") or ""
        try: t = json.loads(t)["content"]["text"]  # stored envelope -> prose
        except Exception: pass
        return t

    def search(self, query, **_):
        if self.buf:
            self._post("/context/ingest", files={
                "tenant_id": (None, self.tenant), "sub_tenant_id": (None, ""), "kind": (None, "knowledge"),
                "app_knowledge": (None, json.dumps(self.buf))})
            self.buf = []
        for _ in range(30):  # ponytail: poll ~60s for async indexing
            ch = self._post("/query", json=dict(tenant_id=self.tenant, sub_tenant_id="", query=query,
                                                kind="knowledge", mode="fast", max_results=6)).get("chunks") or []
            hits = [self._text(c) for c in ch]
            if any("MANUAL" in t for t in hits): return hits
            time.sleep(2)
        return []


def make_memory():
    return HydraMemory() if os.environ.get("HYDRADB_API_KEY") else Memory()


def provider():
    e = os.environ.get
    keys = dict(anthropic=e("ANTHROPIC_API_KEY"), openai=e("OPENAI_API_KEY"),
                gemini=e("GEMINI_API_KEY") or e("GOOGLE_API_KEY"))
    p = e("LLM_PROVIDER") or next((k for k, v in keys.items() if v), None)
    return (p, keys[p]) if p and keys.get(p) else (None, None)


def llm(prompt, tries=4):
    for t in range(tries):  # providers return transient 503/overload errors; back off and retry
        try: return _llm(prompt)
        except RuntimeError as e:
            if t == tries - 1 or "UNAVAILABLE" not in str(e) and "overload" not in str(e).lower(): raise
            time.sleep(3 * (t + 1))


def _llm(prompt):
    """Provider-agnostic text completion. Returns None if no key is set."""
    e = os.environ.get
    p, _ = provider()
    if not p: return None
    keys = dict(anthropic=e("ANTHROPIC_API_KEY"), openai=e("OPENAI_API_KEY"),
                gemini=e("GEMINI_API_KEY") or e("GOOGLE_API_KEY"))
    import requests
    k, m = keys[p], e("LLM_MODEL")
    if p == "anthropic":
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=25,
                          headers={"x-api-key": k, "anthropic-version": "2023-06-01"},
                          json=dict(model=m or "claude-sonnet-5-5", max_tokens=700,
                                    messages=[dict(role="user", content=prompt)])).json()
        if "content" not in r: raise RuntimeError(r.get("error", r))
        return p, r["content"][0]["text"]
    if p == "openai":
        r = requests.post("https://api.openai.com/v1/chat/completions", timeout=25,
                          headers={"Authorization": "Bearer " + k},
                          json=dict(model=m or "gpt-4o-mini", messages=[dict(role="user", content=prompt)])).json()
        if "choices" not in r: raise RuntimeError(r.get("error", r))
        return p, r["choices"][0]["message"]["content"]
    m = m or "gemini-3.8-flash"  # ponytail: model names retire; override with LLM_MODEL
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", timeout=25,
                      headers={"x-goog-api-key": k},
                      json=dict(contents=[dict(parts=[dict(text=prompt)])])).json()
    if "candidates" not in r: raise RuntimeError(r.get("error", r))
    return p, r["candidates"][0]["content"]["parts"][0]["text"]


class Fleet:
    """60 devices over 4 regions. Bootloader v1 on even ids. Weak signal (rssi <= -100) on 40%."""

    def __init__(self, n=60):
        now = time.time()
        self.devs = [dict(id=f"dev-{i:03}", region=["us-west", "us-east", "eu-west", "ap-south"][i % 4],
                          boot="v1" if i % 2 == 0 else "v2",
                          rssi=-100 - i % 7 if i % 5 < 2 else -60 - i % 25) for i in range(n)]
        self.deps = []  # OTA deployment history
        self.events = [(now - 7200, d["id"], "connected", d["rssi"]) for d in self.devs]
        self.events += [(now - 2400, i, "disconnected", self.devs[int(i[-3:])]["rssi"])  # unrelated noise
                        for i in ("dev-001", "dev-002")]

    def inject_bad_ota(self):
        """OTA-2.2.0 goes to every device 15 min ago. v1 bootloader + weak signal hangs in flash verify."""
        now = time.time()
        dep = dict(id="OTA-2.2.0", prev="v2.1", fw="v2.2", start=now - 900)
        self.deps.append(dep)
        for d in self.devs:
            bad = d["boot"] == "v1" and d["rssi"] <= WEAK
            self.events.append((dep["start"] + random.randint(60, 600), d["id"],
                                "disconnected" if bad else "connected", d["rssi"]))
        return dep

    def last(self):
        out = {}
        for e in sorted(self.events, key=lambda e: e[0]): out[e[1]] = e
        return out


def scan(fleet, now=None):
    """Per OTA deployment: devices whose latest state is 'disconnected' since it started."""
    now, last, out = now or time.time(), fleet.last(), {}
    for dep in fleet.deps:
        ids = sorted(i for ts, i, ev, _ in last.values() if ev == "disconnected" and dep["start"] <= ts <= now)
        if len(ids) >= MIN_CLUSTER: out[dep["id"]] = ids
    return out


def breakdown(fleet, ids):
    """Silent/total per (bootloader, signal) group: the evidence the reasoner works from."""
    t = defaultdict(lambda: [0, 0])
    for d in fleet.devs:
        g = (d["boot"], "weak" if d["rssi"] <= WEAK else "strong")
        t[g][1] += 1; t[g][0] += d["id"] in ids
    return t


def reason(dep, ids, table, evidence):
    """LLM if any provider key is set, else rules. Output is only ever a draft for human approval."""
    rows = "; ".join(f"bootloader {b} + {s} signal: {x}/{n} silent" for (b, s), (x, n) in sorted(table.items()))
    groups = [dict(label=f"Bootloader {b} · {s} signal", x=x, n=n) for (b, s), (x, n) in sorted(table.items())]
    best = max(table.items(), key=lambda kv: kv[1][0] / kv[1][1])
    cmd = f'fleetctl sms-rollback --to {dep["prev"]} --payload "ROLLBACK {dep["prev"]}" --devices {",".join(ids)}'
    ok = best[1][0] / best[1][1] >= 0.9 and any("bootloader v1 timeout" in t for t in evidence)
    out = dict(source="rules", groups=groups, command=cmd if ok else "# no pattern matched the manual; escalate to on-call",
               diagnosis=f"{len(ids)} devices went silent minutes after {dep['id']}. {rows}. "
                         + (evidence[0] if evidence else "No manual entry matched."))
    try:
        r = llm(f"IoT incident. OTA {dep['id']} (firmware {dep['prev']} -> {dep['fw']}) was pushed to all devices. "
                f"{len(ids)} went silent (no heartbeat) 1-10 min later: {', '.join(ids)}.\nSilent counts by group: {rows}.\n"
                "Recalled knowledge:\n- " + "\n- ".join(evidence) +
                f'\nReply with JSON only: {{"diagnosis": "<2-3 sentences: the root cause and the evidence for it>", '
                f'"command": "<one `fleetctl sms-rollback --to {dep["prev"]} --payload \\"ROLLBACK {dep["prev"]}\\" '
                f'--devices id,id,...` command, or a # comment if no fix applies>"}}')
        if r:
            p, txt = r
            j = json.loads(txt[txt.index("{"): txt.rindex("}") + 1]); c = j["command"].strip()
            # guardrail: only the silent devices may be targeted, nothing else
            if c.startswith("#") or (c.startswith("fleetctl sms-rollback") and set(re.findall(r"dev-\d+", c)) == set(ids)):
                return dict(source=p, command=c, diagnosis=j["diagnosis"], table=rows, groups=groups)
    except Exception as e:
        print("LLM step failed, using rules:", e)
    return dict(out, table=rows)


class Agent:
    def __init__(self, fleet, mem):
        self.fleet, self.mem, self.incidents, self.lock = fleet, mem, {}, threading.Lock()
        self.stage = 0  # 0 watching, 1 detected, 2 recalling, 3 reasoning
        for m in MANUAL: mem.add(m, kind="manual")
        mem.search("MANUAL bootloader")  # warm up: wait until the manual is indexed

    def step(self):
        """One autonomous pass: scan -> recall -> reason -> draft. No query needed."""
        for dep_id, ids in scan(self.fleet).items():
            if dep_id in self.incidents or self.stage: continue  # ponytail: late joiners / concurrent incidents not handled
            try:
                self.stage = 1  # detected
                dep = next(d for d in self.fleet.deps if d["id"] == dep_id)
                self.mem.add(f"DEPLOYMENT {dep_id} firmware {dep['prev']} -> {dep['fw']} to all devices", kind="ota")
                for i in ids: self.mem.add(f"EVENT {i} went silent after {dep_id}", kind="event")
                table = breakdown(self.fleet, ids)
                (boot, sig), _ = max(table.items(), key=lambda kv: kv[1][0] / kv[1][1])
                self.stage = 2  # recalling from memory
                evidence = [t for t in self.mem.search(f"bootloader {boot} {sig} signal rssi OTA silent timeout watchdog")
                            if "MANUAL" in t][:3]
                self.stage = 3  # reasoning
                inc = dict(key=dep_id, dep=dep_id, ids=ids, total=len(self.fleet.devs), evidence=evidence,
                           status="pending approval", **reason(dep, ids, table, evidence))
                with self.lock: self.incidents[dep_id] = inc
            finally:
                self.stage = 0

    def approve(self, key):
        inc = self.incidents[key]
        inc["status"] = "approved (not executed in demo)"
        print("APPROVED:", inc["command"])

    def state(self):
        byid, now = {d["id"]: d for d in self.fleet.devs}, time.time()
        log = sorted(self.fleet.events, key=lambda e: -e[0])[:14]
        return dict(memory=type(self.mem).__name__, llm=provider()[0], stage=self.stage, done=bool(self.incidents),
                    log=[dict(age=int(now - ts), id=i, ev=ev, rssi=r) for ts, i, ev, r in log], devices=[dict(id=i, region=byid[i]["region"], boot=byid[i]["boot"], rssi=rssi,
                                  down=ev == "disconnected" and time.time() - ts < WINDOW)
                             for i, (ts, _, ev, rssi) in self.fleet.last().items()],
                    incidents=list(self.incidents.values()))


if __name__ == "__main__":
    a = Agent(Fleet(), make_memory())
    print("Memory:", type(a.mem).__name__)
    a.step(); assert not a.incidents, "noise alone must not raise an incident"
    a.fleet.inject_bad_ota(); a.step()
    (inc,) = a.incidents.values()
    print(f"{inc['dep']}: {len(inc['ids'])}/{inc['total']} silent [reasoned by {inc['source']}]")
    print("Diagnosis:", inc["diagnosis"]); print("Draft:", inc["command"])
    byid = {d["id"]: d for d in a.fleet.devs}
    assert len(inc["ids"]) == 12 and all(byid[i]["boot"] == "v1" and byid[i]["rssi"] <= WEAK for i in inc["ids"])
    assert inc["command"].startswith("fleetctl sms-rollback") and all(i in inc["command"] for i in inc["ids"])
    a.approve(inc["key"]); assert inc["status"].startswith("approved")
