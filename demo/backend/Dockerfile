# Dockerfile for Flask backend with VINE models support
# Uses conda environment to match the fairimage setup

FROM continuumio/miniconda3:latest

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up conda environment (fairimage)
# Create conda environment with Python 3.10
RUN conda create -n fairimage python=3.10 -y

# Activate conda environment and install dependencies
# Install VINE dependencies (matching the fairimage environment)
RUN /opt/conda/envs/fairimage/bin/pip install --no-cache-dir \
    torch==2.0.1 \
    torchvision==0.15.2 \
    accelerate==0.30.0 \
    transformers==4.43.3 \
    pillow \
    "numpy<2.0" \
    einops==0.8.0 \
    peft==0.11.1 \
    huggingface_hub \
    open-clip-torch==2.26.1 \
    timm \
    opencv-python==4.6.0.66 \
    scipy==1.11.1 \
    tqdm \
    lpips \
    clean-fid \
    datasets==2.20.0 \
    scikit-image \
    scikit-learn && \
    /opt/conda/envs/fairimage/bin/pip install --no-cache-dir \
    "git+https://github.com/openai/CLIP.git" && \
    /opt/conda/envs/fairimage/bin/pip install --no-cache-dir \
    "git+https://github.com/Shilin-LU/VINE.git#subdirectory=diffusers" && \
    /opt/conda/envs/fairimage/bin/pip install --no-cache-dir \
    Flask==3.0.0 \
    flask-cors==4.0.0 \
    Werkzeug==3.0.1

# Copy backend files (build context is parent directory, so use demo/backend/)
COPY demo/backend/requirements.txt /app/backend/requirements.txt
COPY demo/backend/app.py /app/backend/app.py
COPY demo/backend/setup_vine.py /app/backend/setup_vine.py

# Set environment variables
ENV PATH /opt/conda/envs/fairimage/bin:$PATH
ENV CONDA_DEFAULT_ENV fairimage
ENV PYTHONPATH /app/VINE:/app:$PYTHONPATH

# Create necessary directories
RUN mkdir -p /app/backend/uploads /app/backend/outputs

# Expose Flask port
EXPOSE 8000

# Set working directory to backend
WORKDIR /app/backend

# Run the Flask app
CMD ["python", "setup_vine.py"]
