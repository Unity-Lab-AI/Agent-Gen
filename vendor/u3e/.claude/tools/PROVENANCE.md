# PROVENANCE — `.claude/tools/`

> ⛔ **VENDORED, NOT IMPORTED.** `CONSTRAINTS.md §NO CROSS-PROJECT IMPORTS`
> applies to this directory exactly as it applies to `codec/`: *"a copy that
> drifts is a visible cost; a shared import that drifts is an invisible one."*
> Nothing in this project resolves these scripts out of another repo at runtime.

---

## SOURCE

| | |
|---|---|
| **Repository** | `git@git.unityailab.com:GFourteen/tools.git` |
| **Web** | <https://git.unityailab.com/GFourteen/tools> |
| **Commit vendored** | `8463c6cd1a962e47a78e07bf8e7eea1441727eae` — *"Fix README layout overflow and chart proportions"*, 2026-10-26 02:39:50 -0600 |
| **Vendored into U3E** | 2026-10-26, task `U3E-5.105` |
| **Licence** | MIT — `LICENSE` ships beside the code |
| **Asked for by** | Gee, verbatim: *"https://git.unityailab.com/GFourteen/tools merge this into our .claudes tools and make any neccessary adjustements to the claude.md needed"* |

## WHAT WAS COPIED, AND WHETHER IT WAS TOUCHED

⭐ **Every script is BYTE-IDENTICAL to upstream** — verified with `cmp` at copy
time, hashes recorded below. ⚠ **Keep it that way.** A local edit makes the next
refresh a merge instead of a copy, and the whole reason the hashes are here is so
a later session can tell drift from an upstream change without reading both
trees.

```
  09b13befefb8987c0b7f041192e82e8df3861d850fc94c4b057d22f0def87401  browser.py
  5c25a9e3c871bac8bb182158e183e020558dfb0115bb2c49d049c3e7404e3f97  doctor.py
  2089ab5f27580fa6d78304fd97871015dc93a19cea25135403456f7ab7d9a57e  screen.py
  8b70faccd3e6e30ac187e05554cd282cf05fd5a4f4ca22fe0fd1554f0f29ca04  web.py
  43909dfe6e7a244b9f5bef489b21f2cd12b9ccbc3bbd8b093d23919f0273bb78  requirements.txt
```

Also copied verbatim: `README.md` · `LICENSE` · `install.sh` · `install.ps1`.

⚠ **`install.sh` / `install.ps1` are for pushing this toolkit OUT to other
projects**, not for installing it here — it is already here. They are kept so
the next lab project does not have to re-clone the source.

## THE ONE FILE THAT IS OURS, NOT UPSTREAM'S

`.gitattributes` in this directory is an **addition**, not a copy. Upstream's
root `.gitattributes` pins `*.sh text eol=lf` and `*.ps1 text eol=crlf`; this
repository's root `.gitattributes` carries only `* text=auto` plus the Git-LFS
rules, and `core.autocrlf` is `true` on this machine.

⛔ **Without the pin, `install.sh` checks out with CRLF on Windows and git-bash
refuses the shebang** (`bad interpreter: /usr/bin/env bash^M`). That is the same
class of failure as `CONSTRAINTS.md §CROSS-PLATFORM CASE INSENSITIVITY → THE
EXTENSIONLESS / .exe TRAP`: a copy that reports success and leaves a dead tool.

## HOW TO REFRESH FROM UPSTREAM

```bash
git clone git@git.unityailab.com:GFourteen/tools.git /tmp/tools-refresh
cd /tmp/tools-refresh && git log -1 --format=%H          # the new commit
# diff BEFORE copying — the hashes above say what we currently hold
for f in doctor.py web.py browser.py screen.py requirements.txt; do
  cmp -s "$f" "<U3E>/.claude/tools/$f" || echo "CHANGED: $f"
done
```

⛔ Then update **this file's commit line and hashes in the same commit as the
copy** — `DOCS BEFORE PUSH`. A provenance file that names the wrong commit is
worse than none, because it is believed.

## WHAT THESE TOOLS ARE NOT FOR

⛔ **Not for sourcing training data.** `feedback_no_accounts_for_sourcing` and
`U3E-2.189` are unaffected by this merge: Gee's call on 2026-09-02 was **no
sign-ins, no source API keys, no authenticated scraping**. ⚠ `browser.py` holds
logins across sessions, which makes authenticated scraping *easy* for the first
time in this project — **that does not make it allowed.** Open lanes only.
