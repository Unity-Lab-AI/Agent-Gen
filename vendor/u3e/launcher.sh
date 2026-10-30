#!/usr/bin/env bash
# launcher.sh -- U3E-2.199b. ONE RUN: switchboard up, page open.
#
#   Gee: "so the person can just open this one page and do everything".
#   index.html opens over file:// and a file:// page cannot start a process, so
#   something has to hold the shell. This starts that something and then opens
#   the page, which finds it and grows on/off switches on every card.
#
#   Idempotent: if :8799 is already listening the switchboard is NOT started
#   twice, it just opens the page.

set -u
cd "$(dirname "$0")"

listening() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:8799 -sTCP:LISTEN >/dev/null 2>&1
  else
    # ⚠ bash's own /dev/tcp, so a machine with neither lsof nor ss still answers
    #   the question rather than guessing at it.
    (exec 3<>/dev/tcp/127.0.0.1/8799) >/dev/null 2>&1
  fi
}

if listening; then
  echo "  switchboard already running on :8799"
else
  echo "  starting switchboard on 127.0.0.1:8799 ..."
  nohup node serve/launcher.mjs > .launcher.log 2>&1 &
  sleep 2
fi

echo "  opening index.html"
PAGE="file://$(pwd)/index.html"
if   command -v xdg-open >/dev/null 2>&1; then xdg-open "$PAGE"
elif command -v open     >/dev/null 2>&1; then open "$PAGE"
else
  # ⛔ ABSENT SAYS ABSENT. No opener is not a failure to hide — it is a URL to
  #   paste, and printing it is more use than a silent exit 0.
  echo "  no xdg-open/open on this machine. Paste this into a browser:"
  echo "  $PAGE"
fi
