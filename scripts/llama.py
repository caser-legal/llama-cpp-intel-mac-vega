#!/usr/bin/env python3
import json
import os
import pathlib
import plistlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

LABEL = "local.llama-vega"
DOMAIN = "gui/" + str(os.getuid())
SERVICE = DOMAIN + "/" + LABEL
PLIST = pathlib.Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
BINARY = pathlib.Path.home() / ".local/share/llama-vega/runtime/llama-server"
UI = pathlib.Path.home() / ".local/share/llama-vega/ui"
ICD = "/usr/local/opt/molten-vk/etc/vulkan/icd.d/MoltenVK_icd.json"
PORT = "18435"
URL = "http://127.0.0.1:" + PORT
LLMS = pathlib.Path.home() / "Documents" / "llms"

# Smallest → largest. One at a time.
MODELS = {
    1: {
        "name": "Qwen3.5-2B-Aggressive",
        "file": LLMS / "Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
        "alias": "Qwen3.5-2B-Aggressive",
        "ctx": "262144",
        "size": "1.3 GB",
        "extra": ["--reasoning", "off"],
    },
    2: {
        "name": "Gemma-4-E4B-Abliterated",
        "file": LLMS / "Huihui-gemma-4-E4B-it-abliterated.Q4_K_M.gguf",
        "alias": "Gemma-4-E4B-Abliterated",
        "ctx": "32768",
        "size": "5.3 GB",
        "extra": [],
    },
    3: {
        "name": "Qwen3.5-9B-Abliterated",
        "file": LLMS / "Huihui-Qwen3.5-9B-abliterated.Q4_K_M.gguf",
        "alias": "Qwen3.5-9B-Abliterated",
        "ctx": "32768",
        "size": "5.6 GB",
        "extra": ["--reasoning", "off"],
    },
    4: {
        "name": "Gemma-4-12B-Abliterated",
        "file": LLMS / "Huihui-gemma-4-12B-it-abliterated.Q4_K_M.gguf",
        "alias": "Gemma-4-12B-Abliterated",
        "ctx": "8192",
        "size": "7.4 GB",
        "extra": [],
    },
}


def launchctl(*args):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def require(result):
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "launchctl failed")


def usage():
    lines = [
        "One model at a time. Smallest first.",
        "",
        "  llama1 start     Qwen3.5 2B          1.3 GB   256k ctx",
        "  llama2 start     Gemma 4 E4B         5.3 GB    32k ctx",
        "  llama3 start     Qwen3.5 9B          5.6 GB    32k ctx",
        "  llama4 start     Gemma 4 12B         7.4 GB     8k ctx",
        "  llama1 stop      (or llama2/3/4 stop, or llama stop)",
        "",
        "Starting any slot stops the one that is already running.",
    ]
    raise SystemExit("\n".join(lines))


def parse_argv(argv):
    invoked = pathlib.Path(argv[0]).name
    rest = argv[1:]
    slot = None
    m = re.fullmatch(r"llama([1-4])", invoked)
    if m:
        slot = int(m.group(1))
    elif rest and rest[0] in ("1", "2", "3", "4"):
        slot = int(rest[0])
        rest = rest[1:]
    action = rest[0] if rest else "start"
    if action not in ("start", "stop") or len(rest) > 1:
        usage()
    if action == "start" and slot is None:
        usage()
    return slot, action


def stop_running():
    state = launchctl("print", SERVICE)
    match = re.search(r"^\s*pid = (\d+)$", state.stdout, re.M)
    launchctl("disable", SERVICE)
    if state.returncode == 0:
        launchctl("bootout", SERVICE)
    if match:
        pid = int(match.group(1))
        for _ in range(150):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("The model process is still shutting down")
    # leftover child llama-server from router mode
    subprocess.run(["pkill", "-f", str(BINARY)], capture_output=True)


def write_plist(model):
    command = [
        str(BINARY),
        "-m", str(model["file"]),
        "--alias", model["alias"],
        "--host", "127.0.0.1",
        "--port", PORT,
        "--device", "Vulkan0",
        "-ngl", "all",
        "--load-mode", "none",
        "-c", model["ctx"],
        "-np", "1",
        "-b", "2048",
        "-ub", "512",
        "-t", "6",
        "-tb", "6",
        "-fa", "auto",
        "--jinja",
        "--temp", "0.6",
        "--top-p", "0.95",
        "--top-k", "20",
        "--min-p", "0",
        "--cache-ram", "8192",
        "--cors-origins", "localhost",
        "-lv", "4",
        "--poll", "1",
        "--poll-batch", "1",
        "--threads-http", "6",
        "--metrics",
        "--presence-penalty", "0",
        "--repeat-penalty", "1",
        "--tools", "all",
        "--path", str(UI),
        *model["extra"],
    ]
    log = str(pathlib.Path.home() / "Library/Logs/llama-vega.log")
    service = {
        "Label": LABEL,
        "ProgramArguments": command,
        "EnvironmentVariables": {
            "VK_ICD_FILENAMES": ICD,
            "PATH": str(pathlib.Path.home() / ".local/bin") + ":/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "WorkingDirectory": str(pathlib.Path.home()),
        "RunAtLoad": False,
        "KeepAlive": False,
        "ThrottleInterval": 60,
        "StandardOutPath": log,
        "StandardErrorPath": log,
    }
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps(service))


def start_slot(slot):
    model = MODELS[slot]
    if not model["file"].is_file():
        raise RuntimeError("Missing model file: " + str(model["file"]))
    if not BINARY.is_file():
        raise RuntimeError("Missing llama-server at " + str(BINARY))
    print("Stopping any running model…", flush=True)
    stop_running()
    write_plist(model)
    require(launchctl("enable", SERVICE))
    result = None
    for _ in range(20):
        result = launchctl("bootstrap", DOMAIN, str(PLIST))
        if result.returncode == 0 or launchctl("print", SERVICE).returncode == 0:
            break
        time.sleep(0.25)
    else:
        require(result)
    require(launchctl("kickstart", SERVICE))
    print("Starting llama" + str(slot) + "  " + model["name"] + "  (" + model["size"] + ")…", flush=True)
    deadline = 180 if slot >= 3 else 90
    for _ in range(deadline):
        try:
            with urllib.request.urlopen(URL + "/health", timeout=2) as response:
                if json.load(response).get("status") == "ok":
                    subprocess.run(["open", "-a", "Safari", URL + "/"], check=True)
                    print("Llama" + str(slot) + " ready. Safari opened. Only this model is loaded.")
                    return
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
            pass
        time.sleep(1)
    raise RuntimeError("Model startup timed out; check ~/Library/Logs/llama-vega.log")


def main():
    slot, action = parse_argv(sys.argv)
    if action == "stop":
        stop_running()
        print("Llama stopped. GPU memory released.")
        return
    start_slot(slot)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
