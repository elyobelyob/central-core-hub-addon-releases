
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM


ENV LANG=C.UTF-8

# Install runtime deps: shell tools, python3 and paho-mqtt from apk
# Using the distro package avoids pip and PEP 668/system package conflicts
RUN apk add --no-cache bash curl ca-certificates mosquitto-clients jq python3 py3-paho-mqtt py3-requests

COPY run.sh /run.sh
COPY mqtt_client.py /mqtt_client.py
RUN chmod +x /run.sh /mqtt_client.py

CMD ["/run.sh"]
