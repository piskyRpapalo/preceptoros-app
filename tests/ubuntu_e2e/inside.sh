#!/usr/bin/env bash
# Runs INSIDE a throwaway ubuntu container as an unprivileged user. Driven by tests/ubuntu_e2e/run.sh.
# Prints one JSON receipt line (preceptoros.ubuntu-e2e/1). Anything not proven here is NO_DATA in the receipt.
set -u
R=(); step() { R+=("\"$1\":\"$2\""); printf '%-34s %s\n' "$1" "$2" >&2; }
fail() { step "$1" "FAIL"; printf '{"schema":"preceptoros.ubuntu-e2e/1","result":"FAIL","failed":"%s",%s}\n' "$1" "$(IFS=,; echo "${R[*]}")"; exit 1; }
P=8740; U="http://127.0.0.1:$P"
datahash() { (cd ~/.preceptoros && find . -type f ! -name '*.log' ! -name '*-shm' ! -name '*-wal' ! -name '*.pid' -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16); }
waitup() { for _ in $(seq 1 60); do curl -fs -o /dev/null "$U/api/estado" && return 0; sleep .5; done; return 1; }
stop() { (cd "$1" && bin/preceptoros-servicio para >/dev/null 2>&1); for _ in $(seq 1 20); do curl -fs -o /dev/null "$U/api/estado" || return 0; sleep .3; done; }

# 0 · the download the website links to, checked against the published digest
echo "$EXPECTED_SHA  /in/install.sh" | sha256sum -c --quiet || fail download_digest
step download_digest PASS
cp /in/install.sh ~/install.sh && chmod +x ~/install.sh

# 1 · install from the public repository (default REPO), like a person following the website
~/install.sh >/tmp/i1.log 2>&1 || fail install_public
[ -x ~/preceptoros/bin/preceptoros-pwa ] || fail install_public
step install_public PASS
step installed_head "$(git -C ~/preceptoros rev-parse --short=12 HEAD)"
[ -f ~/.local/share/applications/preceptoros.desktop ] && grep -q '^Exec=' ~/.local/share/applications/preceptoros.desktop || fail desktop_entry
command -v desktop-file-validate >/dev/null && { desktop-file-validate ~/.local/share/applications/preceptoros.desktop >/tmp/dv.log 2>&1 && step desktop_validate PASS || step desktop_validate "WARN:$(head -c 80 /tmp/dv.log | tr '\n"' '  ')"; }
step desktop_entry PASS
[ -x ~/.local/bin/preceptoros-abrir ] || fail launcher
# the launcher itself (xdg-open has no display here: that part is NO_DATA)
~/.local/bin/preceptoros-abrir >/tmp/l.log 2>&1 || true
waitup || fail launcher_starts_app
step launcher_starts_app PASS
curl -fs "$U/app.html" | grep -q 'PreceptorOS' || fail app_shell
curl -fs "$U/manifest.json" | grep -q '"start_url"' || fail pwa_manifest
step app_shell PASS
# 2 · Hexelion: its station door (a reply needs a local model; without one the door must SAY so, not invent).
#     The shared thread (rack CLIs) must deliver and read back.
h="$(curl -s -X POST -H 'Content-Type: application/json' -H "Origin: $U" --data '{"texto":"ubuntu e2e hello"}' "$U/api/hexelion/chat")"
hs="$(printf '%s' "$h" | python3 -c 'import sys,json;d=json.load(sys.stdin);print((d.get("state") or d.get("estado") or "?")+":"+str(d.get("cause") or d.get("causa") or "")[:40])' 2>/dev/null)" || fail hexelion_door
case "$hs" in NO_DATA:*|LECTURA_LOCAL:*|ANSWERED*|MEDIDO*) step hexelion_door "$hs" ;; *) fail hexelion_door ;; esac
r="$(curl -fs -X POST -H 'Content-Type: application/json' -H "Origin: $U" --data '{"para":"claude","texto":"ubuntu e2e hello"}' "$U/api/conversacion")" || fail deliver
echo "$r" | grep -q DELIVERED_TO_THREAD || fail deliver
step deliver_to_thread DELIVERED_TO_THREAD
curl -fs "$U/api/conversacion?desde=0" | grep -q 'ubuntu e2e hello' || fail thread_reads_back
step thread_reads_back PASS
c="$(curl -fs "$U/api/cerebro" 2>/dev/null)" || fail model_discovery
step model_discovery "READ:$(printf '%s' "$c" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(str(d.get("state") or d.get("estado") or "?")[:24])' 2>/dev/null || echo unparsed)"
i="$(curl -s "$U/api/nodo/identity" 2>/dev/null | python3 -c 'import sys,json;d=json.load(sys.stdin);print(str(d.get("state") or d.get("estado") or "?")+":"+str(d.get("cause") or d.get("causa") or "")[:40])' 2>/dev/null)"; step node_identity "${i:-NO_DATA:unreadable}"
stop ~/preceptoros

# 3 · update: a mirror one commit behind -> install -> mirror advances -> install again fast-forwards
cp -r /mirror.git ~/mirror.git
NEW="$(git -C ~/mirror.git rev-parse main)"; OLD="$(git -C ~/mirror.git rev-parse main~1)"
git -C ~/mirror.git update-ref refs/heads/main "$OLD"
export PRECEPTOROS_REPO="file://$HOME/mirror.git" PRECEPTOROS_DESTINO="$HOME/p-up"
git clone -q --depth 1 --no-local "$PRECEPTOROS_REPO" ~/p-up >/dev/null 2>&1 || fail update_seed
[ "$(git -C ~/p-up rev-parse HEAD)" = "$OLD" ] || fail update_seed
(cd ~/p-up && PRECEPTOROS_PWA_PUERTO=$P bin/preceptoros-servicio arranca >/dev/null 2>&1); waitup || fail update_old_runs
curl -fs -X POST -H 'Content-Type: application/json' -H "Origin: $U" --data '{"para":"claude","texto":"before update"}' "$U/api/conversacion" | grep -q DELIVERED_TO_THREAD || fail update_old_runs
stop ~/p-up
before="$(datahash)"
git -C ~/mirror.git update-ref refs/heads/main "$NEW"
~/install.sh >/tmp/i2.log 2>&1 || fail update_runs
[ "$(git -C ~/p-up rev-parse HEAD)" = "$NEW" ] || fail update_fast_forward
step update_fast_forward "PASS:${OLD:0:12}->${NEW:0:12}"
after="$(datahash)"
[ "$before" = "$after" ] || fail update_keeps_data
step update_keeps_data "PASS:$before"
(cd ~/p-up && PRECEPTOROS_PWA_PUERTO=$P bin/preceptoros-servicio arranca >/dev/null 2>&1); waitup || fail update_new_runs
curl -fs "$U/api/conversacion?desde=0" | grep -q 'before update' || fail update_thread_kept
step update_thread_kept PASS
stop ~/p-up
# adversarial: the source rewrites history -> the installer must not move the tree
RW="$(GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t git -C ~/mirror.git commit-tree "$NEW^{tree}" -p "$OLD" -m 'rewritten')" && [ -n "$RW" ] || fail rewritten_history_setup
git -C ~/mirror.git update-ref refs/heads/main "$RW"
~/install.sh >/tmp/i3.log 2>&1
[ "$(git -C ~/p-up rev-parse HEAD)" = "$NEW" ] || fail rewritten_history_refused
step rewritten_history_refused PASS
unset PRECEPTOROS_REPO PRECEPTOROS_DESTINO

# 4 · uninstall: the app goes, the data stays; a tree with your own changes is never deleted
cp ~/p-up/empaquetado/uninstall.sh ~/uninstall.sh   # the public tree predates it; the updated one carries it
echo "mine" >> ~/p-up/README.md
PRECEPTOROS_DESTINO=~/p-up bash ~/uninstall.sh --si >/tmp/u0.log 2>&1
[ -d ~/p-up ] || fail uninstall_keeps_dirty_tree
step uninstall_keeps_dirty_tree PASS
keep="$(datahash)"
bash ~/uninstall.sh --si --borrar-datos </dev/null >/tmp/u1.log 2>&1
[ ! -e ~/.local/share/applications/preceptoros.desktop ] && [ ! -e ~/.local/bin/preceptoros-abrir ] && [ ! -d ~/preceptoros ] || fail uninstall_removes_app
step uninstall_removes_app PASS
[ "$(datahash)" = "$keep" ] || fail uninstall_keeps_data
step uninstall_keeps_data "PASS:no terminal, so --borrar-datos is refused"
step offline_ai "NO_DATA:no_model_in_container"
step native_package "NO_DATA:git_clone_installer_not_deb_snap_flatpak"
step signed_update "NO_DATA:fast_forward_over_https_only_commits_unsigned"
printf '{"schema":"preceptoros.ubuntu-e2e/1","result":"PASS","os":"%s",%s}\n' "$(. /etc/os-release; echo "$PRETTY_NAME")" "$(IFS=,; echo "${R[*]}")"
