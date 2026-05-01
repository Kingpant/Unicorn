#!/usr/bin/env python3
"""Tiny local server — returns USB serial ports with VID/PID as JSON.
Run: python3 list-ports.py  (then open device-finder.html in Chrome)
"""
import glob, json, subprocess, re
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8765

def ioreg_vid_pid():
    """Return {path: (vid, pid)} from ioreg on macOS."""
    result = {}
    try:
        out = subprocess.check_output(
            ['ioreg', '-p', 'IOUSB', '-l'],
            stderr=subprocess.DEVNULL, text=True
        )
        # Each USB device block contains idVendor, idProduct and IODialinDevice
        for block in re.split(r'\+-o ', out):
            vid_m  = re.search(r'"idVendor"\s*=\s*(\d+)', block)
            pid_m  = re.search(r'"idProduct"\s*=\s*(\d+)', block)
            path_m = re.search(r'"IODialinDevice"\s*=\s*"([^"]+)"', block)
            if vid_m and pid_m and path_m:
                result[path_m.group(1)] = (int(vid_m.group(1)), int(pid_m.group(1)))
    except Exception:
        pass
    return result

def list_ports():
    ioreg = ioreg_vid_pid()

    # Try pyserial first (installed by ESP-IDF)
    try:
        from serial.tools import list_ports as lp
        ports = []
        for p in lp.comports():
            if not (p.device.startswith('/dev/tty.usb') or
                    p.device.startswith('/dev/tty.SLAB') or
                    p.device.startswith('/dev/ttyUSB')):
                continue
            vid, pid = p.vid, p.pid
            # Patch with ioreg if pyserial returned None
            if (vid is None or pid is None) and p.device in ioreg:
                vid, pid = ioreg[p.device]
            ports.append({'path': p.device, 'vid': vid, 'pid': pid, 'desc': p.description or ''})
        return ports
    except ImportError:
        pass

    # Fallback: glob + ioreg
    patterns = ['/dev/tty.usbserial-*', '/dev/tty.SLAB_USBtoUART*',
                '/dev/tty.usbmodem*', '/dev/ttyUSB*']
    paths = []
    for p in patterns:
        paths.extend(glob.glob(p))
    result = []
    for path in sorted(set(paths)):
        vid, pid = ioreg.get(path, (None, None))
        result.append({'path': path, 'vid': vid, 'pid': pid, 'desc': ''})
    return result

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/ports':
            body = json.dumps(list_ports()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass

if __name__ == '__main__':
    print(f'Port server running at http://localhost:{PORT}/ports')
    print('Open device-finder.html in Chrome, then press Ctrl+C to stop.\n')
    HTTPServer(('localhost', PORT), Handler).serve_forever()
