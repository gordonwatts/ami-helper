import re
import tempfile
from unittest.mock import MagicMock, patch

import diskcache
import pytest

from src.ami_helper.ami import DOMObject  # Import DOMObject for spec
from src.ami_helper.ami import (
    find_dids_with_hashtags,
    find_dids_with_name,
    find_hashtag,
    find_missing_tag,
    get_metadata,
    get_provenance,
    set_cache,
)
from src.ami_helper.datamodel import CentralPageHashAddress


@pytest.fixture(autouse=True)
def temp_cache():
    """Create a temporary cache for each test and clean it up after."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = diskcache.Cache(tmpdir)
        set_cache(cache)
        yield cache
        cache.close()
        set_cache(None)  # Reset to default after test


def test_find_hashtag_returns_names():
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {"NAME": "tag1", "SCOPE": "PMGL1"},
        {"NAME": "tag2", "SCOPE": "PMGL3"},
    ]

    mock_scope_tags = {"scope": MagicMock(evgen=MagicMock(short="short"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ), patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        result = find_hashtag("scope_extra", "fork")
        assert len(result) == 2
        assert all("scope_extra" == r.scope for r in result)
        assert result[0].hash_tags[0] == "tag1"
        assert result[1].hash_tags[2] == "tag2"


def test_find_hashtag_sql_command():
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []

    mock_scope_tags = {"scope": MagicMock(evgen=MagicMock(short="short"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute, patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        find_hashtag("scope_extra", "fork")
        expected_cmd = (
            'SearchQuery -catalog="short_001:production" '
            '-entity="HASHTAGS" '
            "-mql=\"SELECT DISTINCT `NAME`,`SCOPE` WHERE LOWER(`NAME`) LIKE '%fork%'\""
        )
        mock_execute.assert_called_once_with(expected_cmd)


def test_find_missing_tag_sql_command_with_two_tags():
    """Test that find_missing_tag generates correct SQL with two existing tags."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    # Create an address with tags at positions 0 and 2, missing at position 1
    test_addr = CentralPageHashAddress(
        scope="mc16_13TeV", hash_tags=["tag1", None, "tag3", None]
    )

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute, patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        find_missing_tag(test_addr, missing_index=1)

        # Verify the SQL command structure
        mock_execute.assert_called_once()
        actual_cmd = mock_execute.call_args[0][0]

        # Check catalog and entity
        assert 'SearchQuery -catalog="mc15_001:production"' in actual_cmd
        assert '-entity="DATASET"' in actual_cmd

        # Check the SQL contains the key components
        assert "-sql=" in actual_cmd
        # Should have join between DATASET and HASHTAGS
        assert "`DATASET`" in actual_cmd
        assert "`HASHTAGS`" in actual_cmd
        # Should filter by PMGL2 (missing_index + 1)
        assert "`SCOPE`=`PMGL2`" in actual_cmd or "PMGL2" in actual_cmd
        # Should have subqueries for h1 and h3
        assert "h1" in actual_cmd
        assert "h3" in actual_cmd
        # Should filter by the tag values
        assert "tag1" in actual_cmd
        assert "tag3" in actual_cmd


def test_find_missing_tag_sql_command_with_one_tag():
    """Test that find_missing_tag generates correct SQL with one existing tag."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []

    mock_scope_tags = {"mc23": MagicMock(evgen=MagicMock(short="mc23"))}

    # Create an address with only one tag at position 0, missing at position 3
    test_addr = CentralPageHashAddress(
        scope="mc23_13TeV", hash_tags=["onlytag", None, None, None]
    )

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute, patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        find_missing_tag(test_addr, missing_index=3)

        # Verify the SQL command structure
        mock_execute.assert_called_once()
        actual_cmd = mock_execute.call_args[0][0]

        # Check catalog
        assert 'SearchQuery -catalog="mc23_001:production"' in actual_cmd
        # Should filter by PMGL4 (missing_index=3, so 3 + 1)
        assert "PMGL4" in actual_cmd
        # Should have subquery for h1
        assert "h1" in actual_cmd
        # Should filter by the tag value
        assert "onlytag" in actual_cmd
        # Should have PMGL1 for the first tag
        assert "PMGL1" in actual_cmd


def test_find_missing_tag_sql_structure():
    """Test the exact SQL structure generated by find_missing_tag."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    # Create address with tags at positions 0, 1, and 3; missing at position 2
    test_addr = CentralPageHashAddress(
        scope="mc16_13TeV", hash_tags=["tag1", "tag2", None, "tag4"]
    )

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute, patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        find_missing_tag(test_addr, missing_index=2)

        mock_execute.assert_called_once()
        actual_cmd = mock_execute.call_args[0][0]

        # Extract the SQL from the command
        sql_match = re.search(r'-sql="([^"]+)"', actual_cmd)
        assert sql_match, "Could not find SQL in command"
        sql = sql_match.group(1)

        # Verify key SQL components
        # Should select SCOPE and NAME with DISTINCT
        assert "SELECT DISTINCT" in sql
        assert "`SCOPE`" in sql
        assert "`NAME`" in sql
        # Should join DATASET and HASHTAGS tables
        assert "`DATASET`" in sql
        assert "JOIN `HASHTAGS`" in sql
        # Should have WHERE clause for the missing tag level (PMGL3)
        assert "`SCOPE`='PMGL3'" in sql or "`SCOPE`=`PMGL3`" in sql
        # Should have subqueries with IN clauses for each existing tag
        assert "`IDENTIFIER` IN" in sql
        # Should reference h1, h2, and h4 aliases (for the three existing tags)
        assert "`h1`" in sql
        assert "`h2`" in sql
        assert "`h4`" in sql
        # Should filter by tag values
        assert "'tag1'" in sql
        assert "'tag2'" in sql
        assert "'tag4'" in sql
        # Should have correct PMGL scopes for each tag
        assert "`SCOPE`='PMGL1'" in sql
        assert "`SCOPE`='PMGL2'" in sql
        assert "`SCOPE`='PMGL4'" in sql
        # Should NOT reference h3 (that's the missing one)
        assert "`h3`" not in sql, "Should not have h3 alias for the missing tag"


def test_find_missing_tag_returns_addresses():
    """Test that find_missing_tag returns correct CentralPageHashAddress objects."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {"HASHTAGS.NAME": "newtag1", "HASHTAGS.SCOPE": "PMGL2"},
        {"HASHTAGS.NAME": "newtag2", "HASHTAGS.SCOPE": "PMGL2"},
    ]

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    test_addr = CentralPageHashAddress(
        scope="mc16_13TeV", hash_tags=["tag1", None, None, None]
    )

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ), patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        result = find_missing_tag(test_addr, missing_index=1)

        # Should return 2 addresses
        assert len(result) == 2
        # All should have the same scope
        assert all(r.scope == "mc16_13TeV" for r in result)
        # Should have the original tag at position 0
        assert all(r.hash_tags[0] == "tag1" for r in result)
        # Should have the new tags at position 1 (order may vary)
        tags_at_position_1 = {r.hash_tags[1] for r in result}
        assert tags_at_position_1 == {"newtag1", "newtag2"}


def test_find_dids_with_hashtags_command():
    """Test that find_dids_with_hashtags generates the correct AMI command."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []

    # Create an address with all 4 hashtags filled
    test_addr = CentralPageHashAddress(
        scope="mc23_13p6TeV", hash_tags=["Top", "TTbar", "Baseline", "PowhegPythia"]
    )

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute:
        find_dids_with_hashtags(test_addr)

        # Verify the command structure
        mock_execute.assert_called_once()
        actual_cmd = mock_execute.call_args[0][0]

        # Check the command format
        assert actual_cmd.startswith("DatasetWBListDatasetsForHashtag")
        assert '-scope="PMGL1,PMGL2,PMGL3,PMGL4"' in actual_cmd
        assert '-name="Top,TTbar,Baseline,PowhegPythia"' in actual_cmd
        assert '-operator="AND"' in actual_cmd


def test_find_dids_with_hashtags_returns_filtered_ldns():
    """Test that find_dids_with_hashtags filters results by scope."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {"ldn": "mc23_13p6TeV.123456.dataset1"},
        {"ldn": "mc21_13TeV.654321.dataset2"},  # Different scope, should be filtered
        {"ldn": "mc23_13p6TeV.789012.dataset3"},
    ]

    test_addr = CentralPageHashAddress(
        scope="mc23_13p6TeV", hash_tags=["Top", "TTbar", "Baseline", "PowhegPythia"]
    )

    with patch("src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object):
        result = find_dids_with_hashtags(test_addr)

        # Should only return ldns matching the scope
        assert len(result) == 2
        assert "mc23_13p6TeV.123456.dataset1" in result
        assert "mc23_13p6TeV.789012.dataset3" in result
        assert "mc21_13TeV.654321.dataset2" not in result


def test_find_dids_with_name_require_pmg_true():
    """Test find_dids_with_name with require_pmg=True uses inner joins."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute, patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        find_dids_with_name("mc16_13TeV", "ttbar", require_pmg=True)

        mock_execute.assert_called_once()
        actual_cmd = mock_execute.call_args[0][0]

        # Check catalog and entity
        assert 'SearchQuery -catalog="mc15_001:production"' in actual_cmd
        assert '-entity="DATASET"' in actual_cmd

        # Extract SQL
        sql_match = re.search(r'-sql="([^"]+)"', actual_cmd)
        assert sql_match, "Could not find SQL in command"
        sql = sql_match.group(1)

        # Should use JOIN (not LEFT JOIN) when require_pmg=True
        assert "JOIN" in sql
        assert "LEFT JOIN" not in sql or "LEFT" not in sql.replace("LEFT JOIN", "")

        # Should have all 4 PMGL hashtag tables
        assert "`h1`" in sql
        assert "`h2`" in sql
        assert "`h3`" in sql
        assert "`h4`" in sql

        # Should filter by name
        assert "ttbar" in sql

        # Should filter by EVNT datatype
        assert "EVNT" in sql

        # Should have a LIMIT clause (MSSQL uses FETCH NEXT syntax)
        assert "FETCH NEXT 100 ROWS ONLY" in sql or "LIMIT 100" in sql


def test_find_dids_with_name_require_pmg_false():
    """Test find_dids_with_name with require_pmg=False uses left joins."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []

    mock_scope_tags = {"mc23": MagicMock(evgen=MagicMock(short="mc23"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute, patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        find_dids_with_name("mc23_13p6TeV", "singletop", require_pmg=False)

        mock_execute.assert_called_once()
        actual_cmd = mock_execute.call_args[0][0]

        # Check catalog
        assert 'SearchQuery -catalog="mc23_001:production"' in actual_cmd

        # Extract SQL
        sql_match = re.search(r'-sql="([^"]+)"', actual_cmd)
        assert sql_match, "Could not find SQL in command"
        sql = sql_match.group(1)

        # Should use LEFT JOIN when require_pmg=False
        assert "LEFT JOIN" in sql

        # Should still have all 4 PMGL hashtag tables
        assert "`h1`" in sql
        assert "`h2`" in sql
        assert "`h3`" in sql
        assert "`h4`" in sql

        # Should filter by name
        assert "singletop" in sql

        # Should filter by EVNT datatype
        assert "EVNT" in sql


def test_find_dids_with_name_returns_results():
    """Test that find_dids_with_name returns correct tuples of (ldn, address)."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {
            "LOGICALDATASETNAME": "mc16_13TeV.123456.dataset1.EVNT",
            "h1.NAME PMGL1": "Top",
            "h2.NAME PMGL2": "TTbar",
            "h3.NAME PMGL3": "Baseline",
            "h4.NAME PMGL4": "PowhegPythia",
        },
        {
            "LOGICALDATASETNAME": "mc16_13TeV.654321.dataset2.EVNT",
            "h1.NAME PMGL1": "Top",
            "h2.NAME PMGL2": "SingleTop",
            "h3.NAME PMGL3": "Wt",
            "h4.NAME PMGL4": "PowhegPythia",
        },
    ]

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ), patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        result = find_dids_with_name("mc16_13TeV", "ttbar", require_pmg=True)

        # Should return 2 tuples
        assert len(result) == 2

        # Check first result
        ldn1, addr1 = result[0]
        assert ldn1 == "mc16_13TeV.123456.dataset1.EVNT"
        assert addr1.scope == "mc16_13TeV"
        assert addr1.hash_tags == ["Top", "TTbar", "Baseline", "PowhegPythia"]

        # Check second result
        ldn2, addr2 = result[1]
        assert ldn2 == "mc16_13TeV.654321.dataset2.EVNT"
        assert addr2.scope == "mc16_13TeV"
        assert addr2.hash_tags == ["Top", "SingleTop", "Wt", "PowhegPythia"]


def test_find_dids_with_name_with_none_hashtags():
    """Test that find_dids_with_name handles None/empty hashtags when require_pmg=False."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {
            "LOGICALDATASETNAME": "mc23_13p6TeV.789012.dataset3.EVNT",
            "h1.NAME PMGL1": "Physics",
            "h2.NAME PMGL2": "",
            "h3.NAME PMGL3": None,
            "h4.NAME PMGL4": "Generator",
        },
    ]

    mock_scope_tags = {"mc23": MagicMock(evgen=MagicMock(short="mc23"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ), patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        result = find_dids_with_name("mc23_13p6TeV", "test", require_pmg=False)

        # Should return 1 tuple
        assert len(result) == 1

        ldn, addr = result[0]
        assert ldn == "mc23_13p6TeV.789012.dataset3.EVNT"
        assert addr.scope == "mc23_13p6TeV"
        # Empty strings and None values should be in the hash_tags list
        assert len(addr.hash_tags) == 4
        assert addr.hash_tags[0] == "Physics"
        assert addr.hash_tags[3] == "Generator"


def test_find_dids_with_name_sql_structure():
    """Test the exact SQL structure generated by find_dids_with_name."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []

    mock_scope_tags = {"mc21": MagicMock(evgen=MagicMock(short="mc16"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute, patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        find_dids_with_name("mc21_13TeV", "zprime", require_pmg=True)

        mock_execute.assert_called_once()
        actual_cmd = mock_execute.call_args[0][0]

        # Extract SQL
        sql_match = re.search(r'-sql="([^"]+)"', actual_cmd)
        assert sql_match, "Could not find SQL in command"
        sql = sql_match.group(1)

        # Should have SELECT with all hashtag names
        assert "SELECT" in sql
        assert "`LOGICALDATASETNAME`" in sql
        assert "PMGL1" in sql
        assert "PMGL2" in sql
        assert "PMGL3" in sql
        assert "PMGL4" in sql

        # Should have WHERE clauses
        assert "WHERE" in sql
        assert "`LOGICALDATASETNAME` LIKE '%zprime%'" in sql
        assert "`DATATYPE`='EVNT'" in sql or "`DATATYPE`=`EVNT`" in sql

        # Should have LIMIT 100 (MSSQL uses FETCH NEXT syntax)
        assert "FETCH NEXT 100 ROWS ONLY" in sql or "LIMIT 100" in sql


def test_find_dids_with_name_scope_parsing():
    """Test that find_dids_with_name correctly parses the scope."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []

    mock_scope_tags = {"mc20": MagicMock(evgen=MagicMock(short="mc15"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute, patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        # Pass a scope with underscore - should split and use first part
        find_dids_with_name("mc20_13TeV", "test", require_pmg=True)

        mock_execute.assert_called_once()
        actual_cmd = mock_execute.call_args[0][0]

        # Should use mc15 (from mock_scope_tags["mc20"])
        assert 'SearchQuery -catalog="mc15_001:production"' in actual_cmd


def test_get_metadata_returns_friendly_mapping():
    """Ensure get_metadata maps AMI column names to user-friendly keys and returns values."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {
            "PHYSICSCOMMENT": "Some physics process",
            "PHYSICSSHORT": "HSS",
            "GENERATORNAME": "MadGraphPythia8EvtGen",
            "GENFILTEFF": "0.123",
            "CROSSSECTION": "1.234",
        }
    ]

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ), patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        dataset_name = (
            "mc16_13TeV.304823.MadGraphPythia8EvtGen_A14NNPDF23LO_"
            "HSS_LLP_mH1000_mS400_lt9m.evgen.EVNT.e5102"
        )
        md = get_metadata("mc16_13TeV", dataset_name)

        # Keys should be user-friendly names
        assert md == {
            "Physics Comment": "Some physics process",
            "Physics Short Name": "HSS",
            "Generator Name": "MadGraphPythia8EvtGen",
            "Filter Efficiency": "0.123",
            "Cross Section (nb)": "1.234",
        }


def test_get_metadata_builds_expected_command():
    """Verify the AMI command and SQL built by get_metadata are correct."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {
            "PHYSICSCOMMENT": "X",
            "PHYSICSSHORT": "Y",
            "GENERATORNAME": "Z",
            "GENFILTEFF": "0.1",
            "CROSSSECTION": "0.2",
        }
    ]

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute, patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags):
        dataset_name = "mc16_13TeV.123456.test.EVNT"
        get_metadata("mc16_13TeV", dataset_name)

        mock_execute.assert_called_once()
        actual_cmd = mock_execute.call_args[0][0]

        # Correct catalog and entity
        assert 'SearchQuery -catalog="mc15_001:production"' in actual_cmd
        assert '-entity="DATASET"' in actual_cmd

        # Extract and validate SQL
        sql_match = re.search(r'-sql="([^"]+)"', actual_cmd)
        assert sql_match, "Could not find SQL in command"
        sql = sql_match.group(1)

        # SELECT fields
        assert "SELECT" in sql
        for col in [
            "`PHYSICSCOMMENT`",
            "`PHYSICSSHORT`",
            "`GENERATORNAME`",
            "`GENFILTEFF`",
            "`CROSSSECTION`",
        ]:
            assert col in sql

        # WHERE exact dataset name equality
        assert f"`LOGICALDATASETNAME`='{dataset_name}'" in sql or (
            "`LOGICALDATASETNAME`=" in sql and dataset_name in sql
        )


def test_get_metadata_raises_on_not_found():
    """get_metadata should raise RuntimeError when zero rows are returned (not found)."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []  # zero rows

    mock_scope_tags = {"mc23": MagicMock(evgen=MagicMock(short="mc23"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ), patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags), pytest.raises(
        RuntimeError
    ) as exc:
        ds = "mc23_13p6TeV.999999.nonedataset.EVNT"
        get_metadata("mc23_13p6TeV", ds)

    msg = str(exc.value)
    assert "not found" in msg
    assert "mc23_13p6TeV" in msg
    assert "mc23_13p6TeV.999999.nonedataset.EVNT" in msg


def test_get_metadata_asserts_on_multiple_rows():
    """get_metadata should assert if AMI returns multiple rows (ambiguous)."""
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {
            "PHYSICSCOMMENT": "A",
            "PHYSICSSHORT": "B",
            "GENERATORNAME": "C",
            "GENFILTEFF": "0.1",
            "CROSSSECTION": "0.2",
        },
        {
            "PHYSICSCOMMENT": "A2",
            "PHYSICSSHORT": "B2",
            "GENERATORNAME": "C2",
            "GENFILTEFF": "0.3",
            "CROSSSECTION": "0.4",
        },
    ]

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ), patch("src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags), pytest.raises(
        AssertionError
    ) as exc:
        get_metadata("mc16_13TeV", "mc16_13TeV.123456.something.EVNT")

    assert "Expected exactly one dataset" in str(exc.value)


def test_get_provenance_returns_chain_and_builds_command():
    """Test that get_provenance builds the correct command and returns the provenance chain."""
    mock_dom_object = MagicMock(spec=DOMObject)

    # Dataset name we'll query provenance for
    ds_name = "mc23_13p6TeV.801167.Py8EG.sample.dataset"

    # Rows returned by AMI for the 'edge' view: destination -> source
    # This represents: ds_name <- parent1 <- grandparent
    rows = [
        {"source": "parent1", "destination": ds_name},
        {"source": "grandparent", "destination": "parent1"},
        {"source": "unrelated", "destination": "other"},
    ]

    # Make get_rows accept the "edge" argument used by get_provenance
    def get_rows(arg=None):
        if arg == "edge":
            return rows
        return []

    mock_dom_object.get_rows.side_effect = get_rows

    with patch(
        "src.ami_helper.ami.execute_ami_command", return_value=mock_dom_object
    ) as mock_execute:
        result = get_provenance("mc23_13p6TeV", ds_name)

        # Verify AMI command
        expected_cmd = f"GetDatasetProvenance -logicalDatasetName={ds_name}"
        mock_execute.assert_called_once_with(expected_cmd)

        # Expect the chain in order of discovery: parent then grandparent
        assert result == ["parent1", "grandparent"]
