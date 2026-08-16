#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
bin_dir="${HOME}/.local/bin"
config_dir="${HOME}/.config/ai-notify"
state_dir="${HOME}/.local/state/ai-notify"
config_file="${config_dir}/config.json"
systemd_dir="${HOME}/.config/systemd/user"

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

if python3 -c 'import tomllib' >/dev/null 2>&1; then
  install -m 755 \
    "${project_dir}/bin/ai-notify-repair-config" \
    "${bin_dir}/ai-notify-repair-config"
  install -d -m 755 "$systemd_dir"
  install -m 644 \
    "${project_dir}/systemd/ai-notify-config-repair.service" \
    "${systemd_dir}/ai-notify-config-repair.service"
  install -m 644 \
    "${project_dir}/systemd/ai-notify-config-repair.path" \
    "${systemd_dir}/ai-notify-config-repair.path"

  if ! "${bin_dir}/ai-notify-repair-config"; then
    printf 'Warning: existing Codex or Claude configuration could not be repaired.\n' >&2
  fi
  if command -v systemctl >/dev/null 2>&1 \
    && systemctl --user daemon-reload >/dev/null 2>&1 \
    && systemctl --user enable --now ai-notify-config-repair.path >/dev/null 2>&1; then
    printf 'Enabled automatic Codex and Claude hook repair.\n'
  else
    printf 'Installed hook repair, but user systemd is unavailable; run ai-notify-repair-config manually after provider switches.\n' >&2
  fi
else
  printf 'Skipped automatic hook repair because Python 3.11 or newer is required.\n' >&2
fi

printf 'Next: edit %s, then run: %s test\n' "$config_file" "${bin_dir}/ai-notify"
