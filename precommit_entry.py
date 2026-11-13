"""Pre-commit-compatible multi-file entry point. Delegates to the redacted checker."""
from pathlib import Path
import subprocess
import sys

def main(paths):
    if not paths:
        return 0
    status = 0
    for path in paths:
        # No shell and no file-name echo: config filenames can contain private data.
        try:
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('preflight.py')), path])
            # Only checker-defined statuses are trusted. Signals/unexpected exits fail closed.
            code = result.returncode if type(result.returncode) is int and result.returncode in (0, 1, 2) else 2
        except OSError:
            code = 2
        status = max(status, code)
    return status

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
