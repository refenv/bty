#!/usr/bin/env python
from __future__ import print_function
from wsgiref.simple_server import make_server
from subprocess import Popen, PIPE
import pprint
import json
import copy
import re
import os

REGEX_HWA = r".*(([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})).*"

DEFAULT_HOST = {
	"hwa": None,
	"image": None,
	"hostname": None,
	"managed": False,
	"pxe_default": None
}

CFG_FNAME = "bty.json"

PXE_LABELS = {
	"boot_hda",
	"boot_hda_bzi",
	"install"
}

def ipa_to_hwa(ipa=None):
	"""
	Resolve the given IP address to HW address
	
        @returns hwaddr on the form AA:BB:CC:11:22:33 on success, None otherwise
        """

	if ipa is None:
		return None

        cmd = ["arp", "-a", ipa]

        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)

        out, _ = proc.communicate()
        out = out.lower() if out else ""

        match = re.match(REGEX_HWA, out)
        if match:
                return match.group(1).upper()

        return None

def hdrs(content=None, content_type=None):
	"""Return headers for the given content"""

	if content is None:
		content = b""

	if content_type is None:
		content_type = "text/plain"
	
	return  [
		('Content-type', content_type),
		('Content-Length', str(len(content)))
	]

def cfg_load(environ):
	"""
	Load config from os.path.dirname("SCRIPT_FILENAME")/bty.json

	@returns config as dict on success, None otherwise
	"""

	cfg = None

	script_filename = environ.get("SCRIPT_FILENAME")
	if script_filename is None:
		return cfg

	cfg_path = os.sep.join([os.path.dirname(script_filename), CFG_FNAME])
	if not os.path.exists(cfg_path):
		return cfg

	with open(cfg_path, "r") as cfg_fd:
		cfg = json.load(cfg_fd)

	return cfg

def cfg_save(environ, cfg):
	"""
	Store the given cfg

	@returns True on success, False otherwise
	"""

	script_filename = environ.get("SCRIPT_FILENAME")
	if script_filename is None:
		return False

	cfg_path = os.sep.join([os.path.dirname(script_filename), CFG_FNAME])
	if not os.path.exists(cfg_path):
		return False

	with open(cfg_path, "w") as cfg_fd:
		cfg = json.dump(cfg, cfg_fd, sort_keys=True, indent=2)

	return True

def bootstrap(environ, cfg, host):
	"""@returns bootstrap script for the host to run"""

	print("bootstrap")

	script_filename = environ.get("SCRIPT_FILENAME")
	tmpl_path = os.sep.join([
		os.path.dirname(script_filename),
		"install.tmpl" if host["managed"] else "reboot.tmpl"
	])

	tmpl = ""
	with open(tmpl_path, "r") as tmpl_fd:
		tmpl = tmpl_fd.read()

	for key, val in host.items():
		if val is None:
			continue

		placeholder = "___%s___" % key.upper()
		tmpl = tmpl.replace(placeholder, str(val))

	return tmpl

def pxe_config(environ, cfg, host):
	"""@returns PXE config for the given host on success, None otherwise"""
	
	print("pxe_config")

	if not host["managed"]:
		print ("ERR: host: %r is not managed" % host)
		return None

	if None in [host["hostname"], host["hwa"], host["image"]]:
		print("ERR: invalid host: %r" % host)
		return None

	script_filename = environ.get("SCRIPT_FILENAME")
	tmpl_path = os.sep.join([
		os.path.dirname(script_filename),
		"pxeconfig.tmpl"
	])

	tmpl = ""
	with open(tmpl_path, "r") as tmpl_fd:
		tmpl = tmpl_fd.read()

	for key, val in host.items():
		if val is None:
			continue

		placeholder = "___%s___" % key.upper()
		tmpl = tmpl.replace(placeholder, str(val))

	return tmpl

def pxe_config_install(environ, cfg, host, pxe):
	"""Install the given pxe config"""

	print("pxe_config_install")

	pxe_fname = "01-%s" % host["hwa"].replace(":", "-")

	with open("/tmp/%s" % pxe_fname, "w") as pxe_fd:
		pxe_fd.write(pxe)

def wildcard(environ, cfg):
	"""Wildcard..."""

	print("wildcard")

	content = ""
	content += "ENVIRON: %s" % pprint.pformat(environ)
	content += "\n\n"
	content += "CONFIG: %s" % pprint.pformat(cfg)

	return content

def manage(environ, cfg):
	"""Do some management"""

	return ""

def application(environ, start_response):
        """Application generating and modifying PXE configurations"""

	print("ENTER!")

	req_uri = environ.get("REQUEST_URI")
	if req_uri is None:
		start_response("404", hdrs())
		return []

	hwa = ipa_to_hwa(environ.get("REMOTE_ADDR"))	# Get HWA and set in env
	if hwa is None:
		start_response("404", hdrs())
		return []

	environ["REMOTE_HWA"] = hwa

	cfg = cfg_load(environ)				# Load config

	if hwa not in cfg:				# Add entry in config
		cfg[hwa] = copy.deepcopy(DEFAULT_HOST)
		cfg[hwa]["hwa"] = hwa

		cfg_save(environ, cfg)	

	host = cfg[hwa]

	print("host: %r" % host)

	if "bootstrap" in req_uri:			# Dispatch
		content = bootstrap(environ, cfg, host)

		if host["managed"]:			# Create PXE config for host
			pxe = pxe_config(environ, cfg, host)
			pxe_config_install(environ, cfg, host, pxe)

	elif "manage" in req_uri:
		content = manage(environ, cfg)
	else:
		content = wildcard(environ, cfg)

	encoded = content.encode()

        start_response("200 OK", hdrs(encoded))

	return [encoded]

if __name__ == "__main__":
        httpd = make_server('', 8000, application)
        print("Serving on port 8000...")

        # Serve until process is killed
        httpd.serve_forever()
