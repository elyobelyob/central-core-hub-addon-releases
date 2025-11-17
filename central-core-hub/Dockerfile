
ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG=C.UTF-8

RUN apk add --no-cache bash curl ca-certificates mosquitto-clients jq

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
