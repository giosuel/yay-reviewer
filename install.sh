#!/usr/bin/env bash
# Links yay-review from this repository into ~/.local/bin. (aur-review stays in
# the repo; yay-review finds it next to its own real location.)
#
# Runs as your normal user (no sudo): yay, makepkg and claude all run as you.
# Safe to run repeatedly. Copies or links pointing elsewhere are replaced by
# links to this repo; a copy that differs from the repo version is backed up
# to $BACKUP_ROOT first.
set -euo pipefail

# Resolve the repo folder from the script's real location, so it works from
# any working directory and through symlinks.
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
REPO_DIR="$(dirname "$SELF")"

if [[ $EUID -eq 0 ]]; then
    echo "ERROR: run this as your normal user, not root" >&2
    exit 1
fi

BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
BACKUP_ROOT="${BACKUP_ROOT:-${XDG_STATE_HOME:-$HOME/.local/state}/aur-review/backups}"
BACKUP_DIR="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)"

SCRIPTS=(yay-review)
OBSOLETE=(aur-update aur-review)  # earlier versions linked these too

# ---- Checks -----------------------------------------------------------------
for f in "${SCRIPTS[@]}"; do
    if [[ ! -f "$REPO_DIR/$f" ]]; then
        echo "ERROR: $REPO_DIR/$f is missing" >&2
        exit 1
    fi
    chmod 755 "$REPO_DIR/$f"
done
for cmd in yay claude git python3; do
    command -v "$cmd" >/dev/null || echo "WARNING: '$cmd' not found in PATH" >&2
done

# ---- Linking ----------------------------------------------------------------
# link_file <source in repo> <destination>
link_file() {
    local src="$1" dst="$2"

    # Already a link to the right file: nothing to do
    if [[ -L "$dst" && "$(readlink -f "$dst")" == "$src" ]]; then
        echo "  ok       $dst (already linked)"
        return
    fi

    if [[ -d "$dst" && ! -L "$dst" ]]; then
        echo "ERROR: $dst is a directory, refusing to replace it" >&2
        exit 1
    fi

    if [[ -L "$dst" ]]; then
        echo "  relink   $dst (was -> $(readlink "$dst"))"
    elif [[ -e "$dst" ]]; then
        # Old copied setup. Keep a backup if it differs from the repo version.
        if ! cmp -s "$src" "$dst"; then
            mkdir -p "$BACKUP_DIR"
            cp -a "$dst" "$BACKUP_DIR/"
            echo "  backup   $dst -> $BACKUP_DIR/ (differed from repo)"
        fi
        echo "  replace  $dst (was a copy)"
    else
        echo "  link     $dst"
    fi

    ln -sfn "$src" "$dst"
}

# ---- Cleanup of links from earlier versions --------------------------------
for f in "${OBSOLETE[@]}"; do
    dst="$BIN_DIR/$f"
    if [[ -L "$dst" && "$(readlink -f "$dst")" == "$REPO_DIR/"* ]]; then
        rm "$dst"
        echo "  remove   $dst (no longer installed)"
    fi
done

echo "Linking files from $REPO_DIR"
mkdir -p "$BIN_DIR"
for f in "${SCRIPTS[@]}"; do
    link_file "$REPO_DIR/$f" "$BIN_DIR/$f"
done

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo; echo "WARNING: $BIN_DIR is not in your PATH" ;;
esac

echo
echo "Done. Use yay-review like yay, e.g.: yay-review -Syu"
