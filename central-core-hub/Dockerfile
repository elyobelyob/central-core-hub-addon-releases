ARG BUILD_FROM=alpine:3.18
FROM ${BUILD_FROM}

ENV LANG C.UTF-8

RUN apk add --no-cache bash curl ca-certificates

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
