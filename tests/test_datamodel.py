import json

import pytest

from ami_helper.datamodel import (
    CentralPageHashAddress,
    get_campaign,
    make_central_page_hash_address,
)


class TestMakeCentralPageHashAddress:
    """Tests for make_central_page_hash_address function."""

    def test_pmgl1_hash_scope(self):
        """Test creating address with PMGL1 hash scope."""
        result = make_central_page_hash_address("mc16", "PMGL1", "hash123")
        assert result.scope == "mc16"
        assert result.hash_tags == ("hash123", None, None, None)

    def test_pmgl2_hash_scope(self):
        """Test creating address with PMGL2 hash scope."""
        result = make_central_page_hash_address("mc20", "PMGL2", "hash456")
        assert result.scope == "mc20"
        assert result.hash_tags == (None, "hash456", None, None)

    def test_pmgl3_hash_scope(self):
        """Test creating address with PMGL3 hash scope."""
        result = make_central_page_hash_address("mc23", "PMGL3", "hash789")
        assert result.scope == "mc23"
        assert result.hash_tags == (None, None, "hash789", None)

    def test_pmgl4_hash_scope(self):
        """Test creating address with PMGL4 hash scope."""
        result = make_central_page_hash_address("mc16", "PMGL4", "hashABC")
        assert result.scope == "mc16"
        assert result.hash_tags == (None, None, None, "hashABC")

    def test_invalid_hash_scope_raises_value_error(self):
        """Test that an invalid hash scope raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            make_central_page_hash_address("mc16", "INVALID_SCOPE", "hash123")

        # Check that the error message is informative
        assert "Unknown hash scope: INVALID_SCOPE" in str(exc_info.value)
        assert "legal ones:" in str(exc_info.value)

    def test_returns_central_page_hash_address_type(self):
        """Test that the function returns the correct type."""
        result = make_central_page_hash_address("mc16", "PMGL1", "test")
        assert isinstance(result, CentralPageHashAddress)


class TestGetCampaign:
    """Tests for get_campaign function."""

    def test_mc23a_fullsim_match(self):
        """Dataset containing a known FS tag combination should map to mc23a."""
        dataset = "mc23_13p6TeV.801167.DAOD_LLP1.e12345_s4162_r15540_p5678"
        assert get_campaign("mc23", dataset) == "mc23a - FS"

    def test_mc23d_af3_match(self):
        """Dataset containing a known AF3 tag combination should map to mc23d."""
        dataset = "mc23_13p6TeV.801168.AOD.e12345_a910_r15224_p5678"
        assert get_campaign("mc23", dataset) == "mc23d - AF3"

    def test_no_match_raises(self):
        """A dataset without recognizable tag combo should raise ValueError."""
        with pytest.raises(ValueError):
            get_campaign("mc23", "mc23_13p6TeV.some.dataset.without.tags")


class TestCentralPageHashAddressSerialization:
    """Tests for CentralPageHashAddress JSON serialization."""

    def test_to_dict_with_all_tags(self):
        """Test to_dict() with all hashtags filled."""
        addr = CentralPageHashAddress(
            scope="mc23_13p6TeV", hash_tags=("Top", "TTbar", "Baseline", "Pythia")
        )
        result = addr.to_dict()
        assert result == {
            "scope": "mc23_13p6TeV",
            "hash_tags": ["Top", "TTbar", "Baseline", "Pythia"],
        }

    def test_to_dict_with_none_tags(self):
        """Test to_dict() with some None hashtags."""
        addr = CentralPageHashAddress(
            scope="mc16_13TeV", hash_tags=("Top", None, "Baseline", None)
        )
        result = addr.to_dict()
        assert result == {
            "scope": "mc16_13TeV",
            "hash_tags": ["Top", None, "Baseline", None],
        }

    def test_from_dict_with_all_tags(self):
        """Test from_dict() with all hashtags filled."""
        data = {
            "scope": "mc23_13p6TeV",
            "hash_tags": ["Top", "TTbar", "Baseline", "Pythia"],
        }
        addr = CentralPageHashAddress.from_dict(data)
        assert addr.scope == "mc23_13p6TeV"
        assert addr.hash_tags == ("Top", "TTbar", "Baseline", "Pythia")

    def test_from_dict_with_none_tags(self):
        """Test from_dict() with some None hashtags."""
        data = {
            "scope": "mc16_13TeV",
            "hash_tags": ["Top", None, "Baseline", None],
        }
        addr = CentralPageHashAddress.from_dict(data)
        assert addr.scope == "mc16_13TeV"
        assert addr.hash_tags == ("Top", None, "Baseline", None)

    def test_roundtrip_serialization(self):
        """Test that to_dict() and from_dict() are inverses."""
        original = CentralPageHashAddress(
            scope="mc20_13TeV", hash_tags=("JetPhoton", "Dijet", None, "Sherpa")
        )
        data = original.to_dict()
        restored = CentralPageHashAddress.from_dict(data)
        assert restored == original
        assert restored.scope == original.scope
        assert restored.hash_tags == original.hash_tags

    def test_json_dumps_with_to_dict(self):
        """Test that to_dict() output can be JSON serialized."""
        addr = CentralPageHashAddress(
            scope="mc23_13p6TeV", hash_tags=("Top", "TTbar", "Baseline", "Pythia")
        )
        json_str = json.dumps(addr.to_dict())
        assert isinstance(json_str, str)
        # Verify it can be parsed back
        parsed = json.loads(json_str)
        assert parsed["scope"] == "mc23_13p6TeV"
        assert parsed["hash_tags"] == ["Top", "TTbar", "Baseline", "Pythia"]

    def test_json_roundtrip(self):
        """Test full JSON serialization and deserialization."""
        original = CentralPageHashAddress(
            scope="mc16_13TeV", hash_tags=("Top", None, "Baseline", "PowhegPythia")
        )
        # Serialize to JSON
        json_str = json.dumps(original.to_dict())
        # Deserialize from JSON
        data = json.loads(json_str)
        restored = CentralPageHashAddress.from_dict(data)
        # Verify equality
        assert restored == original
        assert hash(restored) == hash(original)
