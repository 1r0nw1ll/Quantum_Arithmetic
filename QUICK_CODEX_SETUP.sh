#!/bin/bash
# Quick setup for Codex collaboration

echo "🔧 Setting up Codex collaboration..."
echo ""

# Get absolute paths
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📝 Add these to your environment:"
echo ""
echo "export COLLAB_BROADCAST_CMD=\"$BASE_DIR/collab_broadcast\""
echo "export COLLAB_GET_STATE_CMD=\"$BASE_DIR/collab_get_state\""
echo "export COLLAB_SET_STATE_CMD=\"$BASE_DIR/collab_set_state\""
echo ""

echo "✅ Or run this to set them now:"
echo ""
echo "source <(cat << 'ENVEOF'
export COLLAB_BROADCAST_CMD=\"$BASE_DIR/collab_broadcast\"
export COLLAB_GET_STATE_CMD=\"$BASE_DIR/collab_get_state\"
export COLLAB_SET_STATE_CMD=\"$BASE_DIR/collab_set_state\"
ENVEOF
)"
echo ""

echo "🧪 Test with:"
echo "  echo '{\"event_type\": \"codex.test\", \"data\": {\"message\": \"Hello!\"}}' | \$COLLAB_BROADCAST_CMD"
echo ""

echo "🚀 Then run your agents:"
echo "  make scout"
echo "  make agent_loop"
echo ""

echo "👂 I'll be listening with:"
echo "  python3 listen_codex_events.py"
