FROM mongo:latest

COPY delay.sh /home
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# install python for listener
RUN set -ex ;\
    apt-get update ;\
    apt-get install -y --no-install-recommends \
        net-tools \
        iproute2 \
        iputils-ping \
        dnsutils \
        vim \
        ;\
    rm -rf /var/lib/apt/lists/* ;\
    chmod 777 /home/delay.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]