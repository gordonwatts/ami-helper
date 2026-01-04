import logging
import sys
import subprocess
import importlib
import importlib.util


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


def ensure_setup():
    ensure_and_import("setuptools")
    ensure_and_import("wheel")
    ensure_and_import("build")
    ensure_and_import("pyAMI_atlas")


def normalize_derivation_name(content: str) -> str:
    """
    Map short names to full DAOD names, but allow any custom value.

    Args:
        content: Short name (e.g., 'phys') or full name (e.g., 'DAOD_PHYS')

    Returns:
        Full derivation name (e.g., 'DAOD_PHYS')
    """
    content_mapping = {
        "evnt": "EVNT",
        "phys": "DAOD_PHYS",
        "physlite": "DAOD_PHYSLITE",
        "EVNT": "EVNT",
        "PHYS": "DAOD_PHYS",
        "PHYSLITE": "DAOD_PHYSLITE",
    }
    return content_mapping.get(content, content)
