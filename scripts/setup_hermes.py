#!/usr/bin/env python3
import argparse
import pathlib
import yaml
from install_minimal_prompt import install


def main():
    parser = argparse.ArgumentParser(description="Configure an existing Hermes installation; does not run Hermes")
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home() / ".hermes")
    parser.add_argument("--url", default="http://127.0.0.1:18435/v1")
    parser.add_argument("--model", default="HauhauCS-Qwen3.5-2B-Aggressive")
    parser.add_argument("--context", type=int, default=262144)
    parser.add_argument("--allow-host-tools", action="store_true")
    parser.add_argument("--repo", type=pathlib.Path, help="Hermes source checkout; defaults to HOME/hermes-agent")
    parser.add_argument("--standard-prompt", action="store_true", help="Skip lightweight setup and preserve existing prompt/tool preferences")
    args = parser.parse_args()
    path = args.home.expanduser().resolve() / "config.yaml"
    if not path.is_file():
        parser.error("Install Hermes first; config.yaml was not found")
    config = yaml.safe_load(path.read_text()) or {}
    if not args.standard_prompt:
        install(args.repo or path.parent / "hermes-agent")
    config["model"] = {"default": args.model, "provider": "custom", "base_url": args.url,
                       "api_key": "local", "api_mode": "chat_completions",
                       "context_length": args.context, "supports_vision": False}
    config.setdefault("providers", {})["vega"] = {
        "api": args.url, "api_key": "local", "transport": "chat_completions",
        "models": {args.model: {"context_length": args.context, "supports_vision": False}}}
    config.setdefault("terminal", {}).update({"backend": "local", "cwd": str(pathlib.Path.home()), "timeout": 600})
    config.setdefault("agent", {}).update({"reasoning_effort": "high", "max_turns": 1000})
    if not args.standard_prompt:
        agent = config["agent"]
        agent.update({"base_system_prompt": "You are a helpful assistant.",
                      "compact_tool_descriptions": True, "system_prompt": "",
                      "reasoning_effort": "none", "coding_context": "off"})
        for key in ("execution_guidance", "tool_use_enforcement", "task_completion_guidance",
                    "parallel_tool_call_guidance", "environment_probe", "bot_mode_protocol"):
            agent[key] = False
        config["toolsets"] = ["terminal", "file"]
        config.setdefault("platform_toolsets", {})["cli"] = ["terminal", "file"]
        config.setdefault("display", {})["personality"] = ""
        config["model"]["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    config.setdefault("compression", {}).update({
        "enabled": True, "threshold": 0.85, "threshold_tokens": None,
        "model_thresholds": {}, "idle_compact_after_seconds": 0,
        "micro_compact": False, "proactive_prune_tokens": 0,
        "tail_mode": "lean", "target_ratio": 0.2, "in_place": True})
    config.setdefault("local_runtime", {})["enabled"] = False
    auxiliary = config.setdefault("auxiliary", {})
    auxiliary.setdefault("title_generation", {})["enabled"] = False
    for task in ("compression", "skills_hub", "mcp", "memory_query_rewrite", "tts_audio_tags"):
        auxiliary.setdefault(task, {}).update({"provider": "main", "timeout": 180})
    auxiliary["compression"]["timeout"] = 600
    if args.allow_host_tools:
        config.setdefault("approvals", {}).update({"mode": "off", "deny": []})
        config.setdefault("security", {}).update({"tirith_enabled": False,
                                                   "protected_instruction_files": False,
                                                   "allow_private_urls": True})
        config["hooks_auto_accept"] = True
    temporary = path.with_suffix(".yaml.tmp")
    temporary.write_text(yaml.safe_dump(config, sort_keys=False))
    temporary.chmod(0o600)
    temporary.replace(path)
    print("Hermes configured. Run llama, then launch Hermes yourself.")


if __name__ == "__main__":
    main()
