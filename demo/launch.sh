#!/usr/bin/env bash
# Launch the DCP backend (API) + a Cloudflare tunnel in a detached tmux session,
# so they survive SSH disconnects. The frontend is served by GitHub Pages, so the
# server only needs to expose the API — the tunnel points straight at Flask :8000.
#
#   Start:   ./demo/launch.sh
#   Attach:  tmux attach -t dcp        (detach again with: Ctrl-b then d)
#   Stop:    tmux kill-session -t dcp
#
# Prereqs: Docker running, the `vine` conda env, and `cloudflared` installed.
set -euo pipefail

REPO="${DCP_REPO:-/mnt/data3/weisong/DCP}"
SESSION=dcp

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session '$SESSION' is already running. Attach with: tmux attach -t $SESSION"
  exit 0
fi

# Window 1 — Flask backend (threaded) on :8000. Set ALLOWED_ORIGINS here if you
# want to lock CORS to the Pages origin instead of the default '*'.
tmux new-session -d -s "$SESSION" -n backend
tmux send-keys -t "$SESSION:backend" \
  "conda activate vine && export ALLOWED_ORIGINS='https://wweisong.github.io' && export PYTHONPATH=$REPO/VINE:$REPO && cd $REPO/demo/backend && python setup_vine.py" C-m

# Window 2 — Cloudflare quick tunnel -> Flask :8000 (API only)
tmux new-window -t "$SESSION" -n tunnel
tmux send-keys -t "$SESSION:tunnel" "cloudflared tunnel --url http://localhost:8000" C-m

cat <<MSG

Started tmux session '$SESSION' (windows: backend, tunnel).

  1. Attach and wait for the backend: tmux attach -t $SESSION
     ('backend' window should show: Running on http://0.0.0.0:8000)

  2. Fix .env perms once the backend is up (C2PA signing needs this), in another shell:
       sudo chown weisong:weisong $REPO/c2pa-python-example/local_volume/.env
       sudo chmod 644 $REPO/c2pa-python-example/local_volume/.env

  3. Copy the https://*.trycloudflare.com URL from the 'tunnel' window into GitHub:
       repo Settings -> Secrets and variables -> Actions -> Variables -> REACT_APP_API_URL
     then run the "Deploy frontend to GitHub Pages" workflow once.

  Share https://wweisong.github.io/DCP/  (never goes down — only the demo
  buttons depend on the tunnel).

  Detach without stopping: Ctrl-b then d
MSG
