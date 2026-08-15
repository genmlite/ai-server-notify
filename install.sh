#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
bin_dir="${HOME}/.local/bin"
config_dir="${HOME}/.config/ai-notify"
state_dir="${HOME}/.local/state/ai-notify"
config_file="${config_dir}/config.json"

install -d -m 700 "$config_dir" "$state_dir"
install -d -m 755 "$bin_dir"
install -m 755 "${project_dir}/bin/ai-notify" "${bin_dir}/ai-notify"
install -m 755 "${project_dir}/bin/notify-run" "${bin_dir}/notify-run"

if [[ ! -e "$config_file" ]]; then
  install -m 600 "${project_dir}/examples/config.json" "$config_file"
  printf 'Created %s; replace the example topic before testing.\n' "$config_file"
else
  printf 'Preserved existing configuration: %s\n' "$config_file"
fi

printf 'Installed ai-notify and notify-run in %s\n' "$bin_dir"
printf 'Next: edit %s, then run: %s test\n' "$config_file" "${bin_dir}/ai-notify"
