#!/usr/bin/env python3
import argparse
import os
import pathlib
import plistlib
import re
import shutil
import subprocess

LABEL = "local.llama-vega"


def main():
    parser = argparse.ArgumentParser(description="Run a GGUF on the Radeon through Vulkan")
    parser.add_argument("--model", type=pathlib.Path, required=True)
    parser.add_argument("--runtime", type=pathlib.Path, default=pathlib.Path.home() / ".local/share/llama-vega/runtime")
    parser.add_argument("--port", type=int, default=18435)
    parser.add_argument("--device", default="Vulkan0")
    parser.add_argument("--context", type=int, default=262144)
    parser.add_argument("--alias", default="HauhauCS-Qwen3.5-2B-Aggressive")
    parser.add_argument("--reasoning", choices=("on", "off"), default="off")
    parser.add_argument("--host-tools", action="store_true", default=True)
    parser.add_argument("--no-host-tools", dest="host_tools", action="store_false")
    parser.add_argument("--ui-path", type=pathlib.Path,
                        default=pathlib.Path.home() / ".local/share/llama-vega/ui")
    parser.add_argument("--install-service", action="store_true")
    args = parser.parse_args()
    model = args.model.expanduser().resolve()
    binary = args.runtime.expanduser().resolve() / "llama-server"
    if not model.is_file() or not binary.is_file():
        parser.error("The model file and installed llama-server must exist")
    with model.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            parser.error("The model is not a GGUF file")
    if not 1024 <= args.port <= 65535 or not 512 <= args.context <= 262144:
        parser.error("Use port 1024–65535 and context 512–262144")
    brew = shutil.which("brew") or "/usr/local/bin/brew"
    prefix = subprocess.check_output([brew, "--prefix"], text=True).strip()
    icd = pathlib.Path(prefix) / "opt/molten-vk/etc/vulkan/icd.d/MoltenVK_icd.json"
    env = dict(os.environ, VK_ICD_FILENAMES=str(icd))
    devices = subprocess.run([str(binary), "--list-devices"], env=env, capture_output=True, text=True, check=True)
    listing = devices.stdout + devices.stderr
    found = re.search(r"^\s*" + re.escape(args.device) + r":\s*(.+)$", listing, re.M)
    if not found or "AMD" not in found.group(1):
        parser.error("Selected AMD Vulkan device is unavailable; inspect --list-devices output: " + listing)
    # Fast profile (2026-09-19): 256k context, all 6 cores, GPU layers all,
    # flash-attn auto. Do not revert to -t 2 / -fa on / q8 KV / 32k context.
    command = [str(binary), "-m", str(model), "--alias", args.alias, "--host", "127.0.0.1",
               "--port", str(args.port), "--device", args.device, "-ngl", "all", "--load-mode", "none",
               "-c", str(args.context), "-np", "1", "-b", "2048", "-ub", "512", "-t", "6", "-tb", "6",
               "-fa", "auto", "--jinja", "--reasoning", args.reasoning, "--temp", "0.6", "--top-p", "0.95",
               "--top-k", "20", "--min-p", "0", "--cache-ram", "8192", "--cors-origins", "localhost", "-lv", "4",
               "--poll", "1", "--poll-batch", "1", "--threads-http", "6", "--metrics",
               "--presence-penalty", "0", "--repeat-penalty", "1"]
    if args.host_tools:
        command.extend(["--tools", "all"])
    if args.ui_path:
        ui = args.ui_path.expanduser().resolve()
        if not (ui / "index.html").is_file():
            parser.error("UI directory must contain index.html")
        command.extend(["--path", str(ui)])
    env["PATH"] = str(pathlib.Path.home() / ".local/bin") + ":" + prefix + "/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    if args.install_service:
        folder = pathlib.Path.home() / "Library/LaunchAgents"
        folder.mkdir(parents=True, exist_ok=True)
        log = pathlib.Path.home() / "Library/Logs/llama-vega.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        plist = folder / (LABEL + ".plist")
        service = {"Label": LABEL, "ProgramArguments": command,
                   "EnvironmentVariables": {"VK_ICD_FILENAMES": str(icd), "PATH": env["PATH"]},
                   "WorkingDirectory": str(pathlib.Path.home()), "RunAtLoad": False,
                   "KeepAlive": False, "ThrottleInterval": 60,
                   "StandardOutPath": str(log), "StandardErrorPath": str(log)}
        domain = "gui/" + str(os.getuid())
        subprocess.run(["launchctl", "bootout", domain + "/" + LABEL], capture_output=True)
        plist.write_bytes(plistlib.dumps(service))
        subprocess.run(["launchctl", "disable", domain + "/" + LABEL], capture_output=True)
        print("LaunchAgent written (manual start only). Does not run at login.")
        print("Start: llama start    Stop: llama stop")
        print("Chat: http://127.0.0.1:" + str(args.port))
        return
    os.chdir(pathlib.Path.home())
    os.execve(str(binary), command, env)


if __name__ == "__main__":
    main()
