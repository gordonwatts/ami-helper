import pyAMI.client
import pyAMI_atlas.api as AtlasAPI
from pyAMI.object import DOMObject
from .datamodel import SCOPE_TAGS


def find_hashtag_tuples(scope: str) -> list[str]:
    """
    Given a scope, query AMI and return a list of hashtag names for that scope.
    """
    ami = pyAMI.client.Client("atlas-replica")
    AtlasAPI.init()

    # Parse the scope and look up evgen short tag from data model
    scope_short = scope.split("_")[0]
    evgen_short = SCOPE_TAGS[scope_short].evgen.short

    cmd = (
        f'SearchQuery -catalog="{evgen_short}_001:production" '
        '-entity="HASHTAGS" '
        f'-mql="SELECT DISTINCT `NAME` '
        f"WHERE `SCOPE` = 'PMGL1'\""
    )
    result = ami.execute(cmd, format="dom_object")
    assert isinstance(result, DOMObject)

    rows = result.get_rows()
    return [row["NAME"] for row in rows]
