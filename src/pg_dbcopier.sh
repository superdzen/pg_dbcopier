#!/bin/bash


timestamp() {
 date +"%Y-%m-%d %H:%M:%S.%3N"
}


checkerrcode() {
if [ $? -ne 0 ]; then
    echo "$(timestamp) ERROR: last command error. Check log files."
    echo "--------------------------------------------------------------------------------"
    exit 1
fi
}


PG_SERVICE_NAME="postgresql-9.6"
PG_SRC_HOST="db-src"
PG_PORT=5432
PG_USERNAME="replication"
PG_BIN="/usr/pgsql-9.6/bin"
PG_DST_DATA_DIR="/var/lib/pgsql/9.6/data"
PG_DELAY=10
PG_PASSREQUIRED=false

#Usage info fun
usage() {
cat << EOF

Usage: ${0##*/} [OPTION]

Optional:
    -r hostname             Source PostgreSQL hostname for pg_basebackup
                            by default = $PG_SRC_HOST
    -p port_number          Source PostgreSQL hostname port for pg_basebackup
                            by default = $PG_PORT
    -U username             Username for pg_basebackup (customized .pgpass is required)
                            by default = $PG_USERNAME
    -W                      always ask password (for manual launching or if pgpass not customized)
                            by default = $PG_PASSREQUIRED
    -D /dst/data/dir        Destination PostgreSQL data directory
                            by default = $PG_DST_DATA_DIR
    -B /pgsql/bin/dir       cluster executable directory (needed for pg_isready and pg_basebackup)
                            by default = $PG_BIN
    -s service_name         cluster service name
                            by default = $PG_SERVICE_NAME
    
Help: 
    -h                   Print this usage.
    
EOF
}

while getopts r:p:U:D:B:s:hW FLAG; do
  case $FLAG in
    r)
        PG_SRC_HOST=$OPTARG
        ;;
    p)
        PG_PORT=$OPTARG
        ;;
    D)
        PG_DST_DATA_DIR=$OPTARG
        ;;
    U)
        PG_USERNAME=$OPTARG
        ;;
    B)
        PG_BIN=$OPTARG
        ;;
    s)
        PG_SERVICE_NAME=$OPTARG
        ;;  
    W)
        PG_PASSREQUIRED=true
        ;;  
    h)
        usage
        exit 0
        ;;
    *) 
        exit 2
        ;;
  esac
done


#Let's start this shit
echo "$(timestamp) INFO: RUN THE SCRIPT."


echo "$(timestamp) INFO: checking connection to $PG_SRC_HOST:$PG_PORT as $PG_USERNAME"
if [ "$PG_PASSREQUIRED" = false ] ; then
    if_conn_estb=$($PG_BIN/psql -t -h $PG_SRC_HOST -U $PG_USERNAME -p $PG_PORT -d postgres -w -c "SELECT 1")
else
    echo "$(timestamp) WARN: enter the password for $PG_USERNAME"
    if_conn_estb=$($PG_BIN/psql -t -h $PG_SRC_HOST -U $PG_USERNAME -p $PG_PORT -d postgres -W -c "SELECT 1")
fi

if [[ $if_conn_estb -ne 1 ]]; then
    echo "$(timestamp) ERROR: can't connect to $PG_SRC_HOST. Exit the script."
    echo "--------------------------------------------------------------------------------"
    exit 3
fi 


# Stop PostgreSQL service
echo "$(timestamp) INFO: wait $PG_DELAY seconds while $PG_SERVICE_NAME is stopping"
sudo systemctl stop $PG_SERVICE_NAME
sleep $PG_DELAY
PG_IS_READY=$($PG_BIN/pg_isready)
if [[ "$PG_IS_READY" == *" no response" ]]; then
    echo "$(timestamp) INFO: $PG_SERVICE_NAME was successfully stopped"
else
    echo "$(timestamp) ERROR: $PG_SERVICE_NAME was not stopped. Try it one more time."
    sudo systemctl stop $PG_SERVICE_NAME
    echo "$(timestamp) INFO: wait $PG_DELAY seconds while $PG_SERVICE_NAME is stopping"
    sleep $PG_DELAY
    PG_IS_READY=$($PG_BIN/pg_isready)
    if [[ "$PG_IS_READY" == *" no response" ]]; then
        echo "$(timestamp) INFO: $PG_SERVICE_NAME was successfully stopped"
    else
        echo "$(timestamp) ERROR: $PG_SERVICE_NAME was not stopped. Exit the script."
        echo "--------------------------------------------------------------------------------"
        exit 4
    fi
fi


# Delete files in destination directory if required
echo "$(timestamp) INFO: remove files in $PG_DST_DATA_DIR"
rm -rf $PG_DST_DATA_DIR/*


# Run pg_basebackup from $PG_SRC_HOST to $PG_DST_DATA_DIR
echo "$(timestamp) INFO: pg_basebackuping files from $PG_SRC_HOST to $PG_DST_DATA_DIR"
if [ "$PG_PASSREQUIRED" = false ] ; then
    $PG_BIN/pg_basebackup -X stream -h $PG_SRC_HOST -p $PG_PORT -U $PG_USERNAME -w -D $PG_DST_DATA_DIR
else
    echo "$(timestamp) WARN: enter the password for $PG_USERNAME"
    $PG_BIN/pg_basebackup -X stream -h $PG_SRC_HOST -p $PG_PORT -U $PG_USERNAME -W -D $PG_DST_DATA_DIR
fi
#checkerrcode


# Prepare files in PG_DST_DATA_DIR (check if recovery.conf, postmaster.pid not exist)
rm -f $PG_DST_DATA_DIR/recovery.conf
rm -f $PG_DST_DATA_DIR/postmaster.pid


# Start PostgreSQL service
echo "$(timestamp) INFO: wait a few minutes while $PG_SERVICE_NAME is starting"
chmod go-rwx $PG_DST_DATA_DIR
sudo systemctl start $PG_SERVICE_NAME
sleep $PG_DELAY
PG_IS_READY=$($PG_BIN/pg_isready)
if [[ "$PG_IS_READY" == *" accepting connections" ]]; then
    echo "$(timestamp) INFO: $PG_SERVICE_NAME accepts connections"
else
    echo "$(timestamp) ERROR: $PG_SERVICE_NAME was not started. Try it one more time."
    sudo systemctl start $PG_SERVICE_NAME
    echo "$(timestamp) INFO: wait a few minutes while $PG_SERVICE_NAME is starting"
    sleep $PG_DELAY
    PG_IS_READY=$($PG_BIN/pg_isready)
    if [[ "$PG_IS_READY" == *" accepting connections" ]]; then
        echo "$(timestamp) INFO: $PG_SERVICE_NAME accepts connections"
    else
        echo "$(timestamp) ERROR: $PG_SERVICE_NAME was not started. Exit the script."
        echo "--------------------------------------------------------------------------------"
        exit 5
    fi
fi


echo "$(timestamp) INFO: THE SCRIPT IS EXECUTED"
echo "--------------------------------------------------------------------------------"