#!/usr/bin/env python3
"""Run the full backend test suite with detailed output.

Usage:
    python backend/run_tests.py            # run everything
    python backend/run_tests.py -k cycle   # pytest -k filter
    python backend/run_tests.py --unit     # skip integration tests
    python backend/run_tests.py --no-cov   # skip coverage report

Postgres on localhost:5432 is required for integration tests; they auto-skip
if it's unreachable.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--unit", action="store_true", help="Skip integration tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--no-cov", action="store_true", help="Skip coverage summary")
    parser.add_argument("-k", dest="keyword", help="Pytest -k expression")
    parser.add_argument("extra", nargs=argparse.REMAINDER, help="Extra args passed to pytest")
    args = parser.parse_args()

    env = os.environ.copy()
    env.setdefault("IS_LOCAL", "true")
    env.setdefault("JWT_SECRET", "test-secret")

    cmd = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "--color=yes", "-ra"]
    if args.unit:
        cmd += ["--ignore=tests/test_integration.py"]
    if args.integration:
        cmd = [sys.executable, "-m", "pytest", "tests/test_integration.py", "-v", "--tb=short", "--color=yes", "-ra"]
    if args.keyword:
        cmd += ["-k", args.keyword]
    cmd += args.extra

    have_cov = shutil.which("coverage") is not None or _module_installed("coverage")
    if have_cov and not args.no_cov:
        cmd = [sys.executable, "-m", "coverage", "run", "--source=.",
               "--omit=tests/*,run_tests.py,shared.py,*/psycopg/*,*/jwt/*,*/requests/*,*/certifi/*,*/charset_normalizer/*,*/idna/*,*/urllib3/*",
               "-m", "pytest"] + cmd[3:]

    print("=" * 70)
    print(f"Running: {' '.join(cmd)}")
    print(f"CWD:     {HERE}")
    print("=" * 70)

    result = subprocess.run(cmd, cwd=HERE, env=env)

    if have_cov and not args.no_cov and result.returncode == 0:
        print("\n" + "=" * 70)
        print("Coverage report (handler code only)")
        print("=" * 70)
        subprocess.run([sys.executable, "-m", "coverage", "report", "-m",
                        "--include=*/function.py,shared.py"], cwd=HERE, env=env)

    print("\n" + "=" * 70)
    print(f"Exit code: {result.returncode}")
    print("=" * 70)
    return result.returncode


def _module_installed(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    sys.exit(main())
