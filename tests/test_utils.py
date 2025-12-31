"""Tests for utils module."""

from ami_helper.utils import normalize_derivation_name


def test_normalize_derivation_name_uppercase():
    """Test that uppercase short name PHYS maps to DAOD_PHYS."""
    assert normalize_derivation_name("PHYS") == "DAOD_PHYS"


def test_normalize_derivation_name_lowercase():
    """Test that lowercase short names are normalized."""
    assert normalize_derivation_name("phys") == "DAOD_PHYS"
    assert normalize_derivation_name("physlite") == "DAOD_PHYSLITE"
    assert normalize_derivation_name("evnt") == "EVNT"


def test_normalize_derivation_name_already_normalized():
    """Test that already normalized names pass through."""
    assert normalize_derivation_name("DAOD_PHYS") == "DAOD_PHYS"
    assert normalize_derivation_name("DAOD_PHYSLITE") == "DAOD_PHYSLITE"
    assert normalize_derivation_name("EVNT") == "EVNT"


def test_normalize_derivation_name_custom():
    """Test that custom derivation names pass through unchanged."""
    assert normalize_derivation_name("DAOD_LLP1") == "DAOD_LLP1"
    assert normalize_derivation_name("CUSTOM_TYPE") == "CUSTOM_TYPE"
