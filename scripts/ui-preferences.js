(() => {
  const version = "full-context-host-tools-v2";
  if (localStorage.getItem("LlamaVega.preferencesVersion") === version) return;
  const read = (key, fallback) => {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
    catch { return fallback; }
  };
  const preferences = {
    temperature: 0.6, top_p: 0.95, top_k: 20, min_p: 0,
    repeat_penalty: 1, presence_penalty: 0, max_tokens: -1,
    agenticMaxTurns: 1000, showThoughtInProgress: true,
    showMessageStats: true, showAgenticTurnStats: true,
    excludeReasoningFromContext: true, titleGenerationUseLLM: false,
    titleGenerationUseFirstLine: true, jsSandboxEnabled: false
  };
  const tools = ["read_file", "file_glob_search", "grep_search", "exec_shell_command", "write_file", "edit_file", "get_info"];
  localStorage.setItem("LlamaUi.config", JSON.stringify({...read("LlamaUi.config", {}), ...preferences}));
  localStorage.setItem("LlamaUi.userOverrides", JSON.stringify([...new Set([...read("LlamaUi.userOverrides", []), ...Object.keys(preferences)])]));
  localStorage.setItem("LlamaUi.alwaysAllowedTools", JSON.stringify([...new Set([...read("LlamaUi.alwaysAllowedTools", []), ...tools.map(name => `server:${name}`)])]));
  localStorage.setItem("LlamaUi.disabledToolKeys", "[]");
  localStorage.setItem("LlamaUi.disabledToolCategories", "[]");
  localStorage.setItem("LlamaUi.reasoningEffortDefault", "none");
  localStorage.setItem("LlamaVega.preferencesVersion", version);
})();
