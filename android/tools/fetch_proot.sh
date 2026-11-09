#!/usr/bin/env bash
# Puts Termux's proot build (proot + loader + libtalloc + libandroid-shmem) in app/src/main/jniLibs/<abi>/ as lib*.so:
# Android only lets an app execute files from its native library dir, which it fills from jniLibs on install.
# Needs curl, dpkg-deb and sha256sum (any Debian/Ubuntu host, GitHub runners included).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
JNI_DIR="$SCRIPT_DIR/../app/src/main/jniLibs"
TERMUX_REPO="${TERMUX_REPO:-https://packages.termux.dev/apt/termux-main}"
PACKAGES=("proot" "libtalloc" "libandroid-shmem")
ARCHS=("aarch64:arm64-v8a" "x86_64:x86_64")
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

pkg_field() {
	# $1 Packages index, $2 package, $3 field
	awk -v pkg="$2" -v field="$3:" '$1 == "Package:" { cur = $2 } cur == pkg && $1 == field { print $2; exit }' "$1"
}

for pair in "${ARCHS[@]}"; do
	arch="${pair%%:*}"
	abi="${pair#*:}"
	index="$WORK_DIR/Packages-$arch"
	root="$WORK_DIR/root-$arch"
	echo "==> $abi"
	curl -fsSL --retry 4 "$TERMUX_REPO/dists/stable/main/binary-$arch/Packages" -o "$index"
	for pkg in "${PACKAGES[@]}"; do
		filename="$(pkg_field "$index" "$pkg" "Filename")"
		sha256="$(pkg_field "$index" "$pkg" "SHA256")"
		version="$(pkg_field "$index" "$pkg" "Version")"
		if [[ -z "$filename" || -z "$sha256" ]]; then echo "$pkg not found in the $arch index" >&2; exit 1; fi
		deb="$WORK_DIR/$pkg-$arch.deb"
		curl -fsSL --retry 4 "$TERMUX_REPO/$filename" -o "$deb"
		echo "$sha256  $deb" | sha256sum -c --quiet -
		dpkg-deb -x "$deb" "$root"
		echo "    $pkg $version"
	done
	prefix="$root/data/data/com.termux/files/usr"
	out="$JNI_DIR/$abi"
	rm -rf "$out"
	mkdir -p "$out"
	install -m 755 "$prefix/bin/proot" "$out/libproot.so"
	install -m 755 "$prefix/libexec/proot/loader" "$out/libproot-loader.so"
	if [[ -f "$prefix/libexec/proot/loader32" ]]; then install -m 755 "$prefix/libexec/proot/loader32" "$out/libproot-loader32.so"; fi
	# proot asks for libtalloc.so.2: the app links that name to libtalloc.so at runtime (Proot.prepare)
	install -m 755 "$(readlink -f "$prefix/lib/libtalloc.so.2")" "$out/libtalloc.so"
	install -m 755 "$prefix/lib/libandroid-shmem.so" "$out/libandroid-shmem.so"
	if command -v readelf >/dev/null 2>&1; then
		needed="$(readelf -d "$out/libproot.so" | awk '/NEEDED/ { gsub(/[\[\]]/, "", $NF); print $NF }' | tr '\n' ' ')"
		echo "    proot needs: $needed"
		for lib in $needed; do
			case "$lib" in
				libtalloc.so.2|libandroid-shmem.so|libc.so|libdl.so|libm.so|liblog.so) ;;
				*) echo "unexpected dependency $lib: add it to PACKAGES and Proot.kt" >&2; exit 1 ;;
			esac
		done
	fi
done
echo "==> proot runtime ready in $JNI_DIR"
