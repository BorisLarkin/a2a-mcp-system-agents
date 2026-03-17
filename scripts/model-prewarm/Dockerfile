FROM alpine:latest

RUN apk add --no-cache curl

COPY prewarm.sh /prewarm.sh
RUN chmod +x /prewarm.sh

CMD ["/prewarm.sh"]