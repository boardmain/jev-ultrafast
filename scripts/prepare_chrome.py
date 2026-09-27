"""Prepare a local macOS Chrome instance for Browser Harness."""

import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

CHROME_DATA = Path.home() / "Library/Application Support/Google/Chrome"
DEVTOOLS_PORT = CHROME_DATA / "DevToolsActivePort"
INSPECT_URL = "chrome://inspect/#remote-debugging"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def wait_for_devtools(timeout=120):
    if DEVTOOLS_PORT.exists():
        return
    run("open", "-a", "Google Chrome", INSPECT_URL)
    print('In Chrome, enable "Allow remote debugging for this browser instance".')
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if DEVTOOLS_PORT.exists():
            return
        time.sleep(0.25)
    raise RuntimeError(f"Chrome did not create {DEVTOOLS_PORT} within {timeout} seconds")


def verify_connection(browser_harness):
    process = subprocess.Popen(
        [browser_harness],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write("ensure_real_tab()\nprint(page_info())\n")
    process.stdin.close()

    approval_needed = threading.Event()

    def relay_output():
        for line in process.stdout:
            print(line, end="")
            if "mac-approve" in line or "Allow remote debugging?" in line:
                approval_needed.set()

    output_thread = threading.Thread(target=relay_output, daemon=True)
    output_thread.start()
    deadline = time.monotonic() + 30
    approved = False
    while process.poll() is None and time.monotonic() < deadline:
        if approval_needed.is_set() and not approved:
            approved = True
            if subprocess.run([browser_harness, "mac-approve"], check=False).returncode:
                process.terminate()
                process.wait()
                raise RuntimeError("Chrome approval failed; grant Terminal Accessibility access and retry")
        time.sleep(0.1)
    if process.poll() is None:
        process.terminate()
        process.wait()
        raise RuntimeError("Browser Harness connection timed out")
    output_thread.join()
    if process.returncode:
        raise RuntimeError("Browser Harness could not connect to Chrome")


def main():
    if sys.platform != "darwin":
        raise RuntimeError("This preparation script currently supports macOS only")
    browser_harness = shutil.which("browser-harness")
    if not browser_harness:
        raise RuntimeError("browser-harness is unavailable; run this script with 'uv run'")
    wait_for_devtools()
    run(browser_harness, "--reload")
    verify_connection(browser_harness)
    run(browser_harness, "--doctor")
    print("Chrome is ready for Jev Ultrafast.")


if __name__ == "__main__":
    main()