import logging
from ast import Tuple
from typing import List, Tuple

import pyAMI.client
import pyAMI_atlas.api as AtlasAPI
from pyAMI.object import DOMObject
from pypika import Field, Query, Table
from pypika.functions import Lower

from ami_helper.datamodel import (
    SCOPE_TAGS,
    CentralPageHashAddress,
    add_hash_to_addr,
    make_central_page_hash_address,
)

logger = logging.getLogger(__name__)


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
    logger.info(
        f"Searching for hashtags containing '{search_string}' in scope '{scope}'"
    )
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
    logger.debug(f"Executing AMI command: {cmd}")
    result = ami.execute(cmd, format="dom_object")
    assert isinstance(result, DOMObject)

    rows = result.get_rows()
    logger.info(f"Found {len(rows)} hashtags matching '{search_string}'")
    return [
        make_central_page_hash_address(scope, row["SCOPE"], row["NAME"]) for row in rows
    ]


def find_missing_tag(
    s_addr: CentralPageHashAddress, missing_index: int
) -> List[CentralPageHashAddress]:
    """
    Query AMI to find candidate hashtag values for a single missing tag position.

    This function constructs an AMI SQL query that selects datasets which have a
    hashtag defined at the target PMGL scope corresponding to `missing_index`
    and that also satisfy any other non-empty hashtag constraints already
    present in `s_addr`. It returns one CentralPageHashAddress per matching
    hashtag found, with the missing tag filled in.

    Parameters
    ----------
    s_addr : CentralPageHashAddress
        A partially-filled address whose `hash_tags` list may contain empty
        entries. Other non-empty entries are used as constraints in the query.
    missing_index : int
        Zero-based index of the hashtag position to fill. This maps to an AMI
        hashtag scope named "PMGL{missing_index + 1}".

    Returns
    -------
    List[CentralPageHashAddress]
        A list of CentralPageHashAddress objects derived from the AMI results,
        each with the tag at `missing_index` set to a value found in AMI.
    """
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
    logger.debug(f"Executing AMI command: {cmd}")

    ami = pyAMI.client.Client("atlas-replica")
    AtlasAPI.init()
    result = ami.execute(cmd, format="dom_object")
    assert isinstance(result, DOMObject)

    rows = result.get_rows()
    return [
        add_hash_to_addr(s_addr, row["HASHTAGS.SCOPE"], row["HASHTAGS.NAME"])
        for row in rows
    ]


def find_hashtag_tuples(s_addr: CentralPageHashAddress) -> List[CentralPageHashAddress]:
    results = []
    stack = [s_addr]

    while len(stack) > 0:
        current_addr = stack.pop()
        missing_index = [i for i, t in enumerate(current_addr.hash_tags) if not t]
        if len(missing_index) == 0:
            results.append(current_addr)
            continue

        # Find possible tags for the missing index
        possible_tags = find_missing_tag(current_addr, missing_index[0])
        logging.info(
            f"Found {len(possible_tags)} hashtags for tags {', '.join([h for h in current_addr.hash_tags if h is not None])}"
        )
        stack.extend(possible_tags)

    return results
