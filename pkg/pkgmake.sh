#!/bin/sh

TMP=`pwd`; cd `dirname $0`; BASEDIR=`pwd`; cd $TMP

ARTIFACTBASE=http://localhost:4070/artifacts/snapshot
all() {
	download && import && ipk || rpm
}

dist() {
	clean && all
}

download() {
	echo "##### downloading"
	return
	[ -f $BASEDIR/../vendor/.done ] && return

	# download additional artifacts from artifactory

	mkdir -p $BASEDIR/../vendor
	cd $BASEDIR/../vendor
	COPT="-sw%{http_code} %{url_effective}\n"
	#curl "$COPT" -O http://odyssey.apps.csintra.net/artifactory/libs-release/com/csg/ts/security/xeng/external/apr-1.3.9-5.el6_2.x86_64.rpm
	touch .done
	cd $BASEDIR
}

import() {
	echo "##### importing"
	cd $BASEDIR
	[ -d BUILD ] && return
	mkdir -p BUILD
	cp -a $BASEDIR/../src/* BUILD

	rm -rf BUILD/opt/artifactd/var/www/snapshot/*
	rm -rf BUILD/opt/artifactd/var/www/release/*
	rm -rf BUILD/opt/artifactd/var/log/*

	find BUILD -depth -name ".DS_Store" -exec rm {} \;
	find BUILD -depth -name "._*" -exec rm {} \;
	find BUILD -depth -name ".svn" -exec rm -rf {} \;

	chown -Rf 0:0 BUILD/*
	chmod o+rx BUILD/opt/artifactd/
	chmod -R o+rx BUILD/opt/artifactd/var

	return 0
}

rpm() {
	echo "##### building rpm"
	cd $BASEDIR

	rpmbuild --define "_topdir $BASEDIR" --define "my_version $VERSION" --define "my_revision $REVISION" --buildroot=$BASEDIR/BUILD -bb SPECS/code.spec

	cp $BASEDIR/../vendor/*.rpm $BASEDIR/RPMS/x86_64
}

ipk() {
	echo "##### building ipk"
	cd $BASEDIR
	mkdir -p RPMS/x86_64

	# OSX hack to disable extended attributes that result in ._FILE files
	export COPYFILE_DISABLE=true
	
	cd BUILD
	tar cfz $BASEDIR/RPMS/data.tar.gz .
	cd ..
	
	PACKAGE=`grep ^Package: SPECS/control | awk '{print $2}'`
	PACKAGEFILE=${PACKAGE}-${VERSION}-${REVISION}.ipk

	mkdir -p RPMS/control
	cd SPECS
	sed "s/%version%/$VERSION/g;s/%revision%/$REVISION/g" control > $BASEDIR/RPMS/control/control
	cp -f preinst postinst prerm postrm $BASEDIR/RPMS/control 2>/dev/null
	cd ..

	cd RPMS/control
	tar cfz $BASEDIR/RPMS/control.tar.gz .
	cd ..

	echo "2.0" > debian-binary
	tar cfz x86_64/$PACKAGEFILE control.tar.gz data.tar.gz debian-binary
	rm control.tar.gz data.tar.gz debian-binary

	cd $BASEDIR
}

deploy() {
	echo "##### deploying"

	FULLFILES=`ls -1 $BASEDIR/RPMS/x86_64/*.{rpm,ipk} 2>/dev/null`
	[ -z "$FULLFILES" ] && echo "No packages found. Stop." && return 1
	for FULLFILE in $FULLFILES; do
		FILE=`basename "$FULLFILE"`
		COMPONENT=`echo $FILE | cut -f1 -d-`
		VERSION=`echo $FILE | cut -f2 -d-`
		TARGET=$ARTIFACTBASE/$COMPONENT/$VERSION/$FILE
		curl -s -T $FULLFILE -X PUT $TARGET | grep "Message:"
	done
}

clean() {
	echo "##### cleaning"
	cd $BASEDIR
	rm -rf BUILD
	rm -rf BUILDROOT
	rm -rf RPMS
	rm -rf SRPMS
	rm -rf SOURCES
}

_loadversion() {
	# use version from environment or load it from file
	VERSION=${VERSION-`cat $BASEDIR/VERSION`}
	VERSION=`echo "$VERSION" | sed 's/[ 	-]/_/g'`

	# use revision from environment or get it from version control
	REVISION=${REVISION-0}
	[ "$REVISION" -eq 0 ] && REVISION=`git log --oneline $BASEDIR/.. 2>/dev/null | wc -l | xargs`
	[ "$REVISION" -eq 0 ] && REVISION=`svn info -R $BASEDIR/.. 2>/dev/null | grep "Last Changed Rev" | awk '{print $4}' | sort -un | tail -1`
	# really evil hack when no svn is installed and gradle or jenkins use their own SVN implementation
	[ -z "$REVISION" ] && REVISION=`sqlite3 $SVNBASE/.svn/wc.db "select revision from nodes where local_relpath='';" 2>/dev/null`
	[ -z "$REVISION" ] && REVISION=0
}

_usage() {
	echo "Usage: $0 <action>"
	echo
	echo "ACTIONS:"
	declare -F | grep -v " _" | awk '{print "   "$3}'
}

[ $# -eq 0 ] && _usage && exit 1

action="$1"
shift

type "$action" 2>/dev/null | grep function >/dev/null
[ $? -ne 0 ] && echo "no such action: $action" && exit 1

_loadversion

$action $*
echo "##### done"
