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
    add_hash_to_addr,
)


def find_hashtag(scope: str, search_string: str) -> List[CentralPageHashAddress]:
    """
    Query AMI for hashtags whose NAME contains `search_string` (case-insensitive)
    and return a list of CentralPageHashAddress entries for the provided scope.

    Parameters
    ----------
    scope : str
        Scope string used to determine the evgen short tag (e.g. "mc15_13TeV").
    search_string : str
        Substring to search for in hashtag names (case-insensitive).

    Returns
    -------
    List[CentralPageHashAddress]
        A list of CentralPageHashAddress objects constructed from AMI results.

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


def find_missing_tag(
    s_addr: CentralPageHashAddress, missing_index: int
) -> List[CentralPageHashAddress]:
    # Build subqueries for each hashtag using pypika
    dataset = Table("DATASET")
    hashtags_result = Table("HASHTAGS")

    # Start building the WHERE clause
    q = (
        Query.from_(dataset)
        .select(hashtags_result.SCOPE, hashtags_result.NAME)
        .distinct()
        .join(hashtags_result)
        .on(dataset.IDENTIFIER == hashtags_result.DATASETFK)
        .where(hashtags_result.SCOPE == f"PMGL{missing_index + 1}")
    )

    # Add subquery conditions for each hashtag in hashcomb
    for n, hashtag in enumerate(s_addr.hash_tags):
        if hashtag is not None:
            hashtags_alias = Table("HASHTAGS").as_(f"h{n+1}")
            subquery = (
                Query.from_(hashtags_alias)
                .select(hashtags_alias.DATASETFK)
                .where(hashtags_alias.SCOPE == f"PMGL{n+1}")
                .where(hashtags_alias.NAME == hashtag)
            )
            q = q.where(dataset.IDENTIFIER.isin(subquery))

    # Convert to string and format for AMI
    query_text = str(q).replace('"', "`")

    scope = s_addr.scope
    scope_short = scope.split("_")[0]
    evgen_short = SCOPE_TAGS[scope_short].evgen.short

    cmd = (
        f'SearchQuery -catalog="{evgen_short}_001:production" '
        '-entity="DATASET" '
        f'-sql="{query_text}"'
    )

    ami = pyAMI.client.Client("atlas-replica")
    AtlasAPI.init()
    result = ami.execute(cmd, format="dom_object")
    assert isinstance(result, DOMObject)

    rows = result.get_rows()
    return [add_hash_to_addr(s_addr, row["SCOPE"], row["NAME"]) for row in rows]


# def fill_in_missing_tags(
#     s_addr: CentralPageHashAddress,
# ) -> List[CentralPageHashAddress]:
#     """
#     Given a CentralPageHashAddress with some empty tags, return a list of
#     CentralPageHashAddress with all combinations of the missing tags filled in.
#     """
#     scope = s_addr.scope

#     # Find which tags are missing
#     missing_indices = [i for i, tag in enumerate(s_addr.hash_tags) if not tag]

#     if not missing_indices:
#         return [s_addr]

#     # First

#     # # For each missing index, query AMI to find possible tags
#     # possible_tags: List[List[str]] = []
#     # for idx in missing_indices:
#     #     hash_scope = list(make_central_page_hash_address._hash_scope_index.keys())[idx]
#     #     tags = find_hashtag(s_addr.scope, "")
#     #     tags_for_scope = [tag.hash_tags[idx] for tag in tags if tag.hash_tags[idx]]
#     #     possible_tags.append(tags_for_scope)

#     # # Generate all combinations of the possible tags
#     # from itertools import product

#     # all_combinations = product(*possible_tags)

#     # filled_addresses = []
#     # for combination in all_combinations:
#     #     new_tags = s_addr.hash_tags[:]
#     #     for idx, tag in zip(missing_indices, combination):
#     #         new_tags[idx] = tag
#     #     filled_addresses.append(
#     #         CentralPageHashAddress(scope=s_addr.scope, hash_tags=new_tags)
#     #     )

#     # return filled_addresses
#     return []
