FROM postgres:latest

# install python for listener
RUN set -ex && \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        net-tools \
        iproute2 \
        iputils-ping \
        dnsutils \
        vim \
        pgbouncer && \
    rm -rf /var/lib/apt/lists/* 
    # chmod 777 /home/pg_delay.sh /usr/local/bin/pg_entrypoint.sh

# Copy SQL and scripts
COPY pg-init.sql /docker-entrypoint-initdb.d/pg-init.sql
COPY pg_delay.sh /home
COPY pg_entrypoint.sh /usr/local/bin/pg_entrypoint.sh

# Copy PgBouncer config files
RUN rm -f /etc/pgbouncer/pgbouncer.ini
COPY pgbouncer.ini /etc/pgbouncer/pgbouncer.ini
COPY userlist.txt /etc/pgbouncer/userlist.txt

RUN chmod 777 /home/pg_delay.sh /usr/local/bin/pg_entrypoint.sh

ENTRYPOINT ["/usr/local/bin/pg_entrypoint.sh"]