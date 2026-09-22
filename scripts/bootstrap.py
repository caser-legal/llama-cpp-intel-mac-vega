#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import tarfile
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
LOCK = json.loads((REPO / "versions.json").read_text())


def command(args, **kwargs):
    subprocess.run([str(x) for x in args], check=True, **kwargs)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, path, expected, headers=None):
    if path.exists() and digest(path) == expected:
        return
    part = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=120) as response, part.open("wb") as output:
        shutil.copyfileobj(response, output)
    if digest(part) != expected:
        part.unlink()
        raise RuntimeError("Download checksum did not match the pinned release")
    part.replace(path)


def extract_files(archive, destination, strip, selected=None):
    with tarfile.open(archive) as stream:
        for member in stream.getmembers():
            raw = pathlib.PurePosixPath(member.name)
            if raw.is_absolute() or ".." in raw.parts:
                raise RuntimeError("Unsafe archive path")
            parts = raw.parts[strip:]
            if not parts or not member.isfile():
                continue
            if selected and parts[0] not in selected:
                continue
            target = destination.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(member.mode & 0o777)


def install_runtime(build_bin, root):
    destination = root / "runtime"
    destination.mkdir(parents=True, exist_ok=True)
    for source in build_bin.iterdir():
        keep = source.name == "llama-server" or ".dylib" in source.name
        if not keep or source.name.startswith(("libggml-metal", "libllama-cli")):
            continue
        target = destination / source.name
        if target.exists() or target.is_symlink():
            target.unlink()
        if source.is_symlink():
            target.symlink_to(source.readlink())
        else:
            shutil.copy2(source, target)
    for target in destination.iterdir():
        if target.is_symlink() or not target.is_file():
            continue
        listing = subprocess.check_output(["otool", "-l", str(target)], text=True)
        paths = re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset", listing)
        local = "@loader_path" in paths
        for old in paths:
            if str(build_bin.resolve()) in old:
                if local:
                    command(["install_name_tool", "-delete_rpath", old, target])
                else:
                    command(["install_name_tool", "-rpath", old, "@loader_path", target])
                    local = True
        command(["codesign", "--force", "--sign", "-", target], capture_output=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description="Build pinned llama.cpp with Vulkan for Intel macOS")
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home() / ".local/share/llama-vega")
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=2)
    parser.add_argument("--import-build", type=pathlib.Path, help="Use an existing build/bin from the pinned source")
    parser.add_argument("--skip-dependencies", action="store_true")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "x86_64":
        parser.error("This recipe targets Intel macOS, not Apple Silicon or Linux")
    if int(platform.mac_ver()[0].split(".")[0]) < 15:
        parser.error("This validated recipe requires macOS 15 or newer; older versions are unverified")
    root = args.home.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    brew = shutil.which("brew")
    if not brew:
        parser.error("Install Homebrew from https://brew.sh and the Xcode Command Line Tools first")
    env = dict(os.environ, HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_INSTALL_CLEANUP="1")
    if not args.skip_dependencies:
        command([brew, "install", "cmake", "vulkan-headers", "vulkan-loader", "molten-vk", "spirv-headers", "openssl@3"], env=env)
    prefix = subprocess.check_output([brew, "--prefix"], text=True).strip()
    icd = pathlib.Path(prefix) / "opt/molten-vk/etc/vulkan/icd.d/MoltenVK_icd.json"
    if not icd.exists():
        raise RuntimeError("MoltenVK ICD is missing; install molten-vk")
    if args.import_build:
        build_bin = args.import_build.expanduser().resolve()
        if not (build_bin / "llama-server").exists() or not (build_bin / "libggml-vulkan.dylib").exists():
            raise RuntimeError("Import requires a complete Vulkan build/bin")
    else:
        cache = root / "cache"
        cache.mkdir(exist_ok=True)
        shader = LOCK["shaderc"]
        bottle = cache / "shaderc.tar.gz"
        token_url = "https://ghcr.io/token?service=ghcr.io&scope=repository:homebrew/core/shaderc:pull"
        with urllib.request.urlopen(token_url, timeout=30) as response:
            token = json.load(response)["token"]
        download("https://ghcr.io/v2/homebrew/core/shaderc/blobs/sha256:" + shader["bottle_sha256"], bottle,
                 shader["bottle_sha256"], {"Authorization": "Bearer " + token})
        toolchain = root / "toolchain"
        extract_files(bottle, toolchain, 2, {"bin"})
        glslc = toolchain / "bin/glslc"
        command([glslc, "--version"])
        source = LOCK["llama_cpp"]
        archive = cache / "llama.cpp.tar.gz"
        download("https://codeload.github.com/ggml-org/llama.cpp/tar.gz/" + source["commit"], archive, source["source_sha256"])
        checkout = root / "source"
        extract_files(archive, checkout, 1)
        build = root / "build"
        command(["cmake", "-S", checkout, "-B", build, "-DGGML_METAL=OFF", "-DGGML_VULKAN=ON",
                 "-DGGML_NATIVE=ON", "-DCMAKE_BUILD_TYPE=Release", "-DLLAMA_BUILD_TESTS=OFF",
                 "-DLLAMA_BUILD_EXAMPLES=OFF", "-DLLAMA_BUILD_TOOLS=ON",
                 "-DVulkan_GLSLC_EXECUTABLE=" + str(glslc), "-DCMAKE_PREFIX_PATH=" + prefix])
        command(["nice", "-n", "15", "cmake", "--build", build, "-j", args.jobs, "--target", "llama-server"])
        build_bin = build / "bin"
    runtime = install_runtime(build_bin, root)
    env["VK_ICD_FILENAMES"] = str(icd)
    command([runtime / "llama-server", "--list-devices"], env=env)
    print("Runtime installed. No model weights were downloaded.")


if __name__ == "__main__":
    main()
