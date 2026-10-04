#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

version="${1:?usage: scripts/package-armory.sh vMAJOR.MINOR.PATCH}"
if [[ ! "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "invalid package version: $version" >&2
  exit 1
fi

./scripts/build-armory-bof.sh

stage="$(mktemp -d "$PWD/build/package.XXXXXX")"
trap 'rm -rf "$stage"' EXIT
cp build/nanodump.x64.o "$stage/nanodump.x64.o"
cp LICENSE "$stage/LICENSE"

python3 - "$version" "$stage/extension.json" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path('extension.json').read_text())
manifest['version'] = sys.argv[1]
# Minisign's trusted comment includes this manifest as base64. Keep the
# archive copy compact enough for its 4096-byte signature-line limit.
Path(sys.argv[2]).write_text(json.dumps(manifest, separators=(',', ':')) + '\n')
PY

cp "$stage/extension.json" build/extension.json
COPYFILE_DISABLE=1 tar -C "$stage" -czf build/nanodump.tar.gz .
python3 scripts/validate-armory-package.py \
  --archive build/nanodump.tar.gz \
  --version "$version" \
  --expected-object build/nanodump.x64.o \
  --expected-manifest build/extension.json
