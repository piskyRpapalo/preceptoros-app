# Private APP on Ubuntu · evidence (2026-11-16)

What this proves, and only this: the PreceptorOS APP installed from the public installer in a clean Ubuntu 24.04
container offers its nine panels, and Talk gets a **real model answer**. The model is the private APP's own
(`hexelion:latest` on another computer), reached through an authorized loopback door. This is the **private APP**
configuration, not the base product: the base product does not depend on Hexelion (see the Superbot contract, #310).

## How to reproduce

```
HEXELION_ENDPOINT=http://127.0.0.1:<door port> NODE_PATH=<playwright-core> CHROME_PATH=<chromium> SHOTS=<dir> \
  tests/ubuntu_e2e/run.sh
```
The door is a loopback port that reaches the authorized node (on the rack: an SSH tunnel). The container joins the
host network only so its loopback reaches that door; its address is never written here.

## What each step separates

- **Delivered vs answered.** `deliver_to_thread: DELIVERED_TO_THREAD` only proves that the message was stored. `model_reply: ANSWERED:hexelion:latest:…ms:1_verified_source` proves the model answered, with a verified source and its time.
- **Panels.** `browser_walk: PASS:9 panels ANSWERED` means that, in real Chromium at 420×642 against the *installed* app:
  - every tab opened its own panel with no page error (Command, Talk, Boundary, Notebook, Lab, Harness, Public gate, Models, Settings);
  - in Talk, the person's question typed in the composer got the model's answer row.
- **Honest NO_DATA kept:**
  - `hexelion_door` before memory exists;
  - `node_identity` before provisioning;
  - local inference, a native package and a signed update.

## Finding: memory still needs the terminal

A fresh install cannot talk to its model until the memory exists. Today the memory is created only by the terminal
onboarding (`preceptoros.py`, after the person's explicit yes → `memory.crear`). The APP has no button for it. The E2E calls
that same function and says so (`memory_created: PASS:explicit_onboarding_function`). To fix it, the APP needs a
visible "create my memory" step that asks for the same explicit yes.

## Receipts (`preceptoros.ubuntu-e2e/1`)

Run 1:
```json
{"schema":"preceptoros.ubuntu-e2e/1","result":"PASS","os":"Ubuntu 24.04.5 LTS","download_digest":"PASS","install_public":"PASS","installed_head":"6f5fe2e451df","desktop_validate":"PASS","desktop_entry":"PASS","launcher_starts_app":"PASS","app_shell":"PASS","hexelion_door":"NO_DATA:memory_index_unavailable","deliver_to_thread":"DELIVERED_TO_THREAD","thread_reads_back":"PASS","memory_created":"PASS:explicit_onboarding_function","fact_stored":"PASS","browser_walk":"PASS:9 panels ANSWERED","model_reply":"ANSWERED:hexelion:latest:2302ms:1_verified_source","model_discovery":"READ:ok","node_identity":"NO_DATA:identidad_no_provisionada","update_fast_forward":"PASS:0c3226b97b0e->9885e55987de","update_keeps_data":"PASS:63b34fb8d65cdf85","update_thread_kept":"PASS","rewritten_history_refused":"PASS","uninstall_keeps_dirty_tree":"PASS","uninstall_removes_app":"PASS","uninstall_keeps_data":"PASS:no terminal, so --borrar-datos is refused","offline_ai":"NO_DATA:no_model_in_container_inference_is_remote","native_package":"NO_DATA:git_clone_installer_not_deb_snap_flatpak","signed_update":"NO_DATA:fast_forward_over_https_only_commits_unsigned"}
```
Run 2:
```json
{"schema":"preceptoros.ubuntu-e2e/1","result":"PASS","os":"Ubuntu 24.04.5 LTS","download_digest":"PASS","install_public":"PASS","installed_head":"6f5fe2e451df","desktop_validate":"PASS","desktop_entry":"PASS","launcher_starts_app":"PASS","app_shell":"PASS","hexelion_door":"NO_DATA:memory_index_unavailable","deliver_to_thread":"DELIVERED_TO_THREAD","thread_reads_back":"PASS","memory_created":"PASS:explicit_onboarding_function","fact_stored":"PASS","browser_walk":"PASS:9 panels ANSWERED","model_reply":"ANSWERED:hexelion:latest:2469ms:1_verified_source","model_discovery":"READ:ok","node_identity":"NO_DATA:identidad_no_provisionada","update_fast_forward":"PASS:0c3226b97b0e->2ec2c4483dc5","update_keeps_data":"PASS:648c0bad7a4e2ad6","update_thread_kept":"PASS","rewritten_history_refused":"PASS","uninstall_keeps_dirty_tree":"PASS","uninstall_removes_app":"PASS","uninstall_keeps_data":"PASS:no terminal, so --borrar-datos is refused","offline_ai":"NO_DATA:no_model_in_container_inference_is_remote","native_package":"NO_DATA:git_clone_installer_not_deb_snap_flatpak","signed_update":"NO_DATA:fast_forward_over_https_only_commits_unsigned"}
```
