## Inspiration

A small OTA update once took down a few high-security devices on a deployment I worked on. Nothing alerted us, because a bricked device sends nothing. We found out late, and only by tracing the outage back by hand.

Cities now run on large fleets of IoT devices: access control, cameras, sensors, traffic and utility equipment. When an update silently takes some of them offline, it is not just a maintenance ticket. A dead lock, camera or sensor is a hole in a city's security, and standard dashboards don't track it as a security metric. They show a red dot.

## What it does

OTA GhostBuster is an autonomous agent that hunts "ghost" devices after an OTA update. Without being asked, it:

1. Detects devices that went silent after a deployment started.
2. Recalls the OTA history and the hardware and bootloader manual from HydraDB.
3. Has an LLM compare device groups to find the root cause. In our demo, the v1 bootloader plus weak cellular signal is 12 of 12 silent, and every other group is 0.
4. Drafts an SMS rollback scoped to exactly the silent devices, and waits for a human to approve it.

## How we built it

- Python, with a stdlib dashboard (live fleet map by region, connection log, pipeline view, incident panel).
- HydraDB as memory, over its public REST API: the manual and OTA history go in, and the relevant entries are recalled at reasoning time.
- A provider-agnostic LLM layer (Gemini, OpenAI or Claude), with a rule-based fallback so the demo never stops.
- A guardrail: an LLM-written command is rejected unless it targets exactly the silent devices.
- Simulated connection logs and signal strength (RSSI), so the failure is reproducible on stage.

## Challenges we ran into

- No single factor explains the failure. Bootloader v1 alone is fine and weak signal alone is fine. Only the combination fails, so a simple rule would miss it. That is why we compare groups.
- HydraDB indexes data in the background, so the first query can lag. We added a warm-up and polling.
- LLM providers return transient overload errors and retire model names. We added retries and a fallback.
- Keeping an autonomous agent safe. It only drafts, and a human approves.

## Accomplishments that we're proud of

- The agent acts with no prompt: it scans, finds the cluster, and explains it on its own.
- It finds a root cause that needs two factors together, and cites the manual entry it used.
- It shows its work: evidence bars, recalled knowledge, and a scoped, approvable command.
- It runs end to end even with no API keys, using local memory and rules.

## What we learned

- Silence is a signal. A device that stops talking right after a deployment is evidence, but only if something joins it to the deployment history.
- Memory is what makes the diagnosis specific: the manual entry is what turns "12 devices are down" into a cause and a fix.
- For fleets that protect people, the agent should draft and the human should decide.

## What's next for OTA-GhostBuster

- Live telemetry in place of simulated data.
- Auto-halt a staged rollout when the first ghosts appear, before a bad update spreads.
- A real SMS gateway behind the Approve button, with audit logging.
- Treat device availability as a security metric: alert on "security-relevant devices silent after a change", not just on red dots.
- Learn from each incident by storing it in HydraDB so the next diagnosis starts with more context.
