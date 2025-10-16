from ast import Tuple
import pyAMI.client
import pyAMI_atlas.api as AtlasAPI
from pyAMI.object import DOMObject
from pypika import Field, Query, Table
from pypika.functions import Lower
from typing import List, Tuple

from ami_helper.datamodel import (
    SCOPE_TAGS,
    CentralPageHashAddress,
    make_central_page_hash_address,
)


def find_hashtag(scope: str, search_string: str) -> List[CentralPageHashAddress]:
    """
    Given a scope, query AMI and return a list of hashtag names for that scope.
    """
    ami = pyAMI.client.Client("atlas-replica")
    AtlasAPI.init()

    # Query
    hashtags = Table("tbl")
    q = (
        Query.from_(hashtags)
        .select(hashtags.NAME, hashtags.SCOPE)
        .distinct()
        .where(Lower(hashtags.NAME).like(f"%{search_string.lower()}%"))
    )
    query_text = str(q).replace('"', "`").replace(" FROM `tbl`", "")

    # Parse the scope and look up evgen short tag from data model
    scope_short = scope.split("_")[0]
    evgen_short = SCOPE_TAGS[scope_short].evgen.short

    cmd = (
        f'SearchQuery -catalog="{evgen_short}_001:production" '
        '-entity="HASHTAGS" '
        f'-mql="{query_text}"'
    )
    result = ami.execute(cmd, format="dom_object")
    assert isinstance(result, DOMObject)

    rows = result.get_rows()
    return [
        make_central_page_hash_address(scope, row["SCOPE"], row["NAME"]) for row in rows
    ]
