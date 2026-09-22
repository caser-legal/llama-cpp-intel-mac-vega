#!/usr/bin/env python3
import argparse
import hashlib
import io
import pathlib
import shutil
import tarfile
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Install pinned UI with explicitly requested host-tool permissions")
    parser.add_argument("--allow-host-tools", action="store_true", required=True)
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home() / ".local/share/llama-vega")
    args = parser.parse_args()
    url = "https://huggingface.co/buckets/ggml-org/llama-ui/resolve/b10985/dist.tar.gz"
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != "f33bf56adfd39aba33c5c814a65bfd1ac33e62c77c8f9a4d49aeab7eb2350695":
        raise RuntimeError("UI archive checksum mismatch")
    root = args.home.expanduser().resolve() / "ui"
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            path = pathlib.PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError("Unsafe archive path")
            if not member.isfile():
                continue
            target = root.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    script = pathlib.Path(__file__).with_name("ui-preferences.js").read_text()
    index = root / "index.html"
    html = index.read_text()
    if "<head>" not in html:
        raise RuntimeError("Unexpected UI entrypoint")
    index.write_text(html.replace("<head>", "<head><script>" + script + "</script>", 1))
    print("UI preferences prepared. Launch llama-server with --path", root)


if __name__ == "__main__":
    main()
