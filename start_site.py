"""Start the local Flask site and open its rendered login page."""

import os
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from app import app


def open_when_ready(url):
    for _ in range(50):
        try:
            with urllib.request.urlopen(url, timeout=1):
                webbrowser.open(url)
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
    print(f"The site did not become available. Try opening {url} after checking the server output.")


if __name__ == "__main__":
    port = int(os.environ.get("APP_PORT", "5050"))
    url = f"http://127.0.0.1:{port}/login"
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(f"Port {port} is already in use. Set APP_PORT to another port and retry.")
    print(f"Starting WEALTH sense at {url}")
    threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
