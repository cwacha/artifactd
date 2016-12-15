#!/usr/bin/env python
import pytest
import os
BASEDIR=os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import requests
import time
import shutil

PORT=4079

@pytest.fixture(scope="module")
def httpd():
	import sys
	sys.path.insert(0, BASEDIR + '/src/opt/artifactd/bin')
	import artifactd
	import threading
	import logging

	logging.basicConfig(level=logging.NOTSET)
	opts = artifactd.loadConfig("")
	opts['port'] = PORT

	server = artifactd.webserver(opts)
	th = threading.Thread(target=server.startup)
	th.daemon = True
	th.start()
	print "waiting for httpd to start"
	while not server.isReady():
		time.sleep(.5)
	print "httpd ready"
	yield httpd
	print("teardown httpd")
	server.shutdown()

def test_startup(httpd):
	response = requests.get("http://localhost:%d/artifacts" % PORT).text
	assert "<title>Index of /artifacts/</title>" in response

def test_download_readme(httpd):
	response = requests.get("http://localhost:%d/artifacts/README.md" % PORT).text
	assert len(response) > 1024

def sample_document():
	return "Lorem ipsum dolor sit amet, consetetur sadipscing elitr,\
	sed diam nonumy eirmod tempor invidunt ut labore et dolore magna \
	aliquyam erat, sed diam voluptua. At vero eos et accusam et justo \
	duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata \
	sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, \
	consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt \
	ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero \
	eos et accusam et justo duo dolores et ea rebum. Stet clita kasd \
	gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet."

def test_deploy_wrong1(httpd):
	response = requests.put("http://localhost:%d/artifacts/test.pkg" % PORT, data=sample_document())
	assert response.status_code == 403

def test_deploy_wrong2(httpd):
	response = requests.put("http://localhost:%d/artifacts/snapshots/test.pkg" % PORT, data=sample_document())
	assert response.status_code == 403

def test_deploy_wrong3(httpd):
	response = requests.put("http://localhost:%d/artifacts/releases/test.pkg" % PORT, data=sample_document())
	assert response.status_code == 403

def test_deploy_snapshot(httpd):
	response = requests.put("http://localhost:%d/artifacts/snapshot/test.pkg" % PORT, data=sample_document())
	assert response.status_code == 200

def safe_remove(filename):
	if os.path.isfile(filename):
		os.remove(filename)

def test_deploy_release(httpd):
	safe_remove(BASEDIR+"/src/opt/artifactd/var/www/artifacts/release/test.pkg")
	response = requests.put("http://localhost:%d/artifacts/release/test.pkg" % PORT, data=sample_document())
	assert response.status_code == 200

def test_deploy_release_overwrite(httpd):
	safe_remove(BASEDIR+"/src/opt/artifactd/var/www/artifacts/release/test.pkg")
	response = requests.put("http://localhost:%d/artifacts/release/test.pkg" % PORT, data=sample_document())
	response = requests.put("http://localhost:%d/artifacts/release/test.pkg" % PORT, data=sample_document())
	assert response.status_code == 409

def copyfile_withtime(src, dst, timestring):
	shutil.copyfile(src, dst)
	mtime = time.mktime(time.strptime(timestring, "%Y-%m-%d %H:%M:%S"))
	os.utime(dst, (mtime, mtime))

def test_deploy_snapshot_maintenance(httpd):
	with open('workfile', 'w') as f:
		f.write(sample_document())

	snapshotdir = os.path.realpath(BASEDIR + '/src/opt/artifactd/var/www/artifacts/snapshot/test')

	if not os.path.isdir(snapshotdir):
		os.makedirs(snapshotdir)

	copyfile_withtime('workfile', snapshotdir + '/test-1.pkg', "2015-03-04 21:13:00")
	copyfile_withtime('workfile', snapshotdir + '/test-2.pkg', "2015-03-04 21:17:10")
	copyfile_withtime('workfile', snapshotdir + '/test-3.pkg', "2016-04-01 09:28:32")
	copyfile_withtime('workfile', snapshotdir + '/test-4.pkg', "2016-05-02 10:15:00")
	copyfile_withtime('workfile', snapshotdir + '/test-5.pkg', "2016-05-03 11:02:00")
	copyfile_withtime('workfile', snapshotdir + '/test-6.pkg', "2016-07-23 15:34:00")
	copyfile_withtime('workfile', snapshotdir + '/test-7.pkg', "2016-08-23 17:21:00")
	copyfile_withtime('workfile', snapshotdir + '/test-8.pkg', "2016-09-04 09:11:00")
	copyfile_withtime('workfile', snapshotdir + '/test-9.pkg', "2016-09-04 09:14:00")

	response = requests.put("http://localhost:%d/artifacts/snapshot/test/test-10.pkg" % PORT, data=sample_document())

	actual = set(os.listdir(snapshotdir))
	ideal = set(['test-5.pkg', 'test-6.pkg', 'test-7.pkg', 'test-8.pkg', 'test-9.pkg', 'test-10.pkg'])

	os.remove('workfile')
	shutil.rmtree(snapshotdir)
	assert len(ideal) == len(actual) and sorted(ideal) == sorted(actual)

