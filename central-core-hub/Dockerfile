
# The base image is pinned by tag, not by digest: Home Assistant rebuilds these
# images for security fixes, and a digest could not be checked offline. To pin
# one, take the digest from `docker buildx imagetools inspect <image>` and put
# `@sha256:...` after the tag in build.yaml and in the release workflow.
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM $BUILD_FROM


ENV LANG=C.UTF-8

# Runtime: bash and ca-certificates (TLS), python3 and pip (for the venv below).
# curl, mosquitto-clients and jq are not used by run.sh or the add-on, so they
# are not installed. git is needed only while pip fetches the central-core-mqtt-shared
# pin from requirements.txt; it is a build dependency and is removed in the same layer.
RUN apk add --no-cache bash ca-certificates python3 py3-pip

# Create a virtual environment and install Python dependencies into it.
# This avoids PEP 668 "externally-managed-environment" errors when the
# base image provides a system-managed Python. Installing into a venv
# is safe and keeps the system Python managed by the distro package
# manager.
COPY requirements.txt /requirements.txt
RUN apk add --no-cache --virtual .build-deps git \
	&& python3 -m venv /venv \
	&& /venv/bin/pip install --upgrade pip setuptools wheel \
	&& /venv/bin/pip install --no-cache-dir -r /requirements.txt \
	&& apk del .build-deps

# Ensure the venv's binaries are used by default for subsequent steps
ENV PATH="/venv/bin:$PATH"

COPY run.sh /run.sh
COPY *.py /
COPY config.json /config.json
RUN chmod +x /run.sh

CMD ["/run.sh"]
