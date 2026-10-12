# OTA GhostBuster: Slide / Demo Flow (~4 min)

1. **Hook (20s).** "One bad OTA update turned 12 of our 60 smart assets into silent, bricked ghosts. No alert fired, because a dead device sends nothing."
2. **Problem (30s).** Dashboards show a red dot. Nobody connects the silence to the deployment. A truck rolls, and field-service cost climbs.
3. **Architecture (30s).** Show the diagram:
   - Simulated data: connection logs and cellular RSSI.
   - HydraDB knowledge: OTA deployment history and the bootloader/hardware manual.
   - LLM reasoning: correlates the silent drops with OTA timing.
   - Output: root cause plus a drafted SMS rollback payload.
4. **Live demo (100s).** Run `python3 dashboard.py` and open http://localhost:8765.
   - "Nobody is asking it anything. The agent scans every 2 seconds." The page shows all quiet.
   - Click **Push bad OTA update**. Within about 2s, 12 devices turn gray and an incident appears.
   - Read the evidence table: bootloader v1 with weak signal is 12/12 silent. Every other group is 0 silent.
   - Read the recalled manual entry: the bootloader v1 30s watchdog times out on weak signal.
   - Show the drafted `fleetctl sms-rollback` command, scoped to exactly those 12 devices.
   - Click **Approve**.
5. **Safety (15s).** The agent drafts and a human approves. A guardrail rejects any LLM command that targets a device outside the silent set.
6. **Impact (20s).** Minutes to diagnose instead of days. Recovery goes out by SMS because the modem is still alive, so no truck rolls. Each incident enriches HydraDB for the next one.
7. **Next (15s).** Live telemetry ingest, staged-rollout auto-halt, and real SMS gateway execution.

**Fallback:** `python3 ghostbuster.py` prints the same incident in the terminal.
