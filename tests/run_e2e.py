"""Build the example site, serve it on a free port, run the browser test."""
import os
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from static import build, ultra_tool  # noqa: E402

site = os.path.join(ROOT, "example")
dist = os.path.join(site, "dist")
build(site, dist)
srv = ultra_tool().make_server(dist, 0, quiet=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
r = subprocess.run(["node", os.path.join(ROOT, "tests", "e2e.cjs")], cwd=ROOT,
                   env={**os.environ, "BASE": f"http://localhost:{srv.server_address[1]}"})
srv.shutdown()
sys.exit(r.returncode)
