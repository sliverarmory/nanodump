#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

compiler="${CC_X64:-x86_64-w64-mingw32-gcc}"
strip="${STRIP_X64:-x86_64-w64-mingw32-strip}"

mkdir -p build
"$compiler" -masm=intel -Wall -I include -DNANO -DBOF \
  -c source/entry.c -o build/nanodump.x64.o
"$strip" --strip-unneeded build/nanodump.x64.o
