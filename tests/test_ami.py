from unittest.mock import patch, MagicMock
from src.ami_helper.ami import find_hashtag
from src.ami_helper.ami import DOMObject  # Import DOMObject for spec


def test_find_hashtag_tuples_returns_names():
    mock_client = MagicMock()
    mock_dom_object = MagicMock(spec=DOMObject)
    mock_dom_object.get_rows.return_value = [
        {"NAME": "tag1", "SCOPE": "s1"},
        {"NAME": "tag2", "SCOPE": "s2"},
    ]
    mock_client.execute.return_value = mock_dom_object

    mock_scope_tags = {"scope": MagicMock(evgen=MagicMock(short="short"))}

    with patch(
        "src.ami_helper.ami.pyAMI.client.Client", return_value=mock_client
    ), patch("src.ami_helper.ami.AtlasAPI.init"), patch(
        "src.ami_helper.ami.SCOPE_TAGS", mock_scope_tags
    ):
        result = find_hashtag("scope_extra", "fork")
        assert result == [("tag1", "s1"), ("tag2", "s2")]


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
