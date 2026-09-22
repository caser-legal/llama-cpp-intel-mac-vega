#!/usr/bin/env python3
import argparse
import gzip
import json
import plistlib
import subprocess
import threading
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Check real replies, throughput, and Radeon activity")
    parser.add_argument("--url", default="http://127.0.0.1:18435")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    stop = threading.Event()
    samples = []

    def sample_gpu():
        while not stop.is_set():
            try:
                data = plistlib.loads(subprocess.check_output(["ioreg", "-r", "-c", "IOAccelerator", "-a"]))
                for device in data:
                    if "Vega" in device.get("IOClass", ""):
                        stats = device.get("PerformanceStatistics", {})
                        samples.append({key: stats.get(key) for key in
                                        ("Device Utilization %", "GPU Activity(%)", "inUseVidMemoryBytes")})
            except (OSError, ValueError, subprocess.CalledProcessError):
                pass
            stop.wait(0.5)

    with urllib.request.urlopen(base + "/health", timeout=10) as response:
        if json.load(response).get("status") != "ok":
            raise RuntimeError("Server is not ready")
    request = urllib.request.Request(base + "/", headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        if b"<html" not in body.lower():
            raise RuntimeError("Built-in chat UI did not return HTML")
    worker = threading.Thread(target=sample_gpu)
    worker.start()
    checks = [
        ("What is 17 times 23? Give only the number.", lambda s: s.strip() == "391"),
        ("Name the three primary colors of light. Answer briefly.",
         lambda s: all(word in s.lower() for word in ("red", "green", "blue"))),
        ("Explain why the sky looks blue in two sentences.",
         lambda s: "scatter" in s.lower() and "blue" in s.lower()),
    ]
    failures = []
    try:
        for prompt, valid in checks:
            start = time.monotonic()
            payload = {"messages": [{"role": "user", "content": prompt}], "temperature": 0,
                       "max_tokens": 180, "chat_template_kwargs": {"enable_thinking": False}}
            request = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.load(response)
            choice = result["choices"][0]
            text = choice["message"].get("content") or ""
            passed = valid(text) and choice.get("finish_reason") == "stop"
            print(json.dumps({"prompt": prompt, "reply": text, "passed": passed,
                              "elapsed_seconds": round(time.monotonic() - start, 3),
                              "timings": result.get("timings")}), flush=True)
            if not passed:
                failures.append(prompt)
    finally:
        stop.set()
        worker.join()
    summary = {key: max((s.get(key) or 0 for s in samples), default=0) for key in
               ("Device Utilization %", "GPU Activity(%)", "inUseVidMemoryBytes")}
    print(json.dumps({"gpu_peaks": summary, "sample_count": len(samples)}))
    if failures:
        raise SystemExit("Reply checks failed; inspect the output and runtime logs")
    print("Reply and UI checks passed. Confirm Vulkan placement in the server log; GPU samples include all apps.")


if __name__ == "__main__":
    main()
