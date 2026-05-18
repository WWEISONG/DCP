# Docker Setup for VideoMark Backend

This guide explains how to run the VideoMark backend in Docker using a conda environment that matches the `fairimage` setup.

## Prerequisites

- Docker and Docker Compose installed
- At least 8GB of available RAM (for VINE models)
- GPU support (optional but recommended for VINE models)

## Quick Start

### 1. Build and Run with Docker Compose

From the `demo` directory:

```bash
cd /mnt/data3/weisong/Haonan/VideoMark/demo
docker compose up --build
```

Note: Use `docker compose` (without hyphen) - this is the modern Docker Compose V2 command. If you have the older version, use `docker-compose` instead.

This will:
- Build the Docker image with conda environment `fairimage`
- Install all VINE dependencies
- Start the Flask backend on port 8000

### 2. Build Docker Image Manually

```bash
cd /mnt/data3/weisong/Haonan/VideoMark/demo
docker build -f backend/Dockerfile -t videomark-backend:latest ..
```

### 3. Run Docker Container

```bash
docker run -d \
  --name videomark-backend \
  -p 8000:8000 \
  -v /mnt/data3/weisong/Haonan/VideoMark/VINE:/app/VINE:ro \
  -v /mnt/data3/weisong/Haonan/VideoMark/c2pa-python-example:/app/c2pa-python-example:ro \
  videomark-backend:latest
```

## Docker Compose Configuration

The `docker-compose.yaml` file includes:

- **Backend service**: Flask backend with VINE models
- **Volume mounts**: 
  - VINE directory (read-only)
  - C2PA directory (read-only)
  - Backend directory (for development)

## GPU Support

To enable GPU support, uncomment the GPU section in `docker-compose.yaml`:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

And ensure you have `nvidia-docker2` installed:

```bash
# Install nvidia-docker2
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

## Environment Variables

The Docker container uses:
- `CONDA_DEFAULT_ENV=fairimage`: Conda environment name
- `PYTHONPATH=/app/VINE:/app`: Python path for VINE imports

## Troubleshooting

### Container won't start
- Check Docker logs: `docker logs videomark-backend`
- Verify volumes are mounted correctly
- Ensure ports 8000 is available

### VINE models not loading
- Check that VINE directory is mounted: `docker exec videomark-backend ls -la /app/VINE`
- Verify conda environment: `docker exec videomark-backend conda env list`
- Check Python path: `docker exec videomark-backend python -c "import sys; print(sys.path)"`

### Out of memory
- VINE models require significant RAM/VRAM
- Reduce batch size or use CPU mode (slower)
- Ensure Docker has enough memory allocated

## Development Mode

For development, the backend directory is mounted as a volume, so code changes are reflected immediately. Restart the container to apply changes:

```bash
docker-compose restart backend
```

## Production Mode

For production, comment out the backend volume mount in `docker-compose.yaml` to use the code baked into the image.
