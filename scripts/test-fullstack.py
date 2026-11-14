r"""Run client tests and HTTP integration without modifying the application database.
Usage: .\.venv\Scripts\python.exe scripts\test-fullstack.py [frontend_directory]
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
frontend = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'frontend'
compiler = frontend / 'node_modules/typescript/bin/tsc'
if not compiler.is_file():
    raise SystemExit('Install frontend dependencies first: cd frontend && pnpm install --frozen-lockfile')
with tempfile.TemporaryDirectory(prefix='neighborrow-client-') as directory:
    temporary = Path(directory)
    subprocess.run(['node', str(compiler), 'lib/neighborrow-api.ts', '--outDir', str(temporary),
                    '--target', 'es2022', '--module', 'esnext', '--moduleResolution', 'bundler',
                    '--skipLibCheck'], cwd=frontend, check=True)
    module = temporary / 'neighborrow-api.mjs'
    shutil.copyfile(temporary / 'neighborrow-api.js', module)
    environment = {**os.environ, 'API_CLIENT_MODULE': str(module)}
    subprocess.run(['node', '--test', str(frontend / 'tests/api-client.test.mjs')], env=environment, check=True)
    subprocess.run([sys.executable, str(root / 'scripts/test-integration.py'), str(frontend), str(module)], check=True)
