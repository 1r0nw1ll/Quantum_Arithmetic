#!/bin/bash
#
# QA Swarm Node Installer
# Deploys a QA Lab compute node that connects to the primary swarm
#
# Usage:
#   On player4: bash install_swarm_node.sh player2 /path/to/qa_lab
#
# This script:
#   1. Clones the QA Lab repository
#   2. Sets up Python virtual environment
#   3. Installs dependencies
#   4. Configures Syncthing for state sync
#   5. Sets up compute-node agent loop
#   6. Launches swarm daemon
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PRIMARY_NODE="${1:-player2}"
INSTALL_DIR="${2:-$HOME/qa_lab}"
SYNC_METHOD="${3:-syncthing}"  # syncthing or nfs

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   QA Swarm Multi-Node Expansion Installer     ║${NC}"
echo -e "${BLUE}║   Transforming into Distributed Organism      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Primary Node:${NC} $PRIMARY_NODE"
echo -e "${GREEN}Install Directory:${NC} $INSTALL_DIR"
echo -e "${GREEN}Sync Method:${NC} $SYNC_METHOD"
echo ""

# Check if running on primary node
HOSTNAME=$(hostname)
if [ "$HOSTNAME" = "$PRIMARY_NODE" ]; then
    echo -e "${RED}ERROR: This script should run on a SECONDARY node (player4), not the primary node!${NC}"
    echo -e "${YELLOW}Run this script on player4, not player2.${NC}"
    exit 1
fi

# Step 1: Check prerequisites
echo -e "${YELLOW}[1/8]${NC} Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}ERROR: python3 required${NC}"; exit 1; }
command -v git >/dev/null 2>&1 || { echo -e "${RED}ERROR: git required${NC}"; exit 1; }
echo -e "${GREEN}✓${NC} Prerequisites OK"

# Step 2: Clone or sync repository
echo -e "${YELLOW}[2/8]${NC} Setting up QA Lab codebase..."
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Directory exists. Updating...${NC}"
    cd "$INSTALL_DIR"
    git pull || echo "Not a git repo, will sync via $SYNC_METHOD"
else
    echo -e "${YELLOW}Cloning from primary node...${NC}"
    # Try to clone via SSH from primary
    if ssh "$PRIMARY_NODE" "test -d ~/qa_lab/.git"; then
        git clone "ssh://${PRIMARY_NODE}/~/qa_lab" "$INSTALL_DIR" || {
            echo -e "${YELLOW}Git clone failed, will use direct copy${NC}"
            mkdir -p "$INSTALL_DIR"
            scp -r "${PRIMARY_NODE}:~/qa_lab/*" "$INSTALL_DIR/" || {
                echo -e "${RED}ERROR: Cannot access primary node${NC}"
                exit 1
            }
        }
    else
        mkdir -p "$INSTALL_DIR"
        echo -e "${YELLOW}Copying codebase from primary...${NC}"
        scp -r "${PRIMARY_NODE}:~/qa_lab/*" "$INSTALL_DIR/" || {
            echo -e "${RED}ERROR: Cannot copy from primary node${NC}"
            exit 1
        }
    fi
fi
cd "$INSTALL_DIR"
echo -e "${GREEN}✓${NC} Codebase ready"

# Step 3: Create Python virtual environment
echo -e "${YELLOW}[3/8]${NC} Setting up Python virtual environment..."
if [ ! -d "qa_venv" ]; then
    python3 -m venv qa_venv
fi
source qa_venv/bin/activate
pip install --upgrade pip wheel
echo -e "${GREEN}✓${NC} Virtual environment ready"

# Step 4: Install dependencies
echo -e "${YELLOW}[4/8]${NC} Installing dependencies..."
# Install from requirements if it exists
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    # Install common dependencies
    pip install pyyaml numpy matplotlib torch tqdm scipy
fi
echo -e "${GREEN}✓${NC} Dependencies installed"

# Step 5: Setup sync method
echo -e "${YELLOW}[5/8]${NC} Setting up state synchronization ($SYNC_METHOD)..."

if [ "$SYNC_METHOD" = "syncthing" ]; then
    # Install Syncthing
    if ! command -v syncthing &> /dev/null; then
        echo -e "${YELLOW}Installing Syncthing...${NC}"
        sudo apt-get update
        sudo apt-get install -y syncthing
    fi

    # Create sync directories
    mkdir -p tasks/{inbox,active,completed,rejected}
    mkdir -p artifacts/{evals,proofs,ingestion,overleaf}
    mkdir -p plots logs

    # Start Syncthing (will run in background)
    echo -e "${YELLOW}Starting Syncthing...${NC}"
    syncthing &
    SYNCTHING_PID=$!
    sleep 5

    echo -e "${GREEN}✓${NC} Syncthing installed"
    echo -e "${BLUE}📋 MANUAL STEP REQUIRED:${NC}"
    echo "   1. Open http://localhost:8384 on this machine"
    echo "   2. Open http://${PRIMARY_NODE}:8384 on primary node"
    echo "   3. Add folders to sync: tasks/, artifacts/, plots/, logs/"
    echo "   4. Connect the two Syncthing instances"
    echo ""
    echo -e "${YELLOW}Press Enter when Syncthing is configured...${NC}"
    read

elif [ "$SYNC_METHOD" = "nfs" ]; then
    echo -e "${YELLOW}Setting up NFS mount...${NC}"

    # Install NFS client
    if ! command -v mount.nfs &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y nfs-common
    fi

    # Create mount point
    sudo mkdir -p "$INSTALL_DIR"

    # Mount from primary
    echo -e "${YELLOW}Mounting shared directory from $PRIMARY_NODE...${NC}"
    sudo mount "${PRIMARY_NODE}:${INSTALL_DIR}" "$INSTALL_DIR" || {
        echo -e "${RED}ERROR: NFS mount failed${NC}"
        echo "Make sure NFS server is running on $PRIMARY_NODE"
        echo "Run this on $PRIMARY_NODE:"
        echo "  sudo apt install nfs-kernel-server"
        echo "  sudo mkdir -p /export/qa_lab"
        echo "  sudo mount --bind ~/qa_lab /export/qa_lab"
        echo "  echo '/export/qa_lab *(rw,sync,no_subtree_check)' | sudo tee -a /etc/exports"
        echo "  sudo systemctl restart nfs-kernel-server"
        exit 1
    }

    # Add to /etc/fstab for persistence
    echo "${PRIMARY_NODE}:${INSTALL_DIR} ${INSTALL_DIR} nfs defaults 0 0" | sudo tee -a /etc/fstab

    echo -e "${GREEN}✓${NC} NFS mount configured"
fi

# Step 6: Configure as compute node
echo -e "${YELLOW}[6/8]${NC} Configuring as compute node..."

# Create compute node Makefile override
cat > Makefile.node <<'EOF'
# QA Swarm Compute Node Configuration
# This node focuses on execution, not coordination

.PHONY: node-agent-loop

# Compute node only runs execution stages
node-agent-loop:
	@echo "🖥️  QA Compute Node: Starting agent loop..."
	@echo "📥 Checking for assigned tasks..."
	$(PYTHON) qa_agents/cli/executor.py || true
	@echo "👀 Reviewing completed work..."
	$(PYTHON) qa_agents/cli/reviewer.py || true
	@echo "🦀 Running Rust benchmarks..."
	$(MAKE) port-rust-all || true
	@echo "📊 Generating local metrics..."
	$(PYTHON) qa_fast_eval.py || true
	@echo "✅ Compute node cycle complete"

# Daemon for compute node (1-hour cycles)
node-daemon:
	@echo "🔁 Starting compute node daemon (Ctrl+C to stop)..."
	@while true; do \
		$(MAKE) -f Makefile.node node-agent-loop || true; \
		sleep 3600; \
	done
EOF

echo -e "${GREEN}✓${NC} Compute node configuration created"

# Step 7: Create node identity file
echo -e "${YELLOW}[7/8]${NC} Creating node identity..."
cat > .node_config.json <<EOF
{
  "node_type": "compute",
  "node_id": "$HOSTNAME",
  "primary_node": "$PRIMARY_NODE",
  "sync_method": "$SYNC_METHOD",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "capabilities": [
    "executor",
    "reviewer",
    "rust_benchmarks",
    "metrics_generation"
  ]
}
EOF
echo -e "${GREEN}✓${NC} Node identity created"

# Step 8: Launch daemon
echo -e "${YELLOW}[8/8]${NC} Launching swarm daemon..."

# Create systemd service for automatic startup
cat > /tmp/qa-swarm-node.service <<EOF
[Unit]
Description=QA Lab Swarm Compute Node
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/qa_venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/make -f $INSTALL_DIR/Makefile.node node-daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/qa-swarm-node.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable qa-swarm-node
sudo systemctl start qa-swarm-node

echo -e "${GREEN}✓${NC} Daemon launched"

# Final summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Installation Complete! 🎉            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Node Type:${NC} Compute Node"
echo -e "${GREEN}Node ID:${NC} $HOSTNAME"
echo -e "${GREEN}Primary Node:${NC} $PRIMARY_NODE"
echo -e "${GREEN}Install Dir:${NC} $INSTALL_DIR"
echo -e "${GREEN}Sync Method:${NC} $SYNC_METHOD"
echo ""
echo -e "${YELLOW}Status:${NC}"
echo "  Daemon: systemctl status qa-swarm-node"
echo "  Logs: journalctl -u qa-swarm-node -f"
echo "  Stop: systemctl stop qa-swarm-node"
echo "  Restart: systemctl restart qa-swarm-node"
echo ""
echo -e "${BLUE}Your QA swarm is now a distributed organism!${NC}"
echo -e "${BLUE}Tasks assigned by $PRIMARY_NODE will execute on this node.${NC}"
echo ""
echo -e "${GREEN}Next: Check the multi-node dashboard on $PRIMARY_NODE${NC}"
echo "  make cluster-dashboard"
echo ""
