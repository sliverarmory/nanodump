#!/usr/bin/env python3
"""Validate the NanoDump Armory archive and optional minisign signature."""

import argparse
import base64
import json
from pathlib import Path
import re
import struct
import subprocess
import tarfile


ARGUMENTS = [
    ("pid", "int"),
    ("dump-path", "string"),
    ("write-file", "int"),
    ("chunk-size", "int"),
    ("valid-sig", "int"),
    ("fork", "int"),
    ("snapshot", "int"),
    ("duplicate", "int"),
    ("elevate-handle", "int"),
    ("duplicate-elevate", "int"),
    ("getpid", "int"),
    ("seclogon-local", "int"),
    ("seclogon-remote", "int"),
    ("seclogon-binary", "string"),
    ("seclogon-duplicate", "int"),
    ("spoof-callstack", "int"),
    ("silent-process-exit", "int"),
    ("silent-process-exit-path", "string"),
    ("shtinkering", "int"),
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-object", type=Path)
    parser.add_argument("--expected-manifest", type=Path)
    parser.add_argument("--signature", type=Path)
    parser.add_argument("--public-key")
    args = parser.parse_args()

    require(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.version), "invalid version")
    require(bool(args.signature) == bool(args.public_key), "signature and public key must be supplied together")

    with tarfile.open(args.archive, "r:gz") as archive:
        members = archive.getmembers()
        files = [member for member in members if member.isfile()]
        names = {member.name for member in files}
        require(names == {"./extension.json", "./nanodump.x64.o", "./LICENSE"},
                f"unexpected archive contents: {sorted(names)}")
        require(len(files) == len(names) and all(member.isfile() or (member.isdir() and member.name == ".") for member in members),
                "duplicate or non-regular archive member")
        manifest_bytes = archive.extractfile("./extension.json").read()
        object_bytes = archive.extractfile("./nanodump.x64.o").read()
        license_bytes = archive.extractfile("./LICENSE").read()

    manifest = json.loads(manifest_bytes)
    require(manifest.get("version") == args.version, "manifest version differs from tag")
    require(manifest.get("name") == "nanodump", "unexpected package name")
    require(manifest.get("command_name") == "nanodump", "unexpected command name")
    require(manifest.get("repo_url") == "https://github.com/sliverarmory/nanodump", "unexpected repository URL")
    require(manifest.get("bof_executor") == "reflektor", "BOF does not select Reflektor")
    require("depends_on" not in manifest, "unexpected loader dependency")
    require(manifest.get("entrypoint") == "go", "unexpected BOF entrypoint")
    require(manifest.get("files") == [{"os": "windows", "arch": "amd64", "path": "nanodump.x64.o"}],
            "unexpected BOF target or path")
    actual_arguments = [(arg.get("name"), arg.get("type")) for arg in manifest.get("arguments", [])]
    require(actual_arguments == ARGUMENTS, "manifest arguments differ from upstream BOF ABI")
    require(all(arg.get("optional") is True for arg in manifest["arguments"]), "required BOF argument has no default")
    require(manifest["arguments"][2].get("default") == 1, "disk output must be the default")
    require(manifest["arguments"][3].get("default") == 921600, "unexpected chunk size default")
    require(manifest["arguments"][4].get("default") == 1, "valid signature must be the default")
    require(object_bytes[:2] == struct.pack("<H", 0x8664), "BOF is not AMD64 COFF")
    require(b"MIT License" in license_bytes and b"Fortra" in license_bytes, "current upstream license missing")

    if args.expected_object:
        require(object_bytes == args.expected_object.read_bytes(), "packaged BOF differs from tested build")
    if args.expected_manifest:
        require(manifest_bytes == args.expected_manifest.read_bytes(), "staged manifest differs from archive")

    if args.signature:
        subprocess.run(
            ["minisign", "-Vm", str(args.archive), "-x", str(args.signature), "-P", args.public_key],
            check=True,
        )
        lines = args.signature.read_text().splitlines()
        require(len(lines) >= 4 and lines[2].startswith("trusted comment: "), "missing trusted manifest")
        trusted_manifest = base64.b64decode(lines[2].split(": ", 1)[1], validate=True)
        require(trusted_manifest == manifest_bytes, "signed manifest differs from archive")

    print(f"validated NanoDump {args.version}: Reflektor, Windows/amd64, 19 arguments")


if __name__ == "__main__":
    main()
