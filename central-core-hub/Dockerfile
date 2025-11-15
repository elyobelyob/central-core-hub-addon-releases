ARG BUILD_FROM=alpine:3.18
ARG BUILD_ARCH
ARG BUILD_VERSION=1.0.1
FROM ${BUILD_FROM}

ENV LANG C.UTF-8

# Add labels expected by Supervisor / Home Assistant
LABEL io.hass.version="${BUILD_VERSION}"
LABEL io.hass.type="addon"
LABEL io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache bash curl ca-certificates

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
