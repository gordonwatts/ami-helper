import pytest

from src.ami_helper.utils import ensure_and_import


@pytest.fixture(autouse=True)
def ensure_pyami_installed():
    """Ensure pyAMI_atlas is importable before each test.

    This mirrors the behavior in `__main__.py` where the package is
    required at runtime. The fixture is autouse so it's executed for
    every test automatically.
    """
    # Make sure installation has completed
    ensure_and_import("pyAMI_atlas")
    yield
