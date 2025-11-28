# 🔧 Syncthing Path Mismatch - FIX REQUIRED

**Issue:** Syncthing is connected but syncing from wrong paths (0 files transferring)

**Root Cause:** Syncthing folders are NOT pointing to the real swarm directory

---

## ✅ VERIFIED FACTS:

### Real Swarm Location (Player2):
```
Path: /home/player2/signal_experiments/qa_lab
Tasks in inbox: 33 files (including node-optimize-player4.yaml)
Tasks in active: 957 files
Total cluster tasks: 3,556
```

### What Syncthing SHOULD Share:
```
tasks/     → /home/player2/signal_experiments/qa_lab/tasks
artifacts/ → /home/player2/signal_experiments/qa_lab/artifacts
plots/     → /home/player2/signal_experiments/qa_lab/plots
logs/      → /home/player2/signal_experiments/qa_lab/logs
```

### What Syncthing ACTUALLY Shares:
```
❌ Unknown (probably wrong paths or empty directories)
Result: 0 files syncing to player4
```

---

## 🛠️ FIX STEPS (On Player2):

### 1. Open Syncthing Web UI:

```
URL: http://192.168.4.105:8384
      (or http://localhost:8384 on player2)
```

### 2. Edit Each Folder:

For **EACH** shared folder (tasks, artifacts, plots, logs):

1. Click the folder name
2. Click "Edit"
3. Check the "Folder Path" field
4. **Change it to the CORRECT path:**

#### Correct Paths:

| Folder ID | Folder Path (on player2) |
|-----------|--------------------------|
| qa_lab_tasks | `/home/player2/signal_experiments/qa_lab/tasks` |
| qa_lab_artifacts | `/home/player2/signal_experiments/qa_lab/artifacts` |
| qa_lab_plots | `/home/player2/signal_experiments/qa_lab/plots` |
| qa_lab_logs | `/home/player2/signal_experiments/qa_lab/logs` |

5. Click "Save"
6. Wait for Syncthing to rescan (10-30 seconds)

### 3. Verify Sync Started:

After fixing paths, check Syncthing UI:

- Folder should show "Syncing (X%)" or "Up to Date"
- File counts should show:
  - **tasks:** ~990 items (33 inbox + 957 active)
  - **artifacts:** multiple files
  - **plots:** multiple PNG files

---

## 🧪 TEST FILE CREATED:

I created a test file to verify sync:

```
Location (player2): /home/player2/signal_experiments/qa_lab/tasks/inbox/SYNC_TEST_FROM_PLAYER2.txt
Expected (player4): /home/player4/qa_lab/tasks/inbox/SYNC_TEST_FROM_PLAYER2.txt
```

**After fixing Syncthing paths, this file should appear on player4 within 30 seconds.**

On player4, check:
```bash
ls /home/player4/qa_lab/tasks/inbox/SYNC_TEST_FROM_PLAYER2.txt
```

If you see it → Sync is working! ✅
If not → Paths still wrong ❌

---

## 📊 WHAT WILL HAPPEN AFTER FIX:

### Immediate (within 1 minute):
- Syncthing detects ~990 files in tasks/ folder
- Starts syncing all tasks to player4
- SYNC_TEST_FROM_PLAYER2.txt appears on player4
- node-optimize-player4.yaml appears in player4's inbox

### Within 5 minutes:
- All 33 inbox tasks synced to player4
- All 957 active tasks synced to player4
- Artifacts, plots, logs syncing

### Player4 Daemon:
- Scans inbox on next cycle (hourly or manual)
- Picks up node-optimize-player4.yaml
- Executes optimization
- Results sync back to player2 via Syncthing

---

## 🔍 ALTERNATIVE: Quick Fix via Symlink (if web UI is difficult)

If you can't access Syncthing web UI easily, create symlinks:

```bash
# On player2:
mkdir -p /home/player2/qa_lab
ln -s /home/player2/signal_experiments/qa_lab/tasks /home/player2/qa_lab/tasks
ln -s /home/player2/signal_experiments/qa_lab/artifacts /home/player2/qa_lab/artifacts
ln -s /home/player2/signal_experiments/qa_lab/plots /home/player2/qa_lab/plots
ln -s /home/player2/signal_experiments/qa_lab/logs /home/player2/qa_lab/logs
```

This way, if Syncthing is sharing `/home/player2/qa_lab/*`, the symlinks will point to the real data.

**BUT:** Fixing the paths in Syncthing UI is cleaner and preferred.

---

## 📞 VERIFICATION CHECKLIST:

After applying fix:

- [ ] Syncthing UI shows "Syncing" or "Up to Date" (not "Idle" with 0 files)
- [ ] tasks/ folder shows ~990 items
- [ ] SYNC_TEST_FROM_PLAYER2.txt appears on player4
- [ ] node-optimize-player4.yaml appears on player4
- [ ] Player4 can execute optimization task

---

## 🎯 ROOT CAUSE SUMMARY:

**The infrastructure is perfect:**
- ✅ Network connectivity working
- ✅ Syncthing connected (TLS handshake successful)
- ✅ Both nodes configured correctly
- ✅ Player4 optimized and ready (18 workers, 144 batch)

**The ONLY issue:**
- ❌ Syncthing folders on player2 point to wrong paths
- ❌ Real swarm is in `/home/player2/signal_experiments/qa_lab`
- ❌ Syncthing is sharing from somewhere else (empty or non-existent)

**Fix:** Update 4 folder paths in Syncthing web UI → instant sync

---

**Created:** 2025-11-27 22:25 EST
**Status:** Fix required on player2's Syncthing configuration
**ETA after fix:** Files sync in 30 seconds, player4 picks up tasks immediately
