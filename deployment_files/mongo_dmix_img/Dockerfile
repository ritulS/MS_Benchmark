FROM mongo:latest


COPY mongo_dmix_entrypoint.sh /usr/local/bin/mongo_dmix_entrypoint.sh

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
    chmod 777 /usr/local/bin/mongo_dmix_entrypoint.sh

ENTRYPOINT ["/usr/local/bin/mongo_dmix_entrypoint.sh"]