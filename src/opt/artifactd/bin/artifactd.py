#!/usr/bin/env python

import site, os
BASEDIR=os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
site.addsitedir(os.path.join(BASEDIR, 'lib/python/site-packages'))

import sys
import time
import shutil
import optparse
import ConfigParser
import logging
import logging.config
import BaseHTTPServer
import SimpleHTTPServer
import posixpath
import urllib
import cgi
import string
try:
	from cStringIO import StringIO
except ImportError:
	from StringIO import StringIO
import markdown2

CONFIGFILE=os.path.join(BASEDIR, "etc/artifactd.conf")
LOGGINGCONFIGFILE=os.path.join(BASEDIR, "etc/logging.conf")
WWW_BASEDIR=os.path.realpath(os.path.join(BASEDIR, "var/www"))
PUT_BASEDIR=os.path.realpath(os.path.join(WWW_BASEDIR, "artifacts"))
HEADERFILE=os.path.realpath(os.path.join(WWW_BASEDIR, "theme/header.html"))
FOOTERFILE=os.path.realpath(os.path.join(WWW_BASEDIR, "theme/footer.html"))
KEEPSNAPSHOTNUM=5

ERRORLOG=os.path.join(BASEDIR, "var/log/artifactd.log")
ACCESSLOG=os.path.join(BASEDIR, "var/log/access.log")
logging.errorlogfile=ERRORLOG
logging.accesslogfile=ACCESSLOG
logger = logging.getLogger()

with open(os.path.join(BASEDIR, "VERSION")) as f:
	VERSION = f.read().translate(None, "\r\n").strip()

class rfile:
	def __init__(s, rfile, length):
		s.rfile = rfile
		s.length = length
		
	def read(s, length):
		buflen = min(s.length, length)
		if s.length == -1:
			buflen = length
		s.length -= buflen
		return s.rfile.read(buflen)
		
class ArtifactException(Exception):
	def __init__(self, code, message=None):
		self.code = code
		if message is None:
			message = "Unexpected error during deploy."
		super(ArtifactException, self).__init__(message)

class ArtifactHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
	def __init__(self, request, client_address, server):
		self.template_map = {}
		self.template_map['version'] = VERSION
		self.accesslog = logging.getLogger("access")
		SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(self, request, client_address, server)

	def do_PUT(self):
		"""Respond to PUT request"""
		
		logger.info("Deploy started: %s", self.path)
		path = self.translate_path(self.path)
		
		tempfile = None
		try:
			self.verify_put_path(path)

			localdir = os.path.dirname(path)
			if not os.path.isdir(localdir):
				os.makedirs(localdir)
			
			length = int(self.headers.getheader('content-length'))
			rf = rfile(self.rfile, length)
			tempfile = path + ".tmp"
			with open(tempfile, 'wb') as f:
				shutil.copyfileobj(rf, f)
			
			if rf.length > 0:
				raise ArtifactException(400, "Received less data than expected. File upload interrupted.")
				
			if os.path.isfile(path):
				os.remove(path)
			os.rename(tempfile, path)

			self.remove_old_snapshots(path)

			logger.info("Deploy successful: %s", self.path)
			self.send_response(200)
			self.send_header("Content-type", "text/html")
			self.end_headers()
			self.wfile.write("<head>\n")
			self.wfile.write("<title>Deploy successful</title>\n")
			self.wfile.write("</head>\n")
			self.wfile.write("<body>\n")
			self.wfile.write("<h1>Deploy successful</h1>\n")
			self.wfile.write("<p>Message: Successfully deployed artifact %s\n" % (self.path))
			self.wfile.write("</body>\n")
			return
			
		except TypeError as e:
			logger.error("%s: %s", type(e).__name__, e.__str__())
			self.send_error(411)
		except ArtifactException as e:
			logger.error("%s: %s", type(e).__name__, e.__str__())
			self.send_error(e.code, e.message)
		except IOError as e:
			logger.error("%s: %s", type(e).__name__, e.__str__())
			self.send_error(500, e.__str__())
		except Exception as e:
			logger.error("%s: %s", type(e).__name__, e.__str__())
			self.send_error(500, e.__str__())
		
		if tempfile is not None and os.path.isfile(tempfile):
			os.remove(tempfile)
		logger.error("Deploy failed: %s", self.path)
			
	def verify_put_path(self, path):
		path_rel = os.path.join(PUT_BASEDIR, "release", "")
		path_snp = os.path.join(PUT_BASEDIR, "snapshot", "")
		
		if not (path.startswith(path_rel) or path.startswith(path_snp)):
			raise ArtifactException(403, "Forbidden: Failed to deploy. PUT allowed into '/artifacts/snapshot' or '/artifact/release' folders only (was: %s)" % (self.path))

		if os.path.isdir(path):
			raise ArtifactException(409, "Conflict: Failed to deploy. A directory already exists with that name: '%s'" % (path))
			
		if path.startswith(path_rel) and os.path.isfile(path):
			raise ArtifactException(409, "Conflict: Failed to deploy. Cannot overwrite artifacts in 'release' folder")

	def remove_old_snapshots(self, path):
		path_snp = os.path.join(PUT_BASEDIR, "snapshot", "")

		if not path.startswith(path_snp):
			return

		pathdir = os.path.dirname(path)
		files = sorted(os.listdir(pathdir), key=lambda f: os.path.getmtime("{}/{}".format(pathdir, f)), reverse=True)
		i = 0
		for file in files:
			i += 1
			fullname = os.path.join(pathdir, file)
			if i > KEEPSNAPSHOTNUM:
				logger.info("removing old snapshot: %s", fullname)
				os.remove(fullname)


	def list_directory(self, path):
		"""Helper to produce a directory listing (absent index.html).

		Return value is either a file object, or None (indicating an
		error).  In either case, the headers are sent, making the
		interface the same as for send_head().

		"""
		try:
			list = os.listdir(path)
		except os.error:
			self.send_error(404, "No permission to list directory")
			return None
		list.sort(key=lambda a: a.lower())
		f = StringIO()
		displaypath = cgi.escape(urllib.unquote(self.path))
		parentpath = cgi.escape(urllib.unquote(os.path.dirname(self.path.rstrip("/"))))
		f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"')
		f.write('"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">')
		f.write('<html xmlns="http://www.w3.org/1999/xhtml">')
		f.write('<head>')
		f.write('<title>Index of %s</title>' % displaypath)
		f.write('<link rel="stylesheet" href="/theme/style.css" type="text/css" />')
		f.write('<meta name="viewport" content="width=device-width, initial-scale=1" /> </head>')
		f.write('<body>')
		
		if os.path.isfile(HEADERFILE):
			with open(HEADERFILE, 'r') as hf:
				shutil.copyfileobj(hf, f)
		
		f.write("<table id=\"indexlist\"><tbody>")
		f.write("  <tr class=\"indexhead\"><th class=\"indexcolicon\"><img src=\"/theme/icons/blank.png\" alt=\"[ICO]\"></th><th class=\"indexcolname\"><a href=\"?C=N;O=D\">Name</a></th><th class=\"indexcollastmod\"><a href=\"?C=M;O=A\">Last modified</a></th><th class=\"indexcolsize\"><a href=\"?C=S;O=A\">Size</a></th></tr>")
		f.write("  <tr class=\"parent\"><td class=\"indexcolicon\"><a href=\"%s\"><img src=\"/theme/icons/folder-home.png\" alt=\"[PARENTDIR]\"></a></td><td class=\"indexcolname\"><a href=\"%s\">Parent Directory</a></td><td class=\"indexcollastmod\">&nbsp;</td><td class=\"indexcolsize\">  - </td></tr>" % (parentpath, parentpath))

		for name in list:
			fullname = os.path.join(path, name)
			displayname = linkname = name
			itype = self.icon_type(fullname)
			data = os.stat(fullname)
			mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(data.st_mtime))
			size = "  - ";
				
			# Append / for directories or @ for symbolic links
			if os.path.isdir(fullname):
				displayname = name + "/"
				linkname = name + "/"
				itype = "folder"
			if os.path.islink(fullname):
				displayname = name + "@"
				# Note: a link to a directory displays with @ and links with /
			if os.path.isfile(fullname):
				size = self.sizeof_fmt(data.st_size)

			f.write('<tr><td class="indexcolicon"><a href="%s"><img src="/theme/icons/%s.png" alt="[DIR]"></a></td><td class="indexcolname"><a href="%s">%s</a></td><td class="indexcollastmod">%s  </td><td class="indexcolsize">%s</td></tr>\n' % (urllib.quote(linkname), itype, urllib.quote(linkname), cgi.escape(displayname), mtime, size))
		f.write("</tbody></table>")

		# include a README.md if it exists
		self.template_map['readme'] = ""
		readmefile = os.path.join(path, "README.md")
		if os.path.isfile(readmefile):
			with open(readmefile, 'r') as hf:
				self.template_map['readme'] = markdown2.markdown(hf.read())

		if os.path.isfile(FOOTERFILE):
			with open(FOOTERFILE, 'r') as hf:
				self.apply_template(hf, f)

		f.write("</body>\n</html>\n")
		length = f.tell()
		f.seek(0)
		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.send_header("Content-Length", str(length))
		self.end_headers()
		return f
			
	def icon_type(self, path):
		if not hasattr(self, 'icons_map'):
			self.icons_map = {
				'': 'default', # Default
				'.7z' : 'archive',
				'.bz2' : 'archive',
				'.cab' : 'archive',
				'.gz' : 'archive',
				'.tar' : 'archive',
				'.aac' : 'audio',
				'.aif' : 'audio',
				'.aifc' : 'audio',
				'.aiff' : 'audio',
				'.ape' : 'audio',
				'.au' : 'audio',
				'.flac' : 'audio',
				'.iff' : 'audio',
				'.m4a' : 'audio',
				'.mid' : 'audio',
				'.mp3' : 'audio',
				'.mpa' : 'audio',
				'.ra' : 'audio',
				'.wav' : 'audio',
				'.wma' : 'audio',
				'.f4a' : 'audio',
				'.f4b' : 'audio',
				'.oga' : 'audio',
				'.ogg' : 'audio',
				'.xm' : 'audio',
				'.it' : 'audio',
				'.s3m' : 'audio',
				'.mod' : 'audio',
				'.hex' : 'bin',
				'.xlsx' : 'calc',
				'.xlsm' : 'calc',
				'.xltx' : 'calc',
				'.xltm' : 'calc',
				'.xlam' : 'calc',
				'.xlr' : 'calc',
				'.xls' : 'calc',
				'.csv' : 'calc',
				'.sass' : 'css',
				'.scss' : 'css',
				'.docx' : 'doc',
				'.docm' : 'doc',
				'.dot' : 'doc',
				'.dotx' : 'doc',
				'.dotm' : 'doc',
				'.log' : 'doc',
				'.msg' : 'doc',
				'.odt' : 'doc',
				'.pages' : 'doc',
				'.rtf' : 'doc',
				'.tex' : 'doc',
				'.wpd' : 'doc',
				'.wps' : 'doc',
				'.svgz' : 'svg',
				'.ai' : 'eps',
				'.html' : 'html',
				'.xhtml' : 'html',
				'.shtml' : 'html',
				'.htm' : 'html',
				'.URL' : 'html',
				'.url' : 'html',
				'.jar' : 'java',
				'.jpeg' : 'jpg',
				'.jpe' : 'jpg',
				'.json' : 'js',
				'.dmg' : 'pkg',
				'.phtml' : 'php',
				'.m3u8' : 'm3u',
				'.pls' : 'm3u',
				'.pls8' : 'm3u',
				'.bat' : 'script',
				'.cmd' : 'script',
				'.sh' : 'script',
				'.tif' : 'tiff',
				'.nfo' : 'txt',
				'.asf' : 'video',
				'.asx' : 'video',
				'.avi' : 'video',
				'.flv' : 'video',
				'.mkv' : 'video',
				'.mov' : 'video',
				'.mp4' : 'video',
				'.mpg' : 'video',
				'.rm' : 'video',
				'.srt' : 'video',
				'.swf' : 'video',
				'.vob' : 'video',
				'.wmv' : 'video',
				'.m4v' : 'video',
				'.f4v' : 'video',
				'.f4p' : 'video',
				'.ogv' : 'video',
			}
	
		base, ext = posixpath.splitext(path)
		itype = ext.lstrip(".")
		if os.path.isfile(os.path.join(WWW_BASEDIR, "theme/icons", itype + ".png")):
			return itype
		if ext in self.icons_map:
			return self.icons_map[ext]
		ext = ext.lower()
		if ext in self.icons_map:
			return self.icons_map[ext]
		else:
			return self.icons_map['']
		
	def sizeof_fmt(self, num, suffix='B'):
		for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
			if abs(num) < 1024.0:
				return "%3.1f%s%s" % (num, unit, suffix)
			num /= 1024.0
		return "%.1f%s%s" % (num, 'Yi', suffix)

	def apply_template(self, fsrc, fdst):
		while True:
			buf = fsrc.readline()
			if not buf:
				break
			buf = string.Template(buf).safe_substitute(self.template_map)
			fdst.write(buf)

	def log_message(self, format, *args):
		self.accesslog.info("%s - - [%s] %s" %
				(self.client_address[0],
				self.log_date_time_string(),
				format%args))

class webserver():
	def __init__(self, opts=None):
		self.opts = {}
		self.opts['port'] = 8000
		if isinstance(opts, dict):
			self.opts.update(opts)
			print opts

		self.server = None
		self.logger = logging.getLogger()
		self.ready = False

	def startup(self):
		server_address = ("", self.opts['port'])
		self.server = BaseHTTPServer.HTTPServer(server_address, ArtifactHandler)

		self.logger.info("Server Starts - %s:%s" % server_address)
		try:
			os.chdir(WWW_BASEDIR)
			self.ready = True
			self.server.serve_forever()
		except KeyboardInterrupt:
			pass
		self.server.server_close()
		self.logger.info("Server Stops - %s:%s" % server_address)

	def shutdown(self):
		if self.server:
			self.ready = False
			self.server.shutdown()

	def isReady(self):
		return self.ready


def usage():
#   print "1        10        20        30        40        50        60        70       80"
#   print "|...'....|....'....|....'....|....'....|....'....|....'....|....'....|....'....|"
	print "Usage: %s [OPTIONS]" % sys.argv[0]
	print ""
	print "OPTIONS:"
	print "    -h          --help            Show this help"
	print "                --version         Display version information"
	print "    -v          --verbose         Show verbose output"
	print ""
	print "                --port PORT       set the listen port"
	print ""


def main(argv):
	try:
		logging.config.fileConfig(LOGGINGCONFIGFILE)
	except (ConfigParser.NoSectionError) as (e):
		print "ERROR: Cannot load %s: %s" % (LOGGINGCONFIGFILE, e)

	opts = {}
	opts['port'] = 8000
	configparser = ConfigParser.ConfigParser()
	if os.path.isfile(CONFIGFILE):
		print "reading config"
		configparser.read(CONFIGFILE)
		opts['port'] = int(configparser.get("config", "port"))
		print "port: ", opts['port']

	parser = optparse.OptionParser(usage="%prog [OPTIONS]", version="%prog, Version "+VERSION)
	parser.remove_option("-h")
	parser.remove_option("--version")
	parser.add_option("-h", "--help", dest="help", action="store_true")
	parser.add_option("--version", action="version")
	parser.add_option("-v", "--verbose", dest="verbose", action="store_true")
	parser.add_option("--port", dest="port", type="int")

	(options, args) = parser.parse_args(argv)

	if options.help:
		usage()
		return 1
		
	if options.port:
		opts['port'] = int(options.port)

	server = webserver(opts)
	server.startup()

if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))

