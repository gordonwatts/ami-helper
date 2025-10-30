import logging
from pathlib import Path
from typing import List, Optional, Tuple

import diskcache
import pyAMI.client
import pyAMI_atlas.api as AtlasAPI
from pyAMI.object import DOMObject
from pypika import Field, Table, MSSQLQuery
from pypika.functions import Lower

from ami_helper.datamodel import (
    SCOPE_TAGS,
    CentralPageHashAddress,
    add_hash_to_addr,
    make_central_page_hash_address,
)

logger = logging.getLogger(__name__)

# Global cache instance - can be overridden for testing
_cache: Optional[diskcache.Cache] = None


def get_cache() -> diskcache.Cache:
    """Get or create the AMI query cache."""
    global _cache
    if _cache is None:
        cache_dir = Path.home() / ".cache" / "ami-helper"
        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache = diskcache.Cache(str(cache_dir))
        logger.debug(f"Initialized cache at {cache_dir}")
    return _cache


def set_cache(cache: Optional[diskcache.Cache]) -> None:
    """Set the cache instance (useful for testing)."""
    global _cache
    _cache = cache


def execute_ami_command(cmd: str) -> DOMObject:
    """
    Execute an AMI command with caching.

    Parameters
    ----------
    cmd : str
        The AMI command string to execute.

    Returns
    -------
    DOMObject
        The AMI result as a DOMObject.
    """
    cache = get_cache()

    # Check cache first
    cached_result = cache.get(cmd)
    if cached_result is not None:
        logger.debug(f"Cache hit for command: {cmd}")
        return cached_result  # type: ignore

    logger.debug(f"Cache miss, executing AMI command: {cmd}")

    # Execute the command
    ami = pyAMI.client.Client("atlas-replica")
    AtlasAPI.init()
    result = ami.execute(cmd, format="dom_object")
    assert isinstance(result, DOMObject)

    # Cache the result
    cache.set(cmd, result)

    return result


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

    # Query
    hashtags = Table("tbl")
    q = (
        MSSQLQuery.from_(hashtags)
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

    result = execute_ami_command(cmd)
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
        MSSQLQuery.from_(dataset)
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
                MSSQLQuery.from_(hashtags_alias)
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

    result = execute_ami_command(cmd)
    rows = result.get_rows()
    return [
        add_hash_to_addr(s_addr, row["HASHTAGS.SCOPE"], row["HASHTAGS.NAME"])
        for row in rows
    ]


def find_hashtag_tuples(s_addr: CentralPageHashAddress) -> List[CentralPageHashAddress]:
    """
    Produce all fully-populated CentralPageHashAddress combinations reachable from
    the provided partial address by filling missing hashtag slots. It does this by making
    queires to AMI.

    Parameters
    ----------
    s_addr:
        A CentralPageHashAddress that may contain empty/None entries in its
        hash_tags list. These represent missing tags to be discovered.

    Returns
    -------
    List[CentralPageHashAddress]
        A list of CentralPageHashAddress instances with no missing hashtag
        entries (each represents one complete combination discovered).
    """
    results: List[CentralPageHashAddress] = []
    stack = [s_addr]

    while len(stack) > 0:
        current_addr = stack.pop()
        missing_index = [i for i, t in enumerate(current_addr.hash_tags) if not t]
        if len(missing_index) == 0:
            results.append(current_addr)
            continue

        # Find possible tags for the missing index
        possible_tags = find_missing_tag(current_addr, missing_index[0])
        logger.info(
            f"Found {len(possible_tags)} hashtags for tags {', '.join([h for h in current_addr.hash_tags if h is not None])}"
        )
        stack.extend(possible_tags)
    return results


def find_dids_with_hashtags(s_addr: CentralPageHashAddress) -> List[str]:
    "Find dataset IDs matching all hashtags in the provided CentralPageHashAddress."

    hash_scope_list = ",".join(f"PMGL{i+1}" for i in range(len(s_addr.hash_tags)))
    name_list = ",".join(s_addr.hash_tags)  # type: ignore

    cmd = f'DatasetWBListDatasetsForHashtag -scope="{hash_scope_list}" -name="{name_list}" -operator="AND"'

    result = execute_ami_command(cmd)
    ldns = [
        str(res["ldn"]) for res in result.get_rows() if s_addr.scope in str(res["ldn"])
    ]

    return ldns


def find_dids_with_name(
    scope: str, name: str
) -> List[Tuple[str, CentralPageHashAddress]]:
    """
    Search AMI for a dataset with the given name, EVNT type.

    :param scope: What scope shoudl be looking for?
    :type scope: str
    :param name: The name the dataset should contain
    :type name: str
    :return: List of tuples of (dataset logical name, CentralPageHashAddress)
    :rtype: List[Tuple[str, CentralPageHashAddress]]
    """

    # Build the query for an AMI dataset
    dataset = Table("DATASET")
    h1 = Table("HASHTAGS").as_("h1")
    h2 = Table("HASHTAGS").as_("h2")
    h3 = Table("HASHTAGS").as_("h3")
    h4 = Table("HASHTAGS").as_("h4")

    # Build the search for the proper datatypes
    # q = (
    #     MSSQLQuery.from_(dataset)
    #     .select(dataset.LOGICALDATASETNAME)
    #     .where(dataset.LOGICALDATASETNAME.like(f"%{name}%"))
    #     .where(dataset.DATATYPE == "EVNT")
    #     # TODO: Fix this limit (see #10).
    #     .limit(100)
    # )

    # # Next, make sure these have PMG tags
    # subquery = (
    #     MSSQLQuery.from_(hashtags_result)
    #     .select(hashtags_result.DATASETFK)
    #     .where(hashtags_result.SCOPE == "PMGL1")
    # )
    # q = q.where(dataset.IDENTIFIER.isin(subquery))

    q = (
        MSSQLQuery.from_(dataset)
        .left_join(h1)
        .on((dataset.IDENTIFIER == h1.DATASETFK) & (h1.SCOPE == "PMGL1"))
        .left_join(h2)
        .on((dataset.IDENTIFIER == h2.DATASETFK) & (h2.SCOPE == "PMGL2"))
        .left_join(h3)
        .on((dataset.IDENTIFIER == h3.DATASETFK) & (h3.SCOPE == "PMGL3"))
        .left_join(h4)
        .on((dataset.IDENTIFIER == h4.DATASETFK) & (h4.SCOPE == "PMGL4"))
        .select(
            dataset.LOGICALDATASETNAME,
            h1.NAME.as_("PMGL1"),
            h2.NAME.as_("PMGL2"),
            h3.NAME.as_("PMGL3"),
            h4.NAME.as_("PMGL4"),
        )
        .where(dataset.LOGICALDATASETNAME.like(f"%{name}%"))
        .where(dataset.DATATYPE == "EVNT")
        .limit(100)  # keep your limit if desired
    )

    # Convert to string and format for AMI
    query_text = str(q).replace('"', "`")

    # Get the scope sorted out
    scope_short = scope.split("_")[0]
    evgen_short = SCOPE_TAGS[scope_short].evgen.short

    cmd = (
        f'SearchQuery -catalog="{evgen_short}_001:production" '
        '-entity="DATASET" '
        f'-sql="{query_text}"'
    )

    result = execute_ami_command(cmd)
    rows = result.get_rows()

    def _get_alias_value(row, i: int) -> str:
        return row[f"h{i}.NAME PMGL{i}"]

    results: List[Tuple[str, CentralPageHashAddress]] = []
    for row in rows:
        ldn: str = row["LOGICALDATASETNAME"]  # type: ignore
        # Build tags list with explicit Optional type to satisfy typing
        tags: List[Optional[str]] = [
            _get_alias_value(row, 1),
            _get_alias_value(row, 2),
            _get_alias_value(row, 3),
            _get_alias_value(row, 4),
        ]
        addr = CentralPageHashAddress(scope=scope, hash_tags=tags)
        results.append((ldn, addr))

    return results
