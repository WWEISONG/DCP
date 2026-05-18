FROM python:3.12 AS build

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENTRYPOINT [ "python" ]


FROM build AS app

ENTRYPOINT [ "python", "app.py" ]


FROM build AS client

ENTRYPOINT [ "python", "tests/client.py", "./tests/A.jpg", "-o", "client_volume/signed-images" ]


FROM build AS local-setup

RUN apt-get update \
    && apt-get install -y \
    less \
    jq \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*
# Use BuildKit's TARGETARCH instead of `uname -m`: under BuildKit `uname -m`
# can lie (e.g. report x86_64 on arm64 builders via emulation), which
# previously produced an x86_64 awscli inside an arm64 image and broke
# every awslocal call with a rosetta error.
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"; \
    else \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"; \
    fi; \
    unzip awscliv2.zip; \
    ./aws/install; \
    rm -rf awscliv2.zip aws
RUN python3 -m pip install --upgrade localstack
RUN pip install awscli-local[ver2]

ENTRYPOINT [ "bash", "./local-setup.sh" ]
