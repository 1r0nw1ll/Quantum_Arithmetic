"""
Auto-refactor: normalize formatting for chat_closeout.py
"""

#!/usr/bin/env python3
"""
QA Chat Closeout Protocol v4.0
Exports Claude/Gemini/Codex chat sessions to Obsidian vault
Inspired by NetworkChuck's terminal AI workflow
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class ChatCloseout:
    """Handles exporting AI chat sessions to Obsidian vault"""

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = Path(vault_path or "obsidian_vault")
        self.vault_path = self.vault_path.expanduser()
        self.vault_path.mkdir(parents=True, exist_ok=True)

    def format_claude_session(self, session_data: Dict) -> str:
        """Format Claude chat session for Obsidian"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date = datetime.now().strftime("%Y-%m-%d")

        content = f"""# QA Claude Session - {timestamp}

**Date:** {date}
**Agent:** Claude Code
**Context:** QA Bob-iverse Research
**Session Type:** {session_data.get('type', 'development')}

## Summary
{session_data.get('summary', 'Session summary not provided')}

## Key Decisions
{session_data.get('decisions', '- None recorded')}

## Code Changes
{session_data.get('changes', '- None recorded')}

## Next Steps
{session_data.get('next_steps', '- None identified')}

## Raw Transcript
```
{session_data.get('transcript', 'Transcript not available')}
```

---
*Exported from QA Bob-iverse closeout protocol*
*Tags: #qa-research #claude-session #ai-chat*
"""
        return content

    def format_gemini_session(self, session_data: Dict) -> str:
        """Format Gemini chat session for Obsidian"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date = datetime.now().strftime("%Y-%m-%d")

        content = f"""# QA Gemini Session - {timestamp}

**Date:** {date}
**Agent:** Gemini CLI
**Context:** QA Bob-iverse Research
**Focus:** {session_data.get('focus', 'mathematical reasoning')}

## Insights Generated
{session_data.get('insights', '- None recorded')}

## Theorems/Proofs Discussed
{session_data.get('theorems', '- None discussed')}

## Validation Results
{session_data.get('validation', '- None performed')}

## Research Directions
{session_data.get('directions', '- None identified')}

## Raw Transcript
```
{session_data.get('transcript', 'Transcript not available')}
```

---
*Exported from QA Bob-iverse closeout protocol*
*Tags: #qa-research #gemini-session #ai-chat #mathematics*
"""
        return content

    def format_codex_session(self, session_data: Dict) -> str:
        """Format Codex chat session for Obsidian"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date = datetime.now().strftime("%Y-%m-%d")

        content = f"""# QA Codex Session - {timestamp}

**Date:** {date}
**Agent:** GitHub Codex
**Context:** QA Bob-iverse Research
**Task:** {session_data.get('task', 'code generation')}

## Code Generated
```python
{session_data.get('code', '# Code not available')}
```

## Implementation Notes
{session_data.get('notes', '- None recorded')}

## Testing Status
{session_data.get('testing', '- Not tested')}

## Integration Points
{session_data.get('integration', '- None identified')}

## Raw Transcript
```
{session_data.get('transcript', 'Transcript not available')}
```

---
*Exported from QA Bob-iverse closeout protocol*
*Tags: #qa-research #codex-session #ai-chat #code*
"""
        return content

    def export_session(self, provider: str, session_data: Dict) -> Path:
        """Export a chat session to Obsidian vault"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if provider.lower() == "claude":
            content = self.format_claude_session(session_data)
            filename = f"Claude_Session_{timestamp}.md"
        elif provider.lower() == "gemini":
            content = self.format_gemini_session(session_data)
            filename = f"Gemini_Session_{timestamp}.md"
        elif provider.lower() == "codex":
            content = self.format_codex_session(session_data)
            filename = f"Codex_Session_{timestamp}.md"
        else:
            raise ValueError(f"Unknown provider: {provider}")

        filepath = self.vault_path / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Session exported to: {filepath}")
        return filepath

    def create_daily_summary(self, sessions: List[Dict]) -> Path:
        """Create a daily summary of all sessions"""
        date = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# QA Research Daily Summary - {date}

**Generated:** {timestamp}
**Sessions:** {len(sessions)}

## Session Overview

"""

        for i, session in enumerate(sessions, 1):
            provider = session.get('provider', 'unknown')
            summary = session.get('summary', 'No summary')
            content += f"### Session {i}: {provider.title()}\n"
            content += f"{summary}\n\n"

        content += """## Key Takeaways

## Action Items

## Research Progress

---
*Auto-generated daily summary from QA Bob-iverse*
*Tags: #qa-research #daily-summary #ai-sessions*
"""

        filename = f"Daily_Summary_{date}.md"
        filepath = self.vault_path / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Daily summary created: {filepath}")
        return filepath

def main():
    """Main CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description="QA Chat Closeout Protocol")
    parser.add_argument("provider", choices=["claude", "gemini", "codex"],
                       help="AI provider")
    parser.add_argument("--vault", help="Obsidian vault path")
    parser.add_argument("--summary", help="Session summary")
    parser.add_argument("--transcript", help="Path to transcript file")
    parser.add_argument("--interactive", action="store_true",
                       help="Interactive mode for session details")

    args = parser.parse_args()

    closeout = ChatCloseout(args.vault)

    session_data = {}

    if args.interactive:
        print("🤖 QA Chat Closeout Protocol")
        print("Enter session details (press Enter for defaults):")

        session_data['summary'] = input("Session summary: ") or args.summary or "Session summary not provided"
        session_data['type'] = input("Session type (development/reasoning/coding): ") or "development"
        session_data['decisions'] = input("Key decisions made: ") or "- None recorded"
        session_data['changes'] = input("Code/proof changes: ") or "- None recorded"
        session_data['next_steps'] = input("Next steps identified: ") or "- None identified"

        if args.transcript:
            with open(args.transcript, 'r', encoding='utf-8') as f:
                session_data['transcript'] = f.read()
        else:
            session_data['transcript'] = "Transcript not provided"

    else:
        # Use provided args or defaults
        session_data['summary'] = args.summary or "Session summary not provided"
        session_data['transcript'] = "Transcript not provided"
        if args.transcript:
            with open(args.transcript, 'r', encoding='utf-8') as f:
                session_data['transcript'] = f.read()

    # Export session
    filepath = closeout.export_session(args.provider, session_data)
    print(f"📝 Session archived in Obsidian vault: {filepath}")

if __name__ == "__main__":
    main()
