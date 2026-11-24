"""
memwatch.py — sample whole-process-tree RSS and report new peaks.

Usage: python memwatch.py <PID>

Polls every 0.25 s. Prints a line each time a new peak is set.
Ctrl-C to stop; prints final summary on exit.
"""
import psutil
import time
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python memwatch.py <PID>")
        sys.exit(1)

    root_pid = int(sys.argv[1])
    root = psutil.Process(root_pid)
    peak = 0.0
    peak_count = 0

    print(f"Watching PID {root_pid} and its children. Ctrl-C to stop.", flush=True)

    try:
        while True:
            try:
                procs = [root] + root.children(recursive=True)
                total = sum(p.memory_info().rss for p in procs if p.is_running())
            except psutil.NoSuchProcess:
                print("Root process exited.")
                break

            mb = total / 1024 / 1024
            if mb > peak:
                peak = mb
                peak_count += 1
                names = [p.name() for p in procs if p.is_running()]
                print(f"new peak #{peak_count}: {peak:.1f} MB  ({len(procs)} procs: {names})", flush=True)

            time.sleep(0.25)

    except KeyboardInterrupt:
        pass

    print(f"\n=== Final peak: {peak:.1f} MB ===")


if __name__ == "__main__":
    main()
