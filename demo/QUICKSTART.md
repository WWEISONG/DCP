# Quick Start Guide

## Prerequisites Check

Before starting, ensure you have:
- ✅ Python 3.10 or 3.12 installed
- ✅ Node.js 16+ and npm installed
- ✅ Docker and Docker Compose installed
- ✅ sudo access (for Docker commands)

## Quick Start (Two Terminal Windows)

### Terminal 1 - Backend

```bash
cd /mnt/data3/weisong/Haonan/VideoMark/demo
./start_backend.sh
```

Or manually:
```bash
cd demo/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Terminal 2 - Frontend

```bash
cd /mnt/data3/weisong/Haonan/VideoMark/demo
./start_frontend.sh
```

Or manually:
```bash
cd demo/frontend
npm install
npm start
```

## What Happens

1. **Backend starts**:
   - Automatically runs `make build` in `c2pa-python-example/`
   - Automatically runs `make run` to start Docker containers
   - Starts Flask server on `http://localhost:8000` (port 5000 is used by C2PA signer)

2. **Frontend starts**:
   - Opens browser at `http://localhost:3000`
   - Shows drag-and-drop file upload interface

3. **To use**:
   - Drag and drop an image (JPG/JPEG/PNG) or click to select
   - Wait for signing to complete
   - Download the signed file

4. **To stop**:
   - Press `Ctrl+C` in the backend terminal
   - Backend will automatically run `make clean` before shutting down
   - Press `Ctrl+C` in the frontend terminal

## Troubleshooting

- **Backend won't start**: Check that `c2pa-python-example` directory exists at the correct path
- **Docker errors**: Ensure Docker is running and you have sudo permissions
- **Frontend can't connect**: Make sure backend is running on port 8000
- **Port already in use**: Change ports in `app.py` (backend) or `package.json` (frontend)
