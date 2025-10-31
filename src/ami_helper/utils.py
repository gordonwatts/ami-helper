#!/usr/bin/env python3
import logging
import sys, subprocess, importlib, importlib.util


def _try_install_pip(pkg) -> bool:
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "--no-build-isolation"],
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logging.warning(f"Failed to install package '{pkg}' via pip: {e}")
        return False


def _try_install_uv(pkg) -> bool:
    try:
        subprocess.run(
            ["uv", "pip", "install", pkg, "--no-build-isolation"],
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logging.warning(f"Failed to install package '{pkg}' via uv: {e}")
        return False


def ensure_and_import(pkg, pkg_spec=None) -> None:
    if importlib.util.find_spec(pkg) is None:
        logging.warning(f"Required python package '{pkg}' not found; installing...")
        if not _try_install_pip(pkg_spec or pkg):
            if not _try_install_uv(pkg_spec or pkg):
                raise ImportError(f"Could not install required package '{pkg}'")
        importlib.invalidate_caches()
