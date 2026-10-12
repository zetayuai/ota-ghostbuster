# OTA GhostBuster

Autonomous ghost-device hunter. After a bad OTA update, devices go silent. The agent detects the cluster, recalls the OTA history and bootloader manual from HydraDB, has an LLM find the root cause, and drafts an SMS rollback for human approval.

```
connection logs + RSSI (simulated) + HydraDB (OTA history, manual) -> LLM reasoning -> diagnosis + SMS rollback draft
```

## Run
```bash
cp .env.example .env     # add HYDRADB_API_KEY and one LLM key (Gemini, OpenAI or Anthropic); all optional
python3 dashboard.py     # http://localhost:8765  (PORT=8766 to change)
python3 ghostbuster.py   # terminal version with a self-check
```
Only `requests` is needed (`pip install requests`). With no keys it uses a local mock memory and rule-based reasoning.
