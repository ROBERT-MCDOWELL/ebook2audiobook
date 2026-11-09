#!/usr/bin/env bash
# ebook2audiobook Android: runs inside the app's Ubuntu rootfs (proot, fake root), started by E2aService.
# Installs what a minimal Ubuntu lacks (same set as the Dockerfile), clones e2a once, then hands over to the
# regular Linux launcher, which provisions uv/python/engines and serves the GUI on $E2A_INTERFACE_HOST:7860.
set -euo pipefail
export DEBIAN_FRONTEND="noninteractive"
E2A_DIR="${E2A_DIR:-/root/ebook2audiobook}"
E2A_REPO="${E2A_REPO:-https://github.com/DrewThomasson/ebook2audiobook.git}"
E2A_BRANCH="${E2A_BRANCH:-main}"
E2A_UPDATE="${E2A_UPDATE:-0}"
BASE_MARKER="/root/.e2a_base_v1"
BASE_PROGRAMS=(
	"bash" "build-essential" "ca-certificates" "cmake" "curl" "fontconfig" "git" "libegl1" "libfontconfig1"
	"libfreetype6" "libgl1" "libglib2.0-0" "libgomp1" "libnss3" "libopengl0" "libsndfile1" "libx11-6"
	"libxcb-cursor0" "libxcb-render0" "libxcb-shm0" "libxcb-xfixes0" "libxcb-xinerama0" "libxcb1" "libxext6"
	"libxkbcommon-x11-0" "libxrender1" "netcat-openbsd" "pkg-config" "procps" "tzdata" "wget" "xz-utils"
)

echo "==> ebook2audiobook for Android ($(uname -m), $(nproc) cores)"
######## an install killed halfway (app stopped, phone rebooted) leaves dpkg half configured
if [[ -n "$(ls -A /var/lib/dpkg/updates 2>/dev/null)" ]]; then
	echo "==> Finishing an interrupted package install…"
	dpkg --configure -a || true
fi
######## universe holds calibre, espeak-ng, mediainfo, sox… asked by the launcher
UBUNTU_SOURCES="/etc/apt/sources.list.d/ubuntu.sources"
if [[ -f "$UBUNTU_SOURCES" ]] && ! grep -q "universe" "$UBUNTU_SOURCES"; then
	sed -i 's/^Components:.*/Components: main restricted universe multiverse/' "$UBUNTU_SOURCES"
fi
if [[ ! -f "$BASE_MARKER" ]]; then
	echo "==> Installing base packages…"
	apt-get update
	apt-get install -y --no-install-recommends "${BASE_PROGRAMS[@]}"
	touch "$BASE_MARKER"
fi
if [[ ! -d "$E2A_DIR/.git" ]]; then
	echo "==> Downloading ebook2audiobook ($E2A_REPO, $E2A_BRANCH)…"
	rm -rf "$E2A_DIR.partial"
	git clone --depth 1 --branch "$E2A_BRANCH" "$E2A_REPO" "$E2A_DIR.partial"
	mv "$E2A_DIR.partial" "$E2A_DIR"
elif [[ "$E2A_UPDATE" == "1" ]]; then
	echo "==> Updating ebook2audiobook…"
	git -C "$E2A_DIR" pull --ff-only || echo "Update failed, keeping the installed version."
fi
cd "$E2A_DIR"
echo "==> Starting ebook2audiobook v$(<VERSION.txt) (the first start installs everything, it can take an hour or more)…"
exec ./ebook2audiobook.sh
