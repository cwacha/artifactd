#!/usr/bin/env python
import pytest
import os
BASEDIR=os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import requests
import time

PORT=4079

@pytest.fixture(scope="module")
def httpd():
	import sys
	sys.path.insert(0, BASEDIR + '/src/opt/artifactd/bin')
	import artifactd
	import threading
	import logging

	logging.basicConfig(level=logging.NOTSET)

	server = artifactd.webserver({'port': PORT})
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

def test_deploy_snapshot_maintenance(httpd):
	response = requests.put("http://localhost:%d/artifacts/snapshot/test/1/test-1.pkg" % PORT, data=sample_document())
	time.sleep(1)
	response = requests.put("http://localhost:%d/artifacts/snapshot/test/1/test-2.pkg" % PORT, data=sample_document())
	time.sleep(1)
	response = requests.put("http://localhost:%d/artifacts/snapshot/test/1/test-3.pkg" % PORT, data=sample_document())
	time.sleep(1)
	response = requests.put("http://localhost:%d/artifacts/snapshot/test/1/test-4.pkg" % PORT, data=sample_document())
	time.sleep(1)
	response = requests.put("http://localhost:%d/artifacts/snapshot/test/1/test-5.pkg" % PORT, data=sample_document())
	time.sleep(1)
	response = requests.put("http://localhost:%d/artifacts/snapshot/test/1/test-6.pkg" % PORT, data=sample_document())
	time.sleep(1)
	response = requests.put("http://localhost:%d/artifacts/snapshot/test/1/test-7.pkg" % PORT, data=sample_document())

	actual = os.listdir(BASEDIR+"/src/opt/artifactd/var/www/artifacts/snapshot/test/1")
	ideal = ['test-3.pkg', 'test-4.pkg', 'test-5.pkg', 'test-6.pkg', 'test-7.pkg']
	assert len(ideal) == len(actual) and sorted(ideal) == sorted(actual)

