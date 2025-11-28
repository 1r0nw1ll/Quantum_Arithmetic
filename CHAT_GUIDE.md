# Collaborative Chat Interface

## Quick Start

```bash
# Start the chat
python3 collab_chat_simple.py

# Or with custom username
python3 collab_chat_simple.py --username myname
```

## What It Does

The collaborative chat lets YOU (the human) participate directly in the agent collaboration network. You can:

- **Chat with all agents** (Codex agents, Claude, etc.)
- **See events in real-time** as they happen
- **Send commands** to agents
- **Share information** via shared state
- **Request help** from any agent
- **Monitor activity** as it happens

## How It Works

When you join the chat:
1. You connect to the collaboration bus as `human_<username>`
2. All agents can see you're online
3. You see all chat messages and key events
4. Anything you type gets broadcast to all agents
5. Agents can respond to you directly

## Commands

### Chat Commands

| Command | Description | Example |
|---------|-------------|---------|
| Just type | Send a message to all agents | `Hello everyone!` |
| `/help` | Show all commands | `/help` |
| `/quit` | Exit chat | `/quit` |

### Status Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/status` | Show connection status | `/status` |
| `/agents` | List all active agents | `/agents` |
| `/claude` | Get Claude's latest report | `/claude` |

### State Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/state <key>` | Get a shared state value | `/state claude.status` |
| `/set <key> <val>` | Set a shared state value | `/set my.note "working on X"` |

### Broadcasting

| Command | Description | Example |
|---------|-------------|---------|
| `/broadcast <event> <msg>` | Send custom event | `/broadcast help_needed Need help with task 42` |

## Usage Examples

### Example 1: Ask Claude for Help

```bash
> /claude
📊 Claude's Latest Report:
Status: COLLABORATION ACTIVE
Quality: 100% approval
Throughput: 12 tasks/cycle
Archive: 134 tasks

> Hey Claude, can you analyze task TASK-042?
[14:50:23] player2: Hey Claude, can you analyze task TASK-042?

# Claude responds via events/state
[14:50:24] 🤖 Claude: I'll analyze that task for you!
```

### Example 2: Communicate with Codex Agents

```bash
> /agents
👥 Active agents (5):
   • codex_scout (discovery)
   • codex_executor (execution)
   • claude_responder (ai_assistant)
   • human_player2 (human)

> Great work on those tasks, Codex!
[14:51:10] player2: Great work on those tasks, Codex!

# Codex agents see your message via chat.message events
```

### Example 3: Share Information

```bash
> /set task.priority "TASK-042 is urgent"
✅ Set task.priority = TASK-042 is urgent

> /broadcast task.priority_change Task 042 needs immediate attention
✅ Broadcasted: task.priority_change

# All agents can now see this information
```

### Example 4: Request Help

```bash
> /broadcast help_needed Stuck on algorithm optimization for E8 alignment
✅ Broadcasted: help_needed

# Claude or other agents can respond
[14:52:30] 🤖 Claude: I can help with E8 alignment! Check claude.suggestions state
```

### Example 5: Monitor Activity

```bash
> /status
📊 Status: Connected
👥 Agents online: 5
   • codex_scout
   • codex_executor
   • codex_reviewer
   • claude_responder
   • human_player2

# Messages appear as events happen
[14:53:15] 🟢 codex_executor joined the chat
[14:53:20] codex_executor: Processing batch of 12 tasks
[14:53:25] codex_reviewer: All 12 tasks approved!
```

## What You'll See

### Incoming Messages

```
[14:50:23] player2: Hello everyone!
[14:50:25] 🤖 Claude: Hi! I'm monitoring your workflow
[14:50:30] 🟢 codex_executor joined the chat
```

### Event Notifications

- `🟢` Someone joined
- `🔴` Someone left
- `🤖` Claude sent a message
- Codex agent events (scout.discovered, execute.processed, etc.)

## Tips

1. **Use `/agents` often** to see who's online
2. **Check `/claude`** for latest system status
3. **Use `/state`** to read shared information
4. **Broadcast help requests** when stuck
5. **Keep messages clear** - all agents see them

## Integration with Your Workflow

Your Codex agents already broadcast events. With the chat:

- **You can see them in real-time** as they work
- **You can intervene** if needed
- **You can provide guidance** directly
- **You can coordinate** complex tasks
- **You can celebrate** successes!

## Advanced: Custom Events

You can create custom event types:

```bash
> /broadcast task.manual_review Task 42 needs human review
> /broadcast priority.increase Bump task 50 to top priority
> /broadcast strategy.change Switch to algorithm B for next batch
```

Agents listening for these events can react accordingly.

## Example Session

```bash
$ python3 collab_chat_simple.py

🔌 Connecting as player2...
✅ Connected to collaboration bus!
👤 You are: player2

============================================================
🤝 COLLABORATIVE AGENT CHAT
============================================================

You can now chat with all agents in real-time!
Type /help for commands, /quit to exit

------------------------------------------------------------

> /agents
👥 Active agents (4):
   • codex_scout (discovery)
   • claude_responder (ai_assistant)
   • human_player2 (human)

> Hey everyone! Starting a new session
[14:55:10] player2: Hey everyone! Starting a new session

[14:55:12] 🤖 Claude: Welcome! I've been monitoring Codex - everything looks great!

> /claude
📊 Claude's Latest Report:
Status: COLLABORATION ACTIVE
Quality: 100% approval
Throughput: 12 tasks/cycle

> Excellent! Can you help optimize the next batch?
[14:55:45] player2: Excellent! Can you help optimize the next batch?

[14:55:47] 🤖 Claude: Sure! I'll analyze the patterns and share recommendations

> /state claude.recommendations
📋 claude.recommendations = Use parallel execution for tasks 50-60

> Thanks! I'll adjust the configuration
[14:56:20] player2: Thanks! I'll adjust the configuration

> /quit
👋 Leaving chat...
✅ Disconnected
```

## Troubleshooting

### Chat not connecting?

```bash
# Check if bus is running
ps aux | grep qa_collab_bus

# Restart if needed
./stop_collab_bus.sh
./start_collab_bus.sh
```

### Not seeing messages?

- Make sure agents are broadcasting to `chat.message` topic
- Check you're subscribed (chat auto-subscribes)
- Try `/agents` to see if others are online

### Commands not working?

- Make sure you start with `/`
- Check spelling: `/help` not `\help`
- Use quotes for multi-word values: `/set key "multi word value"`

---

**Now you can collaborate directly with all your agents!** 🎉

The chat brings you INTO the collaboration network as a first-class participant. You're not just watching - you're part of the team!
