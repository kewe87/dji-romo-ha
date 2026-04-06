#!/usr/bin/env python3
"""
DJI Home Credential Extractor for Rooted Android Devices
=========================================================

Extracts the User Token and Device Serial Number from a rooted
Android device running the DJI Home app via ADB over WiFi.

Requirements:
  - Python 3.10+
  - ADB (Android Debug Bridge) installed on your PC
  - Rooted Android device with DJI Home app installed and logged in
  - ADB wireless debugging enabled on the device

Usage:
  python extract_credentials.py
"""

import os
import re
import shutil
import subprocess
import sys


def find_adb() -> str | None:
    """Find the ADB executable on the system."""
    adb = shutil.which("adb")
    if adb:
        return adb

    candidates = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(local, "Android", "Sdk", "platform-tools", "adb.exe"),
            os.path.join(home, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"),
            r"C:\Program Files\Android\platform-tools\adb.exe",
        ]
    else:
        candidates = [
            os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
            "/opt/android-sdk/platform-tools/adb",
        ]

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def run(adb: str, *args: str, timeout: int = 30) -> tuple[bool, str]:
    """Run an ADB command. Returns (success, output)."""
    cmd = [adb] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, f"Could not run: {adb}"


def check_adb_version(adb: str) -> bool:
    """Verify ADB is functional."""
    ok, out = run(adb, "version")
    if ok and "Android Debug Bridge" in out:
        version = out.split("\n")[0]
        print(f"  ADB: {version}")
        return True
    print(f"  ADB found but not working: {out}")
    return False


def check_device_reachable(adb: str, ip: str, port: str) -> bool:
    """Check if device IP is reachable."""
    if sys.platform == "win32":
        ping_cmd = ["ping", "-n", "1", "-w", "2000", ip]
    else:
        ping_cmd = ["ping", "-c", "1", "-W", "2", ip]
    try:
        result = subprocess.run(ping_cmd, capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def main():
    print()
    print("=" * 60)
    print("  DJI Home Credential Extractor")
    print("  for rooted Android devices")
    print("=" * 60)
    print()

    # ---- Step 1: Check ADB ----
    print("Step 1: Checking prerequisites")
    print("-" * 40)

    adb = find_adb()
    if not adb:
        print("  ERROR: ADB not found!")
        print()
        print("  Install Android SDK Platform Tools:")
        print("    https://developer.android.com/tools/releases/platform-tools")
        print()
        print("  Or install via package manager:")
        print("    Windows:  winget install Google.PlatformTools")
        print("    macOS:    brew install android-platform-tools")
        print("    Linux:    sudo apt install adb")
        sys.exit(1)

    if not check_adb_version(adb):
        sys.exit(1)

    # Check Python version
    if sys.version_info < (3, 10):
        print(f"  ERROR: Python 3.10+ required, you have {sys.version}")
        sys.exit(1)
    print(f"  Python: {sys.version.split()[0]}")
    print()

    # ---- Step 2: Connect to device ----
    print("Step 2: Connect to your device")
    print("-" * 40)
    print()
    print("  On your Android device:")
    print("  1. Settings > Developer Options > Wireless Debugging")
    print("  2. Enable Wireless Debugging")
    print("  3. Tap 'Pair with pairing code' (if first time)")
    print()

    pair = input("  Do you need to pair first? (y/N): ").strip().lower()
    if pair == "y":
        print()
        print("  Look at the pairing dialog on your device.")
        pair_ip = input("  Pairing IP:Port (e.g. 192.168.1.100:43567): ").strip()
        if not pair_ip or ":" not in pair_ip:
            print("  ERROR: Invalid format. Use IP:PORT (e.g. 192.168.1.100:43567)")
            sys.exit(1)
        pair_code = input("  6-digit pairing code: ").strip()
        if not pair_code or len(pair_code) != 6 or not pair_code.isdigit():
            print("  ERROR: Pairing code must be exactly 6 digits")
            sys.exit(1)

        ok, out = run(adb, "pair", pair_ip, pair_code)
        if "Successfully" not in out:
            print(f"  ERROR: Pairing failed: {out}")
            sys.exit(1)
        print("  Paired successfully!")
        print()

    print("  Now look at the main 'Wireless Debugging' screen.")
    print("  It shows IP address and Port (NOT the pairing port).")
    print()
    ip = input("  Device IP (e.g. 192.168.1.100): ").strip()
    if not ip:
        print("  ERROR: No IP provided")
        sys.exit(1)

    # Validate IP format
    parts = ip.split(".")
    if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        print(f"  ERROR: Invalid IP address: {ip}")
        sys.exit(1)

    port = input("  Connection port (e.g. 40475): ").strip()
    if not port or not port.isdigit():
        print(f"  ERROR: Invalid port: {port}")
        sys.exit(1)

    # Check if device is reachable
    print(f"\n  Pinging {ip}...", end=" ")
    if not check_device_reachable(adb, ip, port):
        print("FAILED")
        print(f"  ERROR: Device {ip} is not reachable on the network")
        print("  Check that your PC and device are on the same WiFi network")
        sys.exit(1)
    print("OK")

    # Connect
    target = f"{ip}:{port}"
    print(f"  Connecting to {target}...", end=" ")
    ok, out = run(adb, "connect", target)
    if "connected" not in out.lower():
        print("FAILED")
        print(f"  ERROR: {out}")
        print()
        print("  Possible causes:")
        print("  - Wrong port (make sure it's the CONNECTION port, not the pairing port)")
        print("  - Wireless debugging is disabled")
        print("  - Device needs to be re-paired")
        sys.exit(1)
    print("OK")
    print()

    # ---- Step 3: Check root ----
    print("Step 3: Checking root access")
    print("-" * 40)
    print("  Requesting root...", end=" ")
    ok, out = run(adb, "-s", target, "shell", "su -c id")
    if "uid=0" not in out:
        print("WAITING")
        print("  Check your device for a Magisk/Superuser popup and ALLOW it")
        input("  Press Enter when you have granted root access...")
        print("  Retrying...", end=" ")
        ok, out = run(adb, "-s", target, "shell", "su -c id")
        if "uid=0" not in out:
            print("FAILED")
            print(f"  ERROR: Root access denied: {out}")
            print()
            print("  Your device must be rooted (Magisk, KernelSU, etc.)")
            print("  and the shell must be granted superuser access")
            sys.exit(1)
    print("OK (root confirmed)")

    # Check for 'strings' command on device
    print("  Checking 'strings' command...", end=" ")
    ok, out = run(adb, "-s", target, "shell", "su -c 'which strings'")
    if not ok or not out:
        print("FAILED")
        print("  ERROR: 'strings' command not found on device")
        print("  Install busybox or toybox on your rooted device")
        sys.exit(1)
    print("OK")
    print()

    # ---- Step 4: Check DJI Home app ----
    print("Step 4: Checking DJI Home app")
    print("-" * 40)

    # Check if app is installed
    print("  Checking installation...", end=" ")
    ok, out = run(adb, "-s", target, "shell", "pm list packages com.dji.home")
    if "com.dji.home" not in out:
        print("FAILED")
        print("  ERROR: DJI Home app is not installed on this device")
        sys.exit(1)
    print("OK")

    # Check if app is running
    print("  Checking if app is running...", end=" ")
    ok, pid_out = run(adb, "-s", target, "shell", "su -c 'pidof com.dji.home'")
    if not pid_out or not pid_out.strip():
        print("NOT RUNNING")
        print()
        print("  Please open the DJI Home app and log in to your account.")
        print("  Make sure your robot is visible on the main screen.")
        input("  Press Enter when ready...")
        ok, pid_out = run(adb, "-s", target, "shell", "su -c 'pidof com.dji.home'")
        if not pid_out or not pid_out.strip():
            print("  ERROR: DJI Home app is still not running")
            sys.exit(1)

    pid = pid_out.strip().split()[0]
    if not pid.isdigit():
        print(f"  ERROR: Invalid PID: {pid}")
        sys.exit(1)
    print(f"OK (PID: {pid})")
    print()

    # ---- Step 5: Extract credentials ----
    print("Step 5: Extracting credentials")
    print("-" * 40)
    print("  Dumping app memory (this may take 10-30 seconds)...")

    ok, out = run(
        adb, "-s", target, "shell",
        f"su -c 'dd if=/proc/{pid}/mem bs=1M skip=32 count=480 of=/data/local/tmp/heap.bin 2>&1'",
        timeout=120,
    )
    # dd reports I/O errors for unreadable regions, that's normal
    print("  Memory dump complete")

    # Check dump file exists
    ok, out = run(adb, "-s", target, "shell", "su -c 'ls -la /data/local/tmp/heap.bin'")
    if "heap.bin" not in out:
        print("  ERROR: Memory dump failed - file not created")
        sys.exit(1)

    # Extract token
    print("  Searching for user token...", end=" ")
    ok, token_out = run(
        adb, "-s", target, "shell",
        "su -c 'strings /data/local/tmp/heap.bin | grep -oE \"US_[A-Za-z0-9_-]{50,}\" | sort -u | head -1'",
        timeout=120,
    )
    token = token_out.strip() if token_out.strip().startswith("US_") else None
    print("FOUND" if token else "NOT FOUND")

    # Extract serial number
    print("  Searching for device serial number...", end=" ")
    ok, sn_out = run(
        adb, "-s", target, "shell",
        "su -c 'strings /data/local/tmp/heap.bin | grep -oE '\"'\"'\"sn\":\"[A-Za-z0-9]+\"'\"'\"' | sort -u | head -1'",
        timeout=120,
    )
    sn_match = re.search(r'"sn":"([A-Za-z0-9]+)"', sn_out) if sn_out else None
    sn = sn_match.group(1) if sn_match else None
    print("FOUND" if sn else "NOT FOUND")

    # Extract ROMO ID
    print("  Searching for ROMO ID...", end=" ")
    ok, romo_out = run(
        adb, "-s", target, "shell",
        "su -c 'strings /data/local/tmp/heap.bin | grep -oE \"ROMO-[A-Z0-9]+\" | sort -u | head -1'",
        timeout=120,
    )
    romo_id = romo_out.strip() if romo_out.strip().startswith("ROMO-") else None
    print("FOUND" if romo_id else "NOT FOUND")

    # Cleanup
    print("  Cleaning up...", end=" ")
    run(adb, "-s", target, "shell", "su -c 'rm -f /data/local/tmp/heap.bin'")
    print("OK")

    # ---- Results ----
    print()
    print("=" * 60)
    print("  RESULTS")
    print("=" * 60)
    print()

    if token:
        print(f"  User Token:  {token}")
    else:
        print("  User Token:  NOT FOUND")

    if sn:
        print(f"  Device SN:   {sn}")
    else:
        print("  Device SN:   NOT FOUND")

    if romo_id:
        print(f"  ROMO ID:     {romo_id}")

    print()

    if token and sn:
        print("  Copy these values into Home Assistant:")
        print("  Settings > Devices & Services > Add Integration > DJI Romo")
    else:
        print("  Extraction incomplete.")
        print()
        if not token:
            print("  Token not found:")
            print("  - Make sure you are logged in to the DJI Home app")
            print("  - Navigate to the main screen where your robot is visible")
            print("  - Try again")
        if not sn:
            print("  Serial number not found:")
            print("  - Make sure your robot is paired in the app")
            print("  - Try again")
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
