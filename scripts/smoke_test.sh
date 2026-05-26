#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
host="${COMMANDCODE_PROXY_HOST:-127.0.0.1}"
port="${COMMANDCODE_PROXY_PORT:-8788}"
base="http://$host:$port/v1"

python3 "$repo_dir/scripts/test_reasoning_mapping.py"

python3 "$repo_dir/commandcode_proxy.py" --host "$host" --port "$port" >/tmp/hermes-commandcode-provider.log 2>&1 &
pid="$!"
trap 'kill "$pid" >/dev/null 2>&1 || true; rm -f "${stream_tmp:-}"' EXIT

for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -fsS "http://$host:$port/health" >/dev/null 2>&1 && break
  sleep 0.2
done

curl -fsS "$base/models" | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["data"][0].get("context_length"); print("models ok")'

curl -fsS "$base/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"moonshotai/Kimi-K2.5","messages":[{"role":"user","content":"Reply with exactly OK."}],"max_tokens":256,"stream":false}' \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["usage"]["prompt_tokens"]; print("chat ok")'

stream_tmp="$(mktemp)"
curl -fsS -N "$base/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"moonshotai/Kimi-K2.5","messages":[{"role":"user","content":"Reply with exactly OK."}],"max_tokens":256,"stream":true,"stream_options":{"include_usage":true}}' \
  > "$stream_tmp"
grep -q '"usage"' "$stream_tmp"
rm -f "$stream_tmp"
echo "stream usage ok"

curl -fsS "$base/chat/completions" \
  -H 'Content-Type: application/json' \
  --data-binary @- <<'JSON' | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["choices"][0]["message"].get("tool_calls"); print("tool calls ok")'
{"model":"moonshotai/Kimi-K2.5","messages":[{"role":"user","content":"Call add for 2+3."}],"tools":[{"type":"function","function":{"name":"add","description":"Add two integers","parameters":{"type":"object","properties":{"a":{"type":"integer"},"b":{"type":"integer"}},"required":["a","b"]}}}],"tool_choice":"auto","max_tokens":1024,"stream":false}
JSON

echo "all smoke tests passed"
