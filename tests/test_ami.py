from unittest.mock import patch, MagicMock
from src.ami_helper.ami import find_hashtag, find_missing_tag
from src.ami_helper.ami import DOMObject  # Import DOMObject for spec
from src.ami_helper.datamodel import CentralPageHashAddress


def test_find_hashtag_tuples_returns_names():
    mock_client = MagicMock()
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {"NAME": "tag1", "SCOPE": "PMGL1"},
        {"NAME": "tag2", "SCOPE": "PMGL3"},
    ]
    mock_client.execute.return_value = mock_dom_object

    mock_scope_tags = {"scope": MagicMock(evgen=MagicMock(short="short"))}

    with patch(
        "src.ami_helper.ami.pyAMI.client.Client", return_value=mock_client
    ), patch("src.ami_helper.ami.AtlasAPI.init"), patch(
        "src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags
    ):
        result = find_hashtag("scope_extra", "fork")
        assert len(result) == 2
        assert all("scope_extra" == r.scope for r in result)
        assert result[0].hash_tags[0] == "tag1"
        assert result[1].hash_tags[2] == "tag2"


def test_find_hashtag_tuples_sql_command():
    mock_client = MagicMock()
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []
    mock_client.execute.return_value = mock_dom_object

    mock_scope_tags = {"scope": MagicMock(evgen=MagicMock(short="short"))}

    with patch(
        "src.ami_helper.ami.pyAMI.client.Client", return_value=mock_client
    ), patch("src.ami_helper.ami.AtlasAPI.init"), patch(
        "src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags
    ):
        find_hashtag("scope_extra", "fork")
        expected_cmd = (
            'SearchQuery -catalog="short_001:production" '
            '-entity="HASHTAGS" '
            "-mql=\"SELECT DISTINCT `NAME`,`SCOPE` WHERE LOWER(`NAME`) LIKE '%fork%'\""
        )
        mock_client.execute.assert_called_once_with(expected_cmd, format="dom_object")


def test_find_missing_tag_sql_command_with_two_tags():
    """Test that find_missing_tag generates correct SQL with two existing tags."""
    mock_client = MagicMock()
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []
    mock_client.execute.return_value = mock_dom_object

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    # Create an address with tags at positions 0 and 2, missing at position 1
    test_addr = CentralPageHashAddress(
        scope="mc16_13TeV", hash_tags=["tag1", None, "tag3", None]
    )

    with patch(
        "src.ami_helper.ami.pyAMI.client.Client", return_value=mock_client
    ), patch("src.ami_helper.ami.AtlasAPI.init"), patch(
        "src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags
    ):
        find_missing_tag(test_addr, missing_index=1)

        # Verify the SQL command structure
        mock_client.execute.assert_called_once()
        actual_cmd = mock_client.execute.call_args[0][0]

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
    mock_client = MagicMock()
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []
    mock_client.execute.return_value = mock_dom_object

    mock_scope_tags = {"mc23": MagicMock(evgen=MagicMock(short="mc23"))}

    # Create an address with only one tag at position 0, missing at position 3
    test_addr = CentralPageHashAddress(
        scope="mc23_13TeV", hash_tags=["onlytag", None, None, None]
    )

    with patch(
        "src.ami_helper.ami.pyAMI.client.Client", return_value=mock_client
    ), patch("src.ami_helper.ami.AtlasAPI.init"), patch(
        "src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags
    ):
        find_missing_tag(test_addr, missing_index=3)

        # Verify the SQL command structure
        mock_client.execute.assert_called_once()
        actual_cmd = mock_client.execute.call_args[0][0]

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
    mock_client = MagicMock()
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = []
    mock_client.execute.return_value = mock_dom_object

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    # Create address with tags at positions 0, 1, and 3; missing at position 2
    test_addr = CentralPageHashAddress(
        scope="mc16_13TeV", hash_tags=["tag1", "tag2", None, "tag4"]
    )

    with patch(
        "src.ami_helper.ami.pyAMI.client.Client", return_value=mock_client
    ), patch("src.ami_helper.ami.AtlasAPI.init"), patch(
        "src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags
    ):
        find_missing_tag(test_addr, missing_index=2)

        mock_client.execute.assert_called_once()
        actual_cmd = mock_client.execute.call_args[0][0]

        # Extract the SQL from the command
        import re

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
    mock_client = MagicMock()
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {"NAME": "newtag1", "SCOPE": "PMGL2"},
        {"NAME": "newtag2", "SCOPE": "PMGL2"},
    ]
    mock_client.execute.return_value = mock_dom_object

    mock_scope_tags = {"mc16": MagicMock(evgen=MagicMock(short="mc15"))}

    test_addr = CentralPageHashAddress(
        scope="mc16_13TeV", hash_tags=["tag1", None, None, None]
    )

    with patch(
        "src.ami_helper.ami.pyAMI.client.Client", return_value=mock_client
    ), patch("src.ami_helper.ami.AtlasAPI.init"), patch(
        "src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags
    ):
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
