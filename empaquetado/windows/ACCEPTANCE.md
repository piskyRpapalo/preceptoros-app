# PreceptorOS on Windows · acceptance by a third party

State: **NO_DATA · pending external test.** Nobody on our side has run PreceptorOS on Windows. This page asks
you to, and to send back one receipt.

## What you need
- Windows 10 or 11, a normal (non-administrator) account.
- Python 3.10+ and Git. The installer tells you the exact `winget` command if one is missing.
- About 300 MB of disk and an internet connection.

## Steps
1. Download `install.ps1` from the website's App → Windows choice.
2. Read the SHA-256 published for that release, then check the download:
   `(Get-FileHash .\install.ps1 -Algorithm SHA256).Hash`
3. Download `acceptance.ps1` from the same release and read it. It is short.
4. Run, in a PowerShell window in the folder with both files:
   `powershell -ExecutionPolicy Bypass -File .\acceptance.ps1 -Installer .\install.ps1 -ExpectedSha256 <digest>`
5. It installs, starts the app on `127.0.0.1` only, checks the app shell, sends one test message, re-runs the
   installer (the update), and uninstalls. Your data folder is kept. The last line is a JSON receipt.

## What to send back
Only the last JSON line. It contains words (PASS/FAIL/NO_DATA), the Windows version number, the Python version,
a 12-character commit id and 16-character hashes. It contains **no** user name, path, computer name, IP or message
text. Read it before sending; redact anything you want.

Post it to the issue linked from the download page, or give it to the person who asked you.

## What each step proves

| Receipt key | Proves | Does not prove |
|---|---|---|
| download_digest | the file is the published one | who built it |
| install | the tree is on disk | anything about the app running |
| starts, app_shell | the server runs and serves the app on loopback | a desktop window |
| hexelion_door | Hexelion's door answers (or says NO_DATA honestly) | that a model runs |
| deliver_to_thread, thread_reads_back | the conversation store works and persists | a reply |
| model_discovery | the app can read its model list | inference |
| update_keeps_data | re-running the installer keeps your data | that an update moved the version (`update_moved` stays NO_DATA) |
| uninstall_removes_tree, uninstall_keeps_data | uninstall removes the app, keeps the data | — |

## Known gaps before you start
- `install.ps1` creates no Start-menu shortcut (`shortcut: NO_DATA`).
- Some measurements read Linux-only sources (`/proc`); on Windows they should say NO_DATA. A crash there is a
  finding: send it.
- If anything fails, the receipt says FAIL. A FAIL is useful information, not a problem for you to fix.
