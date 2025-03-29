FROM postgres:latest

COPY pg-init.sql /docker-entrypoint-initdb.d/pg-init.sql

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
    rm -rf /var/lib/apt/lists/* 


# ENTRYPOINT ["/usr/local/bin/pg_dmix_entrypoint.sh"]