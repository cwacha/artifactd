#!/bin/sh

TMP=`pwd`; cd `dirname $0`/..; BASEDIR=`pwd`; cd $TMP

RUNAS=`id | sed -e 's/[=()]/ /g' | awk '{print $3}'`
RUNAS_CMDLINE="$BASEDIR/bin/artifactd.sh $*"
APPUSER=artifactd
APPNAME="Artifactd"
PIDFILE=$BASEDIR/var/run/artifactd.pid
LOCKFILE=/tmp/artifactd.lock
LOCKSTATE=

lock() {
	# make sure we only lock once!
	[ -n "$LOCKSTATE" ] && return;

	LOCKSTATE=WAIT
	TIMEOUT_SEC=90

	[ -f $LOCKFILE ] && echo "Waiting $TIMEOUT_SEC seconds for lock $LOCKFILE."

	while [ -f $LOCKFILE ]; do
		OLDPID=`ps -ef | grep \`cat $LOCKFILE\` | grep -v grep`
		[ -z "$OLDPID" ] && break
		[ $TIMEOUT_SEC -lt 1 ] && quit 1 "Timeout while waiting for lock $LOCKFILE. Abort."
		sleep 1
		TIMEOUT_SEC=`expr $TIMEOUT_SEC - 1`
	done
	
	# Perform the new lock
	LOCKSTATE=LOCKED
	echo $$ >$LOCKFILE
}

unlock() {
	[ "$LOCKSTATE" != "LOCKED" ] && return
	[ -f $LOCKFILE ] && rm -f $LOCKFILE >/dev/null 2>&1
	LOCKSTATE=
}

runas() {
	[ -z "$1" ] && quit 100 "No user given, cannot swith user! Stop."

	if [ "$RUNAS" = root -a "$1" != root ]; then
		echo "Switching to user $1"
		cd /
		su "$1" -c "$RUNAS_CMDLINE"
		quit $?
	fi

	[ "$RUNAS" != "$1" ] && quit 100 "`basename $0` MUST be run as user root or $1 (was: $RUNAS). Stop."
}

quit() {
	[ -n "$2" ] && echo "ERROR: $2" >&2
	unlock
	exit "$1"
}

start() {
	runas $APPUSER

	lock

	if is_running; then
		echo "$APPNAME already running (`get_pids`)."
		unlock
		return
	fi

	echo "Starting $APPNAME"
	$BASEDIR/bin/artifactd.py $* >/dev/null 2>&1 &
	echo `get_pids` > $PIDFILE

	status
	unlock
}

stop() {
	runas $APPUSER
	
	lock

	if is_running; then
		echo "Shutting down $APPNAME"
	else
		echo "$APPNAME not running."
		unlock
		return
	fi

	for pid in `get_pids`; do
		kill $pid
	done

	if is_running; then
		echo -n "Waiting for shutdown."
	fi

	I=60
	while is_running && [ "$I" -gt 0 ]; do
		echo -n "."
		sleep 1
		I=`expr $I - 1`
	done

	if is_running; then
		echo
		echo "Impatience threshold hit, bailing out!"
		for pid in `get_pids`; do
			kill -9 $pid
		done
	fi
	
	rm $PIDFILE

	status
	unlock
}

status() {
	if is_running; then
		echo "$APPNAME running (`get_pids`)."
	else
		echo "$APPNAME stopped."
	fi
}

get_pids() {
	ps -eo pid,user,args | grep "artifactd.py" | grep -v grep | awk '{print $1}' | xargs
}

is_running() {
	NUM=`get_pids`

	if [ -n "$NUM" ]; then
		return 0
	fi
	return 1
}

case "$1" in
	start)
		start
		;;
	stop)
		stop
		;;
	restart)
		stop
		start
		;;
	status)
		status
		;;
	*)
		echo "Usage: $0 { start | stop | restart | status }"
		exit 1
		;;
esac

exit 0




