""" Dev -> IK 27/03/26
SAR Sensor CSV Logger
Reads CSV from Arduino over serial and saves to ~/Downloads every 5 seconds.

Change to true in arduino sketch for code to log to CSV and not in a human-readable format
    #define CSV_MODE

Install dependency for code to work:
    pip3 install pyserial
"""

# Imports
import sys
import os
import glob
import time
import csv
import serial


# Config
BAUD_RATE    = 115200
SAVE_EVERY_S = 5
DOWNLOADS    = os.path.expanduser("~/Downloads/SARImplementation")
OUTFILE      = os.path.join(DOWNLOADS, "sar_log.csv")  # fixed name, overwritten each save


def find_arduino_port():
    """Return the most likely Arduino serial port on macOS."""
    candidates = (
        glob.glob("/dev/tty.usbmodem*") +
        glob.glob("/dev/tty.usbserial*") +
        glob.glob("/dev/tty.SLAB_USBtoUART*")
    )
    if not candidates:
        raise RuntimeError(
            "No Arduino port found. Plug in your board, or pass the port "
            "as a command-line argument:\n  python3 sar_logger.py /dev/tty.usbmodem101"
        )
    if len(candidates) > 1:
        print(f"[info] Multiple ports found: {candidates}")
        print(f"[info] Using {candidates[0]} — pass a different port as an argument if wrong.")
    return candidates[0]


def _save(path, lines):
    """Overwrite the file with every raw CSV line collected"""
    try:
        with open(path, "w", newline="") as f:
            for line in lines:
                f.write(line + "\n")
        print(f"[save] wrote {len(lines)} lines → {path}")
    except Exception as e:
        print(f"[error] could not write file: {e}")


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_arduino_port()
    print(f"[info] Connecting to {port} at {BAUD_RATE} baud …")

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=2)
    except serial.SerialException as e:
        sys.exit(f"[error] Could not open port: {e}")

    time.sleep(2)
    ser.reset_input_buffer()

    # Write an empty file immediately so it exists to the script
    _save(OUTFILE, ["# waiting for data…"])

    csv_lines  = []   # raw text lines
    last_save  = time.monotonic()
    total_rows = 0

    print(f"[info] Logging to: {OUTFILE}")
    print(f"[info] Saving every {SAVE_EVERY_S}s  |  Ctrl-C to stop\n")

    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            print(f"[raw] {repr(line)}")

            if not line:
                continue

            # Always collect the header row
            if line.startswith("pulse,"):
                if not csv_lines:
                    csv_lines.append(line)
                    print(f"[header] {line}")
                continue

            # Skip obvious non-CSV lines
            if line.startswith("#") or line.startswith("=") or line.startswith("-") or line.startswith(" "):
                print(f"[skip] {line}")
                continue

            # Accept any line that has at least one comma
            if "," not in line:
                print(f"[skip] no comma: {line}")
                continue

            csv_lines.append(line)
            total_rows += 1
            print(f"[row {total_rows}] {line}")

            now = time.monotonic()
            if now - last_save >= SAVE_EVERY_S:
                _save(OUTFILE, csv_lines)
                last_save = now

    except KeyboardInterrupt:
        print("\n[info] Ctrl-C — saving …")
    finally:
        _save(OUTFILE, csv_lines)
        ser.close()
        print(f"[info] Done. {total_rows} rows saved to: {OUTFILE}")


if __name__ == "__main__":
    main()