# Digital Content Protector (DCP)

A research demo from **UNSW CSE** and **CSIRO Data61** that combines two
content-authenticity techniques over a single image:

- **C2PA** — cryptographic provenance metadata embedded in the file.
- **Invisible neural watermarking** — a recoverable payload encoded into the pixels themselves.

The web app exposes both pipelines end-to-end: sign, watermark, verify, and
simulated attacker scenarios (tamper image bytes, tamper manifest fields, add
noise, aggressive JPEG re-compression).

The marketing/docs site is hosted on **GitHub Pages**. The interactive demo
talks to a Flask backend that you run on your own server.

---

## Repository layout

```
.
├── demo/
│   ├── frontend/             # React app — deployed to GitHub Pages
│   └── backend/              # Flask API — deployed to your own server
├── c2pa-python-example/      # Adobe's reference C2PA stack (docker-compose)
├── .github/workflows/
│   └── deploy-pages.yml      # CI that ships the frontend to Pages on push
└── README.md
```

Two third-party dependencies are **not** vendored in this repo (too large,
upstream-managed):

- `VINE/` — the invisible-watermark model. Clone beside this repo:
  `git clone https://github.com/Shilin-LU/VINE.git ../VINE`
- `c2patool/` — Adobe's pre-built C2PA CLI (optional fallback for manifest
  reads). Download from <https://github.com/contentauth/c2patool/releases> and
  put the binary in your `PATH`.

---

## Local development

### Backend

```bash
conda create -n dcp python=3.10 -y
conda activate dcp
cd demo/backend
pip install -r requirements.txt
# also install VINE's dependencies — see VINE/environment.yaml
python setup_vine.py
```

The backend bootstraps the C2PA Docker stack (`c2pa-python-example/`) on
startup, then serves the API on port 8000.

### Frontend

```bash
cd demo/frontend
npm install
npm start
```

Opens <http://localhost:3000>. By default it talks to <http://localhost:8000>.
Override with `REACT_APP_API_URL=https://your-backend npm start`.

---

## Production deployment

### 1) Frontend → GitHub Pages

This repo ships a workflow that builds the React app and publishes to Pages
on every push to `main`.

**One-time setup:**

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Settings → Secrets and variables → Actions → Variables → New repository variable:**
   - Name: `REACT_APP_API_URL`
   - Value: the public HTTPS URL of your backend (e.g. `https://dcp-backend.cse.unsw.edu.au`).

Push to `main` and the workflow at `.github/workflows/deploy-pages.yml` will:

1. Install Node 20 and the frontend dependencies.
2. Run `npm run build` with `REACT_APP_API_URL` injected.
3. Upload the build folder as a Pages artefact and publish it.

The site goes live at `https://<your-username>.github.io/<repo-name>/`. Re-run
the workflow (Actions → Deploy frontend to GitHub Pages → Run workflow) if you
change the repo variable, since CRA bakes env vars in at build time.

### 2) Backend → UNSW / CSIRO server

The backend needs:

- Linux with Docker + Docker Compose installed
- ≥ 4 GB RAM (model + diffusers in memory)
- A public hostname and HTTPS (browsers block HTTP from the Pages site)
- Ports 80 / 443 reachable, or sit behind your group's reverse proxy

A minimal deployment on a fresh Ubuntu VM:

```bash
# clone the repo + the VINE submodule beside it
git clone https://github.com/<your-org>/<repo>.git
cd <repo>
git clone https://github.com/Shilin-LU/VINE.git ../VINE

# install the Python env
cd demo/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# (install VINE's deps — refer to ../VINE/environment.yaml)

# lock CORS to your Pages origin (recommended)
export ALLOWED_ORIGINS="https://<your-username>.github.io"

# run the backend (foreground, port 8000)
python setup_vine.py
```

In production you'll want it under `systemd` or a process supervisor. Place a
reverse proxy in front of it for HTTPS. **Caddy** is the simplest option —
one-line auto-Let's-Encrypt:

```Caddyfile
dcp-backend.example.com {
    reverse_proxy localhost:8000
}
```

Then point your Pages site at it by setting the
`REACT_APP_API_URL` repo variable to `https://dcp-backend.example.com` and
re-running the deploy workflow.

### CORS

By default the backend allows all origins (development-friendly). For
production, set `ALLOWED_ORIGINS` to the exact Pages URL:

```bash
ALLOWED_ORIGINS="https://your-username.github.io"
```

Comma-separate to allow multiple origins.

---

## Credits

- Frontend & backend: this repo.
- C2PA stack: [contentauth / c2pa-python-example](https://github.com/contentauth/c2pa-python-example).
- Watermarking: [Shilin-LU / VINE](https://github.com/Shilin-LU/VINE).
- Design system inspired by the [SAF project](https://static-analyzer-factory.github.io/static-analyzer-factory/).

Built by Wei Song, Yulei Sui, Zhenchang Xing and Jingling Xue —
UNSW CSE · CSIRO Data61.
