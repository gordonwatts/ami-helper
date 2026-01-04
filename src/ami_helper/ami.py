import logging
from typing import Dict, List, Optional, Tuple
import pyAMI.client
from pyAMI.object import DOMObject
from pypika import MSSQLQuery, Table
from pypika.functions import Lower

from ami_helper.datamodel import (
    SCOPE_TAGS,
    CentralPageHashAddress,
    add_hash_to_addr,
    make_central_page_hash_address,
)
from ami_helper.disk_cache import diskcache_decorator

logger = logging.getLogger(__name__)


@diskcache_decorator()
def execute_ami_command(
    cmd: str, rowset_type: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Execute an AMI command with caching.

    Parameters
    ----------
    cmd : str
        The AMI command string to execute.

    Returns
    List[Dict[str, str]]
        The AMI result as a list of dictionaries.
    """
    # Execute the command
    import pyAMI_atlas.api as AtlasAPI  # type: ignore

    ami = pyAMI.client.Client("atlas-replica")
    AtlasAPI.init()
    result = ami.execute(cmd, format="dom_object")
    assert isinstance(result, DOMObject)

    # Only return the rows without all the complex information.
    returned_rows = result.get_rows(rowset_type=rowset_type)
    rows = [{str(k): str(v) for k, v in r.items()} for r in returned_rows]

    return rows


def find_hashtag(
    scope: str, search_string: str, ignore_cache: bool = False
) -> List[CentralPageHashAddress]:
    """
    Query AMI for hashtags whose NAME contains `search_string` (case-insensitive)
    and return a list of CentralPageHashAddress entries for the provided scope.

    Parameters
    ----------
    scope : str
        Scope string used to determine the evgen short tag (e.g. "mc15_13TeV").
    search_string : str
        Substring to search for in hashtag names (case-insensitive).
    ignore_cache : bool
        Bypass the on-disk cache for AMI calls.

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

    rows = execute_ami_command(cmd, ignore_cache=ignore_cache)  # type: ignore
    logger.info(f"Found {len(rows)} hashtags matching '{search_string}'")
    return [
        make_central_page_hash_address(scope, row["SCOPE"], row["NAME"]) for row in rows
    ]


def find_missing_tag(
    s_addr: CentralPageHashAddress, missing_index: int, ignore_cache: bool = False
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
    ignore_cache : bool
        Bypass the on-disk cache for AMI calls.

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
        .where(dataset.AMISTATUS == "VALID")
    )

    # Add subquery conditions for each hashtag in hash combinations
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

    rows = execute_ami_command(cmd, ignore_cache=ignore_cache)  # type: ignore
    return [
        add_hash_to_addr(s_addr, row["HASHTAGS.SCOPE"], row["HASHTAGS.NAME"])
        for row in rows
    ]


def find_hashtag_tuples(
    s_addr: CentralPageHashAddress, ignore_cache: bool = False
) -> List[CentralPageHashAddress]:
    """
    Produce all fully-populated CentralPageHashAddress combinations reachable from
    the provided partial address by filling missing hashtag slots. It does this by making
    queries to AMI.

    Parameters
    ----------
    s_addr:
        A CentralPageHashAddress that may contain empty/None entries in its
        hash_tags list. These represent missing tags to be discovered.
    ignore_cache : bool
        Bypass the on-disk cache for AMI calls.

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
        possible_tags = find_missing_tag(
            current_addr, missing_index[0], ignore_cache=ignore_cache
        )
        logger.info(
            f"Found {len(possible_tags)} hashtags for tags "
            f"{', '.join([h for h in current_addr.hash_tags if h is not None])}"
        )
        stack.extend(possible_tags)
    return results


def find_dids_with_hashtags(
    s_addr: CentralPageHashAddress, ignore_cache: bool = False
) -> List[str]:
    """
    Find dataset IDs matching all hashtags in the provided CentralPageHashAddress.

    Parameters
    ----------
    s_addr : CentralPageHashAddress
        Address containing the hashtag tuple to search for.
    ignore_cache : bool
        Bypass the on-disk cache for AMI calls.
    """

    hash_scope_list = ",".join(f"PMGL{i+1}" for i in range(len(s_addr.hash_tags)))
    name_list = ",".join(s_addr.hash_tags)  # type: ignore

    cmd = (
        f'DatasetWBListDatasetsForHashtag -scope="{hash_scope_list}" -name="{name_list}"'
        ' -operator="AND"'
    )

    rows = execute_ami_command(cmd, ignore_cache=ignore_cache)  # type: ignore
    ldns = [str(res["ldn"]) for res in rows if s_addr.scope in str(res["ldn"])]

    return ldns


def find_dids_with_name(
    scope: str, name: str, require_pmg: bool = True, ignore_cache: bool = False
) -> List[Tuple[str, CentralPageHashAddress]]:
    """
    Search AMI for a dataset with the given name, EVNT type.

    :param scope: What scope should be looking for?
    :type scope: str
    :param name: The name the dataset should contain
    :type name: str
    :param require_pmg: Demand 4 PMG hash tags (usually only PMG datasets have hashtags)
    :type require_pmg: bool
    :param ignore_cache: Bypass the on-disk cache for AMI calls.
    :type ignore_cache: bool
    :return: List of tuples of (dataset logical name, CentralPageHashAddress)
    :rtype: List[Tuple[str, CentralPageHashAddress]]
    """

    # Build the query for an AMI dataset
    dataset = Table("DATASET")
    h1 = Table("HASHTAGS").as_("h1")
    h2 = Table("HASHTAGS").as_("h2")
    h3 = Table("HASHTAGS").as_("h3")
    h4 = Table("HASHTAGS").as_("h4")

    q = MSSQLQuery.from_(dataset)
    if require_pmg:
        q = (
            q.join(h1)
            .on((dataset.IDENTIFIER == h1.DATASETFK) & (h1.SCOPE == "PMGL1"))
            .join(h2)
            .on((dataset.IDENTIFIER == h2.DATASETFK) & (h2.SCOPE == "PMGL2"))
            .join(h3)
            .on((dataset.IDENTIFIER == h3.DATASETFK) & (h3.SCOPE == "PMGL3"))
            .join(h4)
            .on((dataset.IDENTIFIER == h4.DATASETFK) & (h4.SCOPE == "PMGL4"))
        )
    else:
        q = (
            q.left_join(h1)
            .on((dataset.IDENTIFIER == h1.DATASETFK) & (h1.SCOPE == "PMGL1"))
            .left_join(h2)
            .on((dataset.IDENTIFIER == h2.DATASETFK) & (h2.SCOPE == "PMGL2"))
            .left_join(h3)
            .on((dataset.IDENTIFIER == h3.DATASETFK) & (h3.SCOPE == "PMGL3"))
            .left_join(h4)
            .on((dataset.IDENTIFIER == h4.DATASETFK) & (h4.SCOPE == "PMGL4"))
        )

    results_limit = 500
    q = (
        q.select(
            dataset.LOGICALDATASETNAME,
            h1.NAME.as_("PMGL1"),
            h2.NAME.as_("PMGL2"),
            h3.NAME.as_("PMGL3"),
            h4.NAME.as_("PMGL4"),
        )
        .distinct()
        .where(dataset.LOGICALDATASETNAME.like(f"%{name}%"))
        .where(dataset.DATATYPE == "EVNT")
        .where(dataset.AMISTATUS == "VALID")
        .limit(results_limit)  # keep your limit if desired
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

    rows = execute_ami_command(cmd, ignore_cache=ignore_cache)  # type: ignore
    if len(rows) == results_limit:
        logger.warning(
            f"Query for datasets with name '{name}' returned {results_limit} results - "
            "there may be more matching datasets not retrieved. "
            "Consider refining your search."
        )

    def _get_alias_value(row, i: int) -> str:
        return row[f"h{i}.NAME PMGL{i}"]

    results: List[Tuple[str, CentralPageHashAddress]] = []
    for row in rows:
        ldn: str = row["LOGICALDATASETNAME"]  # type: ignore
        # Build tags tuple with explicit Optional type to satisfy typing
        tags: Tuple[Optional[str], ...] = (
            _get_alias_value(row, 1),
            _get_alias_value(row, 2),
            _get_alias_value(row, 3),
            _get_alias_value(row, 4),
        )
        addr = CentralPageHashAddress(scope=scope, hash_tags=tags)
        results.append((ldn, addr))

    return results


def get_short_scope(scope: str) -> str:
    s_name = scope.split("_")[0]
    scope_info = SCOPE_TAGS.get(s_name, None)
    if scope_info is None:
        return s_name
    return scope_info.evgen.short


def get_metadata(scope: str, name: str, ignore_cache: bool = False) -> Dict[str, str]:
    """
    Get metadata for a dataset with the given name.

    :param scope: What scope should be looking for?
    :type scope: str
    :param name: The exact name of the dataset
    :type name: str
    :param ignore_cache: Bypass the on-disk cache for AMI calls.
    :type ignore_cache: bool
    :return: Dictionary of metadata key-value pairs
    :rtype: Dict[str, str]
    """

    dataset = Table("DATASET")
    q = MSSQLQuery.from_(dataset)
    q = (
        q.select(
            dataset.PHYSICSCOMMENT,
            dataset.PHYSICSSHORT,
            dataset.GENERATORNAME,
            dataset.GENFILTEFF,
            dataset.CROSSSECTION,
        )
        .where(dataset.LOGICALDATASETNAME == name)
        .where(dataset.AMISTATUS == "VALID")
    )

    evgen_short = get_short_scope(scope)
    query_text = str(q).replace('"', "`")
    cmd = (
        f'SearchQuery -catalog="{evgen_short}_001:production" '
        '-entity="DATASET" '
        f'-sql="{query_text}"'
    )

    rows = execute_ami_command(cmd, ignore_cache=ignore_cache)  # type: ignore
    if len(rows) == 0:
        # Dataset not found at the given scope/name
        raise RuntimeError(f"Dataset '{name}' not found in scope '{scope}'")
    assert (
        len(rows) == 1
    ), f"Expected exactly one dataset for name '{name}', found {len(rows)}"

    name_map = {
        "PHYSICSCOMMENT": "Physics Comment",
        "PHYSICSSHORT": "Physics Short Name",
        "GENERATORNAME": "Generator Name",
        "GENFILTEFF": "Filter Efficiency",
        "CROSSSECTION": "Cross Section (nb)",
    }

    metadata = {name_map.get(k, k): v for k, v in rows[0].items()}

    return metadata  # type: ignore


def get_provenance(scope: str, ds_name: str, ignore_cache: bool = False) -> List[str]:
    """
    Get the provenance dataset logical names for a given dataset.

    :param scope: What scope should be looking for?
    :type scope: str
    :param ds_name: The exact name of the dataset
    :type ds_name: str
    :param ignore_cache: Bypass the on-disk cache for AMI calls.
    :type ignore_cache: bool
    :return: List of provenance dataset logical names
    :rtype: List[str]
    """

    cmd = f"GetDatasetProvenance -logicalDatasetName={ds_name}"
    rows = execute_ami_command(cmd, "edge", ignore_cache=ignore_cache)  # type: ignore

    def find_backone(name: str) -> Optional[str]:
        for r in rows:
            if r["destination"] == name:
                return r["source"]

    result_names = []
    backone = ds_name
    while True:
        backone = find_backone(backone)
        if backone is None:
            break
        result_names.append(backone)
        ds_name = backone

    return result_names


def get_by_datatype(scope, run_number: int, datatype, ignore_cache: bool = False):
    """
    Get dataset logical names for a run number and datatype.

    :param scope: What scope should be looking for?
    :type scope: str
    :param run_number: Run number of the dataset to look up.
    :type run_number: int
    :param datatype: Exact match of data type (DAOD_PHYSLITE, AOD, etc.)
    :type datatype: str
    :param ignore_cache: Bypass the on-disk cache for AMI calls.
    :type ignore_cache: bool
    """
    dataset = Table("DATASET")
    q = MSSQLQuery.from_(dataset)
    q = (
        q.select(
            dataset.LOGICALDATASETNAME,
        )
        .where(dataset.AMISTATUS == "VALID")
        .where(dataset.DATASETNUMBER == str(run_number))
        .where(dataset.DATATYPE == datatype)
        .distinct()
    )

    evgen_short = get_short_scope(scope)
    query_text = str(q).replace('"', "`")
    cmd = (
        f'SearchQuery -catalog="{evgen_short}_001:production" '
        '-entity="DATASET" '
        f'-sql="{query_text}"'
    )

    rows = execute_ami_command(cmd, ignore_cache=ignore_cache)  # type: ignore

    return [r["LOGICALDATASETNAME"] for r in rows]
