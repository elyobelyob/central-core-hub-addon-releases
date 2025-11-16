# Home Assistant Add-on DevContainer
FROM mcr.microsoft.com/vscode/devcontainers/base:ubuntu-22.04

# Install Docker CLI, Home Assistant CLI, and other tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    docker.io \
    curl \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Home Assistant CLI
RUN pip3 install --no-cache-dir homeassistant-cli

# Create a non-root user (VS Code default)
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME
USER $USERNAME
WORKDIR /workspace
