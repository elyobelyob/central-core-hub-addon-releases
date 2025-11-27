
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM


ENV LANG=C.UTF-8

# Install runtime deps: shell tools, python3 and paho-mqtt from apk
# Using the distro package avoids pip and PEP 668/system package conflicts
RUN apk add --no-cache bash curl ca-certificates mosquitto-clients jq python3 py3-paho-mqtt py3-requests py3-pip git

# Create a virtual environment and install Python dependencies into it.
# This avoids PEP 668 "externally-managed-environment" errors when the
# base image provides a system-managed Python. Installing into a venv
# is safe and keeps the system Python managed by the distro package
# manager.
COPY requirements.txt /requirements.txt
RUN python3 -m venv /venv \
	&& /venv/bin/pip install --upgrade pip setuptools wheel \
	&& /venv/bin/pip install --no-cache-dir -r /requirements.txt

# Ensure the venv's binaries are used by default for subsequent steps
ENV PATH="/venv/bin:$PATH"

COPY run.sh /run.sh
COPY *.py /
COPY config.json /config.json
RUN chmod +x /run.sh

CMD ["/run.sh"]
