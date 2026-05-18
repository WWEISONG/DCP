# C2PA File Signing Demo

This demo application provides a web interface for signing image files with C2PA credentials. It consists of a Flask backend and a React frontend.

## Structure

```
demo/
├── backend/          # Flask backend server
│   ├── app.py        # Main Flask application
│   └── requirements.txt
└── frontend/         # React frontend application
    ├── src/
    ├── public/
    └── package.json
```

## Features

- **Automatic Docker Setup**: Backend automatically builds and runs Docker containers on startup
- **Automatic Cleanup**: Backend runs cleanup command on shutdown
- **File Upload**: Drag-and-drop interface for uploading image files
- **C2PA Signing**: Automatically signs uploaded files using the C2PA Python example client
- **File Download**: Download signed files directly from the web interface

## Prerequisites

- Python 3.10 or 3.12
- Node.js 16+ and npm
- Docker and Docker Compose
- sudo access (required for Docker commands)

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
```bash
cd demo/backend
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd demo/frontend
```

2. Install dependencies:
```bash
npm install
```

## Running the Application

### Start the Backend

1. Make sure you're in the backend directory:
```bash
cd demo/backend
```

2. Activate your virtual environment (if using one):
```bash
source venv/bin/activate
```

3. Run the Flask server:
```bash
python app.py
```

The backend will:
- Automatically run `make build` and `make run` from the `c2pa-python-example` directory
- Start the Flask server on `http://localhost:8000` (port 5000 is used by the C2PA signer service)
- On shutdown (Ctrl+C), automatically run `make clean`

### Start the Frontend

1. Open a new terminal and navigate to the frontend directory:
```bash
cd demo/frontend
```

2. Start the React development server:
```bash
npm start
```

The frontend will start on `http://localhost:3000` and automatically open in your browser.

## Usage

1. Open the web interface at `http://localhost:3000`
2. Drag and drop an image file (JPG, JPEG, or PNG) into the upload area, or click to select a file
3. Wait for the file to be uploaded and signed (this may take a few moments)
4. Once complete, click the "Download Signed File" button to download the signed image

## API Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

### `POST /upload`
Upload and sign an image file.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: file (image file)

**Response:**
```json
{
  "message": "File signed successfully",
  "filename": "signed_image.jpg",
  "download_url": "/download/file_id/signed_image.jpg"
}
```

### `GET /download/<file_id>/<filename>`
Download a signed file.

**Response:**
- File download

## Troubleshooting

### Backend Issues

- **Docker permission errors**: Make sure you have sudo access and are in the docker group, or run with sudo
- **Makefile not found**: Ensure the `c2pa-python-example` directory exists at the correct relative path
- **Port 8000 already in use**: Change the port in `app.py` or stop the process using port 8000

### Frontend Issues

- **Cannot connect to backend**: Make sure the backend is running on `http://localhost:8000`
- **CORS errors**: The backend has CORS enabled, but if issues persist, check the CORS configuration in `app.py`

### Docker Issues

- **Containers not starting**: Check Docker is running and you have sufficient permissions
- **Build failures**: Ensure all dependencies in `c2pa-python-example` are properly configured

## Notes

- The backend requires sudo access to run Docker commands
- File uploads are limited to 10MB by default
- Only JPG, JPEG, and PNG image formats are supported
- Signed files are stored in `demo/backend/outputs/`
- Uploaded files are temporarily stored in `demo/backend/uploads/`
