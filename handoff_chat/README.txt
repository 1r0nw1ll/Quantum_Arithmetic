This folder contains raw session/event logs for ingestion by a Claude agent.

Files
-----
- claude_agent.log         : Claude agent bus logs (greetings, subscriptions, status)
- logs.collab_events.jsonl : Collaboration bus events (may include message traces)
- logs.agent_runs.jsonl    : Agent run metadata
- logs.agent_daemon.out    : Daemon stdout (for recovery context)

Notes
-----
- These are raw logs. If a clean transcript is required, parse collab_events.jsonl for message events
  (e.g., type == 'chat.message', role == 'user'|'assistant') and extract content in chronological order.
- If the submission portal needs a plain-text transcript, produce transcript.txt from collab_events.jsonl.
