FROM postgres:latest

COPY pg_delay.sh /home
COPY pg_entrypoint.sh /usr/local/bin/pg_entrypoint.sh

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
    chmod 777 /home/pg_delay.sh /usr/local/bin/pg_entrypoint.sh

ENTRYPOINT ["/usr/local/bin/pg_entrypoint.sh"]