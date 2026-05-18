# C2PA Docker Deployment Guide

This guide explains how to deploy the C2PA Docker environment with backend API access for frontend integration.

## Architecture

```
Frontend → Backend API (Port 8000) → C2PA Signer Service (Port 5000) → LocalStack (Port 4566)
```

## Prerequisites

- Docker and Docker Compose installed
- At least 4GB of available RAM
- Ports 8000, 5001, and 4566 available (or configure custom ports)

## Quick Start

### 1. Start All Services

From the `c2pa-python-example` directory:

```bash
docker compose up -d
```

This will start:
- **Backend API** (port 8000) - Your frontend should connect here
- **C2PA Signer Service** (port 5001) - Internal signing service
- **LocalStack** (port 4566) - Mock AWS services
- **Setup Container** - One-time setup that exits after completion

### 2. Verify Services are Running

Check service status:

```bash
docker compose ps
```

All services should show as "Up" or "Healthy".

### 3. Test the Backend API

Test the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "c2pa_service": "available",
  "c2pa_url": "http://signer:5000"
}
```

### 4. Sign an Image via Backend API

```bash
curl -X POST \
  http://localhost:8000/api/c2pa/attach \
  -F "file=@path/to/your/image.jpg" \
  -o signed_image.jpg
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory to customize ports:

```env
# Backend API port (accessible from frontend)
BACKEND_PORT=8000

# C2PA Signer service external port
C2PA_PORT=5001

# LocalStack port
LOCALSTACK_PORT=4566
```

### Port Configuration

If you need to change ports, update `docker-compose.yaml`:

```yaml
backend:
  ports:
    - "YOUR_PORT:8000"  # Change YOUR_PORT to desired port

signer:
  ports:
    - "YOUR_PORT:5000"  # Change YOUR_PORT to desired port
```

## Frontend Integration

### API Base URL

Your frontend should use the backend API URL:

```
http://localhost:8000/api/c2pa
```

### Example Frontend Code

See `backend/README.md` for detailed frontend integration examples.

### CORS Configuration

The backend has CORS enabled for all origins. For production, you may want to restrict this:

Edit `backend/app.py`:

```python
CORS(app, origins=["http://your-frontend-domain.com"])
```

## Service Endpoints

### Backend API (Port 8000)

- `GET /health` - Health check
- `POST /api/c2pa/attach` - Sign an image
- `GET /api/c2pa/signer_data` - Get signer information
- `POST /api/c2pa/sign` - Sign raw data

### C2PA Signer Service (Port 5001)

- `GET /health` - Health check
- `POST /attach` - Sign an image (direct access)
- `GET /signer_data` - Get signer data (direct access)
- `POST /sign` - Sign data (direct access)

## Monitoring

### View Logs

View all service logs:

```bash
docker compose logs -f
```

View specific service logs:

```bash
docker compose logs -f backend
docker compose logs -f signer
```

### Check Service Health

```bash
# Backend health
curl http://localhost:8000/health

# C2PA service health (direct)
curl http://localhost:5001/health
```

## Troubleshooting

### Services Won't Start

1. Check Docker is running:
   ```bash
   docker ps
   ```

2. Check port availability:
   ```bash
   netstat -tuln | grep -E '8000|5001|4566'
   ```

3. View error logs:
   ```bash
   docker compose logs
   ```

### Backend Can't Connect to C2PA Service

1. Verify signer service is healthy:
   ```bash
   docker compose ps signer
   ```

2. Check network connectivity:
   ```bash
   docker compose exec backend curl http://signer:5000/health
   ```

### Frontend Can't Connect to Backend

1. Verify backend is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check CORS configuration in `backend/app.py`

3. Verify firewall settings allow connections to port 8000

### Setup Container Fails

The setup container runs once to configure certificates and AWS resources. If it fails:

1. Check setup logs:
   ```bash
   docker compose logs setup
   ```

2. Restart setup:
   ```bash
   docker compose up setup
   ```

## Stopping Services

Stop all services:

```bash
docker compose down
```

Stop and remove volumes (clean slate):

```bash
docker compose down -v
```

## Production Considerations

⚠️ **This setup is for development only!**

For production deployment:

1. **Security:**
   - Use real AWS KMS instead of LocalStack
   - Implement proper authentication/authorization
   - Restrict CORS to specific domains
   - Use HTTPS/TLS

2. **Certificates:**
   - Use real certificates from a trusted CA
   - Don't use self-signed certificates

3. **Configuration:**
   - Use environment variables for sensitive data
   - Don't commit `.env` files to version control
   - Use secrets management (AWS Secrets Manager, etc.)

4. **Scaling:**
   - Consider using a reverse proxy (nginx, traefik)
   - Implement load balancing if needed
   - Use container orchestration (Kubernetes, ECS)

5. **Monitoring:**
   - Add logging aggregation
   - Implement health checks
   - Set up alerting

## Development Workflow

1. **Make changes to backend:**
   ```bash
   # Edit backend/app.py
   docker compose build backend
   docker compose up -d backend
   ```

2. **Make changes to C2PA service:**
   ```bash
   # Edit app.py or other files
   docker compose build signer
   docker compose up -d signer
   ```

3. **View logs while developing:**
   ```bash
   docker compose logs -f backend signer
   ```

## Additional Resources

- [C2PA Python Example README](README.md)
- [Backend API Documentation](backend/README.md)
- [C2PA Specification](https://c2pa.org/)
- [Flask Documentation](https://flask.palletsprojects.com/)
