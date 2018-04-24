from __future__ import print_function
import pprint
import json
import copy
import re
import os
import bty
from subprocess import Popen, PIPE
from flask import Flask, render_template

REGEX_HWA = r".*(([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})).*"

CFG_FPATH="/tmp/bty.json"

DEFAULT_HOST = {
    "hwa": None,
    "img": None,
    "hostname": None,
    "managed": False,
    "pxe_default": None
}

DEFAULT_CFG = {
    "bty": {
        "root": "/srv/bty",
        "templates": "/srv/bty/templates"
    },
    "pxe": {
        "root": "/srv/tftpboot/pxelinux.cfg",
    },
    "img": {
        "root": "/srv/images"
    },
    "sys": {
        "usr": "nvm",
        "grp": 'CNEXLABS\domain^users'
    },
    "web": {
        "usr": "www-data",
        "grp": "www-data"
    },
    "machines": {}
}

CFG_FNAME = "bty.json"

PXE = {
    "cfg_path": "/srv/tftpboot/pxelinux.cfg",
    "labels": [
        "boot_hda",
        "boot_hda_bzi",
        "install"
    ],
}

def ipa_to_hwa(ipa=None):
    """
    Resolve the given IP address to HW address

    @returns hwaddr on the form AA:BB:CC:11:22:33 on success, None otherwise
    """

    if ipa is None:
        print("FAILED: ip: %r" % ipa)
        return None

    cmd = ["arp", "-a", ipa]

    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)

    out, _ = proc.communicate()
    out = out.lower() if out else ""

    match = re.match(bty.REGEX_HWA, out)
    if match:
            return match.group(1).upper()

    print("FAILED: out: %r" % out)

    return None

def hdrs(content=None, content_type=None):
    """Return headers for the given content"""

    if content is None:
        content = b""

    if content_type is None:
        content_type = "text/html"

    return  [
        ('Content-type', content_type),
        ('Content-Length', str(len(content)))
    ]

def cfg_load(cfg_fpath):
    """
    Load config from os.path.dirname("SCRIPT_FILENAME")/bty.json

    @returns config as dict on success, None otherwise
    """

    if not os.path.exists(cfg_fpath):
        print("FAILED: !exist(cfg_fpath: %r)" % cfg_fpath)
        return None

    with open(cfg_fpath, "r") as cfg_fd:
        return json.load(cfg_fd)

    return None

def cfg_save(cfg_fpath, cfg):
    """
    Store the given cfg

    @returns True on success, False otherwise
    """

    with open(cfg_fpath, "w") as cfg_fd:
        cfg = json.dump(cfg, cfg_fd, sort_keys=True, indent=2)

    return True

def pxe_config(environ, cfg, host):
    """@returns PXE config for the given host on success, None otherwise"""

    print("pxe_config")

    if not host["managed"]:
        host["hostname"] = "unmanaged"
        return None

    if None in [host["hostname"], host["hwa"]]:
        print("ERR: invalid host: %r" % host)
        return None

    host["PXE_DEFAULT"] = "boot_hd0"            # TODO: make this configurable

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
    pxe_fname = pxe_fname.lower()
    pxe_fpath = os.sep.join([PXE["cfg_fpath"], pxe_fname])

    print("pxe_fpath: %r" % pxe_fpath)

    with open(pxe_fpath, "w") as pxe_fd:
        pxe_fd.write(pxe)

app = Flask(__name__)
#app.config.from_object('websiteconfig')

cfg = cfg_load(CFG_FPATH)

@app.route("/cfg")
@app.route("/")
def app_cfg():
    """Render configuration"""

    print("## STATE")

    return render_template('ui_cfg.html', cfg=cfg)

@app.route("/bootstrap")
def app_bootstrap():
    """@returns bootstrap script for the host to run"""

    print("## bootstrap")

    if host["managed"]:             # Create PXE config for host
        pxe = pxe_config(os.environ, cfg, host)
        pxe_config_install(os.environ, cfg, host, pxe)

    return render_template(
        "bootstrap.sh" if host["managed"] else "bootstrap_cancel.sh",
        cfg=cfg,
        host=host
    )
