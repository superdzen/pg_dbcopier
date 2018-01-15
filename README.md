# pg_dbcopier

Pg_dbcopier is a python script that can make a stand-alone copy of the remote PostgreSQL server.
> Can be started automatically.
There is a simplified version for Linux shell - pg_dbcopier.sh

##### Sequencing:
1. Start script
2. Parse arguments;
3. Initiate logger;
4. Check connection to remote server via postgresql port (5432 by default);
5. Stop local PostgreSQL service or process;
6. Make a backup of local PostgreSQL data directory if required;
7. Make a copy from remoter server via pg_basebackup;
8. Start local PostgreSQL service, check its status.

**Some errors are checked at every step**


##### Mimimum OS requirments:
  - Linux (tested on RHEL/Centos 7.x)
  - Python 2.7 or higher
  - PostgreSQL 9.x (installed from repositories or rpm/deb)
  - Systemd and passwordless rights for running: sudo systemctl start/stop/status/restart postgresql
  - Passwordless rights for execute commands as postgres: sudo -u postgres *

##### PostgreSQL requirements:
  - Remote(source) server must be configured for streaming replication https://www.postgresql.org/docs/9.6/static/high-availability.html
  - One user with replication privilege on source server
  - Customized .pgpass for postgres user on destination server

#### Execution example:
##### Check rights:
```
[admin@db-dst ~]$ ping db-src -c 1
PING db-src (192.168.56.102) 56(84) bytes of data.
[admin@db-dst ~]$ sudo -u postgres psql
could not change directory to "/home/admin": Permission denied
psql (9.6.6)
Type "help" for help.

postgres=# drop database demo;
DROP DATABASE
postgres=# \q
[admin@db-dst ~]$ sudo systemctl restart postgresql-9.6
[admin@db-dst ~]$ sudo -u postgres cat /var/lib/pgsql/.pgpass
db-src:*:*:replication:replication

[admin@db-dst ~]$
```

##### Run help:
```
[admin@db-dst ~]$ ./pg_dbcopier.py -h

usage: pg_dbcopier.py [-r REMOTE_HOST] [-p PORT_NUMBER] [-U USERNAME] [-W]
                      [-D DATA_DIR] [-m] [-A BACKUP_DIR] [-B PG_BIN_DIR]
                      [-s SERVICE_NAME] [-l LOG_FILE] [--no-console-log]
                      [--no-file-log] [-h]

optional arguments:
  -r REMOTE_HOST, --remote-host REMOTE_HOST
                        Source PostgreSQL hostname for pg_basebackup.
                        By default = db-src
  -p PORT_NUMBER, --port-number PORT_NUMBER
                        Source PostgreSQL port for pg_basebackup.
                        By default = 5432
  -U USERNAME, --username USERNAME
                        Username for pg_basebackup. Customized .pgpass is required.
                        By default = replication
  -W                    Always ask password.
                        (for manual launching or if .pgpass not customized)
  -D DATA_DIR, --data-dir DATA_DIR
                        Destination PostgreSQL data directory.
                        By default = /var/lib/pgsql/9.6/data
  -m                    Make backup of old data
  -A BACKUP_DIR, --backup-dir BACKUP_DIR
                        Data directory for old data backups (with -m option).
                        By default = /var/lib/pgsql/9.6/backups
  -B PG_BIN_DIR, --pg-bin-dir PG_BIN_DIR
                        Cluster executable directory for launching and pg_basebackup.
                        By default = /usr/pgsql-9.6/bin
  -s SERVICE_NAME, --service-name SERVICE_NAME
                        Cluster service name.
                        By default = postgresql-9.6
  -l LOG_FILE, --log-file LOG_FILE
                        Name for log file.
                        By default = pg_db_copier.log
  --no-console-log      Do not write log in stdout
  --no-file-log         Do not write log in file
  -h, --help            Show this usage and exit
```

##### Run script with defaults:

```
[admin@db-dst ~]$ ./pg_dbcopier.py
2018-01-15 22:49:47,877 INFO the script started
2018-01-15 22:49:48,023 INFO service postgresql-9.6 was successfully stopped
2018-01-15 22:49:48,023 INFO delete old data
2018-01-15 22:49:48,072 INFO run pg_basebackup
2018-01-15 22:49:54,241 INFO service postgresql-9.6 was successfully started
2018-01-15 22:49:54,263 INFO the script succeeded
2018-01-15 22:49:54,264 INFO --------------------------------------------------------------------------------
[admin@db-dst ~]$
```


##### Run script with some arguments:

```
[admin@db-dst ~]$ ./pg_dbcopier.py -U replication -r db-src -p 5432 -D /var/lib/pgsql/9.6/data -m -A /var/lib/pgsql/9.6/backups -s postgresql-9.6 -B /usr/pgsql-9.6/bin
2018-01-15 22:52:07,229 INFO the script started
2018-01-15 22:52:07,318 INFO service postgresql-9.6 was successfully stopped
2018-01-15 22:52:07,318 INFO make backup of old data
2018-01-15 22:52:18,740 INFO delete old data
2018-01-15 22:52:18,833 INFO run pg_basebackup
2018-01-15 22:52:23,698 INFO service postgresql-9.6 was successfully started
2018-01-15 22:52:23,719 INFO the script succeeded
2018-01-15 22:52:23,720 INFO --------------------------------------------------------------------------------
```

##### Run script with some wrong arguments:
```
[admin@db-dst ~]$ ./pg_dbcopier.py -U replication -r db-src -p 543
2018-01-15 22:54:29,114 INFO the script started
2018-01-15 22:54:29,191 ERROR failed to run command: check connection to PostgreSQL
2018-01-15 22:54:29,191 ERROR output: could not change directory to "/home/admin": Permission denied
psql: could not connect to server: Connection refused
        Is the server running on host "db-src" (192.168.56.102) and accepting
        TCP/IP connections on port 543?

[admin@db-dst ~]$ ./pg_dbcopier.py -U replication -r db-src -p 5432 -D /
2018-01-15 22:54:36,046 INFO the script started
2018-01-15 22:54:36,046 ERROR wrong --data-dir: /
[admin@db-dst ~]$ ./pg_dbcopier.py -U replication -r db-src1 -p 5432
2018-01-15 22:54:47,254 INFO the script started
2018-01-15 22:54:52,302 ERROR failed to run command: check connection to PostgreSQL
2018-01-15 22:54:52,303 ERROR output: could not change directory to "/home/admin": Permission denied
psql: could not translate host name "db-src1" to address: Name or service not known
```

##### Manual run (with input password):
```
[admin@db-dst ~]$ ./pg_dbcopier.py -U replication -r db-src -p 5432 -W
2018-01-15 22:55:45,983 INFO the script started
Password for user replication:
2018-01-15 22:55:48,989 INFO service postgresql-9.6 was successfully stopped
2018-01-15 22:55:48,989 INFO delete old data
2018-01-15 22:55:49,083 INFO run pg_basebackup
Password:
2018-01-15 22:55:56,635 INFO service postgresql-9.6 was successfully started
2018-01-15 22:55:56,657 INFO the script succeeded
2018-01-15 22:55:56,658 INFO --------------------------------------------------------------------------------
```