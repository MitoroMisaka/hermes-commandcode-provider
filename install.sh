#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hermes_home="${HERMES_HOME:-$HOME/.hermes}"
bin_dir="${HOME}/.local/bin"
configure=0

for arg in "$@"; do
  case "$arg" in
    --configure)
      configure=1
      ;;
    -h|--help)
      echo "Usage: ./install.sh [--configure]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$hermes_home/plugins/model-providers/commandcode" "$bin_dir"

install -m 755 "$repo_dir/commandcode_proxy.py" "$hermes_home/commandcode_proxy.py"
install -m 644 "$repo_dir/plugins/model-providers/commandcode/__init__.py" \
  "$hermes_home/plugins/model-providers/commandcode/__init__.py"
install -m 644 "$repo_dir/plugins/model-providers/commandcode/plugin.yaml" \
  "$hermes_home/plugins/model-providers/commandcode/plugin.yaml"
install -m 755 "$repo_dir/bin/hermes-commandcode" "$bin_dir/hermes-commandcode"

if [ "$configure" = 1 ]; then
  "$repo_dir/scripts/configure_hermes.py"
fi

echo "Installed Hermes Command Code provider."
echo "Run: hermes-commandcode -z 'Reply with exactly OK.'"
