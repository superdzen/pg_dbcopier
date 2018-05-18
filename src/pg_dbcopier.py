#!/usr/bin/python

import logging
import argparse
import subprocess
import sys
import time
import getpass

SCRIPT_LOG_FILE = 'pg_db_copier.log'
PG_SERVICE_NAME = "postgresql-9.6"
PG_SOURCE_HOST = "db-src"
PG_PORT = 5432
PG_USERNAME = "replication"
PG_BIN_DIR = "/usr/pgsql-9.6/bin"
PG_DATA_DIR = "/var/lib/pgsql/9.6/data"
PG_BACKUP_DIR = "/var/lib/pgsql/9.6/backups"

logger = None


def arg_parser():
    """Parsing arguments

    :return: returns nothing
    """
    parser = argparse.ArgumentParser(add_help=False, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-r', '--remote-host', default=PG_SOURCE_HOST,
                        help="""Source PostgreSQL hostname for pg_basebackup. 
By default = """ + PG_SOURCE_HOST)

    parser.add_argument('-p', '--port-number', type=int, default=PG_PORT,
                        help="""Source PostgreSQL port for pg_basebackup. 
By default = """ + str(PG_PORT))

    parser.add_argument('-U', '--username', default=PG_USERNAME,
                        help="""Username for pg_basebackup. Customized .pgpass is required.
By default = """ + PG_USERNAME)

    parser.add_argument('-W', action='store_true',
                        help="""Always ask password.
(for manual launching or if .pgpass not customized)""")

    parser.add_argument('-D', '--data-dir', default=PG_DATA_DIR,
                        help="""Destination PostgreSQL data directory. 
By default = """ + PG_DATA_DIR)

    parser.add_argument('-m', action='store_true',
                        help="""Make backup of old data""")

    parser.add_argument('-A', '--backup-dir', default=PG_BACKUP_DIR,
                        help="""Data directory for old data backups (with -m option). 
By default = """ + PG_BACKUP_DIR)

    parser.add_argument('-B', '--pg-bin-dir', default=PG_BIN_DIR,
                        help="""Cluster executable directory for launching and pg_basebackup. 
By default = """ + PG_BIN_DIR)

    parser.add_argument('-s', '--service-name', default=PG_SERVICE_NAME,
                        help="""Cluster service name. 
By default = """ + PG_SERVICE_NAME)

    parser.add_argument('-l', '--log-file', default=SCRIPT_LOG_FILE,
                        help="""Name for log file. 
By default = """ + SCRIPT_LOG_FILE)

    parser.add_argument('--no-console-log', action='store_true',
                        help="""Do not write log in stdout""")

    parser.add_argument('--no-file-log', action='store_true',
                        help="""Do not write log in file""")

    parser.add_argument('-h', '--help', action='help', help='Show this usage and exit')

    return parser.parse_args()


def init_logger(args):
    """Initiates logger - an instance of logging object.

    Checks whether to write to the log file or to the console (stdout)
    :param args: script arguments list.
    Process arguments: --no-console-log, --no-file-log
    :return: returns nothing
    """
    global logger
    logger = logging.getLogger(__file__)
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    if not args.no_console_log:
        console_log_handler = logging.StreamHandler(sys.stdout)
        console_log_handler.setFormatter(log_formatter)
        logger.addHandler(console_log_handler)
    if not args.no_file_log:
        file_log_handler = logging.FileHandler(args.log_file)
        file_log_handler.setFormatter(log_formatter)
        logger.addHandler(file_log_handler)

    logger.setLevel(logging.INFO)


def user_rights():
    """Returns string with execution rights

    :return: string "" or "sudo -u postgres"
    """
    user_rights_ = "sudo -u postgres "
    if getpass.getuser() == "postgres":
        user_rights_ = ""

    return user_rights_


def run_shell_command(command, description, show_error=True):
    """Runs the linux command and checks the output and errors

    :param command: line of the command being executed
    :param description: description of the command being executed
    :param show_error: shows executing error in output log
    :return: returns nothing
    """
    output = ''
    try:
        output = subprocess.check_output([command], shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        if show_error:
            logger.error("failed to run command: {}".format(description))
            logger.error('output: ' + e.output.decode('utf-8'))
            exit(1)
        else:
            return e.output.decode('utf-8').strip()
    return output


def check_pg_connection(args):
    """Checks that the data directory is not equal '.', '..' or '/'

    Test connection to remote PostgreSQL (source)
    :param args: script arguments list.
    Process arguments: --data-dir, --pg-bin-dir, --backup-dir, --remote-host, --port-number, --username, -W
    :return: returns nothing
    """
    if args.data_dir in ['/', '.', '..']:
        logger.error('wrong --data-dir: {}'.format(args.data_dir))
        exit(2)

    password_mode = 'w'
    if args.W:
        password_mode = 'W'

    command = '{}{}/psql -t -h {} -U {} -p {} -d postgres -{} -c "SELECT 1"'.format(user_rights(), args.pg_bin_dir,
                                                                                    args.remote_host, args.username,
                                                                                    args.port_number, password_mode)
    output = run_shell_command(command, 'check connection to PostgreSQL')

    # if SELECT 1 returns 1 than connection is OK
    if output == '1':
        logger.info(
            "connection to {}:{} as {} was successfull".format(args.remote_host, args.port_number, args.username))


def pg_service_action(args, action):
    """This function can make systemctl actions 'status', 'stop', 'start' and 'restart' and check errors

    The 'status' and 'restart' actions uses for perform 'stop', 'start' actions
    An auxiliary test is performed via the PostgreSQL utility pg_isready
    :param args: script arguments list.
    Process arguments: --service-name
    :param action: systemctl actions: 'status', 'stop', 'start' and 'restart'
    :return: returns status of service
    """
    service_name = args.service_name
    command = " ".join(("sudo systemctl", action, service_name))
    command2 = 'sudo pkill -u postgres'
    if action not in ('status', 'stop', 'start', 'restart'):
        logger.error("unknown service action: " + action + "\n")
        exit(3)

    # 'status' action return codes in (1, -1, 2, -2, 3) depending on the status of linux service
    # and status of PostgreSQL process
    if action == 'status':
        output = run_shell_command(command, action + " {} service".format(service_name), show_error=False)
        pg_isready = if_pg_isready(args)
        if 'Active: active (running)' in output:
            if pg_isready:
                return 1
            else:
                return -1
        elif 'Active: inactive (dead)' in output:
            if not pg_isready:
                return 2
            else:
                return -2
        elif 'Active: failed' in output:
            if pg_isready:
                logger.error("service {} is failed. PostgreSQL is active. Stop the script".format(service_name))
                exit(4)
            else:
                logger.warn(
                    "service {} is failed. PostgreSQL is not response. Trying to restart service".format(service_name))
                pg_service_action(args, 'restart')
                return 3

    # First attempt - stop the service via systemctl
    # Second attempt - stop the process via sudo pkill -u postgres
    elif action == 'stop':
        status_code = pg_service_action(args, 'status')
        if status_code in (1, -1, 2, -2, 3):
            run_shell_command(command, action + " {} service".format(service_name), show_error=False)
            if not if_pg_isready(args):
                logger.info('service {} was successfully stopped'.format(service_name))
            else:
                output = run_shell_command(command2, "manual stop postgres".format(service_name), show_error=False)
                if not if_pg_isready(args):
                    logger.warn('service {} was stopped manually'.format(service_name))
                else:
                    logger.error("cant stop postgres. Stop the script".format(service_name))
                    logger.error('output: ' + output)
                    exit(5)

    # Starting the service via systemctl
    # Check service status
    # If status_code = 1 (service active/running and postgresql is ready) - show warning
    # If status_code = -1 (service active/running and postgresql is not response) - try to restart service
    # If status_code = 2 (service inactive/dead and postgresql is not response) - try to start service
    # If status_code = -2 (service inactive/dead and postgresql is ready) - try to restart service
    elif action == 'start':
        status_code = pg_service_action(args, 'status')
        if status_code == 1:
            logger.warn('service {} already started'.format(service_name))
        if status_code == -1:
            logger.warn('service {} already started, but PostgreSQL is not response. trying to restart service'.format(
                service_name))
            pg_service_action(args, 'restart')
        if status_code == 2:
            output = run_shell_command(command, action + " {} service".format(service_name), show_error=False)
            if if_pg_isready(args):
                logger.info('service {} was successfully started'.format(service_name))
            else:
                logger.error("cant start {} service. Stop the script".format(service_name))
                logger.error('output: ' + output)
                exit(6)
        if status_code == -2:
            logger.warn('service {} stopped, but PostgreSQL is active. trying to restart service'.format(service_name))
            pg_service_action(args, 'restart')

    # Restart service and check
    elif action == 'restart':
        output = run_shell_command(command, action + " {} service".format(service_name), show_error=False)
        if if_pg_isready(args):
            logger.info('service {} was successfully restarted'.format(service_name))
        else:
            logger.error("cant restart {} service. Stop the script".format(service_name))
            logger.error('output: ' + output)
            exit(7)


def if_pg_isready(args):
    """Checks status of PostgreSQL proccess via the utility pg_isready

    :param args: script arguments list.
    Process arguments: --pg-bin-dir
    :return: True if PostgreSQl is ready and False if it is not response
    """
    command = '{}/pg_isready'.format(args.pg_bin_dir)
    output = run_shell_command(command, 'check if PostgresQL is ready', show_error=False)

    if "accepting connections" in output:
        return True
    elif "no response" in output:
        return False


def make_pg_basebackup(args):
    """Makes a copy of remote DB via pg_basebackup
    
    :param args: script arguments list.
    Process arguments: --data-dir, --pg-bin-dir, --backup-dir, --remote-host, --port-number, --username, -W, -m
    :return:
    """
    # Make a backup if it is required
    if args.m:
        old_backup_file = "{}/old_backup_{}.tar.gz".format(args.backup_dir, time.strftime("%Y%m%d%H%M%S"))
        logger.info('make backup of old data')
        command_old_backup = "{}tar -czf {} {}".format(user_rights(), old_backup_file, args.data_dir)
        output = run_shell_command(command_old_backup, 'check connection to PostgreSQL', show_error=False)
        if "Error" in output:
            logger.error("Cant make backup.")
            logger.error('output:\n' + output)
            logger.info("Trying to start {}".format(args.service_name))
            return

    # Delete old data
    logger.info('delete old data')
    command_del_old_data = "{}sh -c \"rm -rf {}/*\"".format(user_rights(), args.data_dir)
    run_shell_command(command_del_old_data, 'delete old data')

    # Run pg_basebackup
    logger.info('run pg_basebackup')
    password_mode = 'w'
    if args.W:
        password_mode = 'W'

    command_basebackup = "{}pg_basebackup -X stream -h {} -p {} -U {} -{} -D {}".format(user_rights(), args.remote_host,
                                                                                        args.port_number, args.username,
                                                                                        password_mode, args.data_dir)
    run_shell_command(command_basebackup, 'run pg_basebackup')


def main():
    args = arg_parser()
    init_logger(args)
    logger.info("the script started")
    check_pg_connection(args)
    pg_service_action(args, 'stop')
    make_pg_basebackup(args)
    pg_service_action(args, 'start')
    pg_service_action(args, 'status')
    logger.info("the script succeeded")
    logger.info("--------------------------------------------------------------------------------")


if __name__ == '__main__':
    main()
