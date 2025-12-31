from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple


@dataclass(frozen=True)
class EvgenInfo:
    short: str


@dataclass(frozen=True)
class SimInfo:
    short: str
    # Full simulation tags
    FS: List[str] = field(default_factory=list)
    # Alternative fast simulation tags; keys like "AF2", "AF3" map to a list of tags
    AF: Mapping[str, List[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoInfo:
    short: str
    # Campaign name -> list of r-tags
    campaigns: Mapping[str, List[str]]


@dataclass(frozen=True)
class ScopeTags:
    evgen: EvgenInfo
    sim: SimInfo
    reco: RecoInfo


# Typed mapping of scope short name -> ScopeTags
SCOPE_TAGS: Dict[str, ScopeTags] = {
    "mc16": ScopeTags(
        evgen=EvgenInfo(short="mc15"),
        sim=SimInfo(short="mc16", FS=["s3126"], AF={"AF2": ["a875"]}),
        reco=RecoInfo(
            short="mc16",
            campaigns={"mc16a": ["r9364"], "mc16d": ["r10201"], "mc16e": ["r10724"]},
        ),
    ),
    "mc20": ScopeTags(
        evgen=EvgenInfo(short="mc15"),
        sim=SimInfo(
            short="mc16",
            FS=["s3681", "s4231", "s3797"],
            AF={"AF2": ["a907"]},
        ),
        reco=RecoInfo(
            short="mc20",
            campaigns={
                "mc20a": ["r13167", "r14859"],
                "mc20d": ["r13144", "r14860"],
                "mc20e": ["r13145", "r14861"],
            },
        ),
    ),
    "mc23": ScopeTags(
        evgen=EvgenInfo(short="mc23"),
        sim=SimInfo(
            short="mc23",
            FS=["s4162", "s4159", "s4369"],
            AF={"AF3": ["a910", "a911", "a934"]},
        ),
        reco=RecoInfo(
            short="mc23",
            campaigns={
                "mc23a": ["r15540", "r14622"],
                "mc23d": ["r15530", "r15224"],
                "mc23e": ["r16083"],
            },
        ),
    ),
}


# Backwards-compatibility alias, if any external code expects the old name.
# Note: structure is different (dataclasses), so attribute access will differ.
scopetag_dict = SCOPE_TAGS


@dataclass(frozen=True)
class CentralPageHashAddress:
    """
    Hash tag address paired with a scope - gives a "unique" set of
    data samples when queried against ami.
    """

    scope: str
    hash_tags: Tuple[Optional[str], ...]

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the CentralPageHashAddress to a dictionary for JSON serialization.

        :return: Dictionary with 'scope' and 'hash_tags' keys
        :rtype: Dict[str, Any]
        """
        return {"scope": self.scope, "hash_tags": list(self.hash_tags)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CentralPageHashAddress":
        """
        Create a CentralPageHashAddress from a dictionary (e.g., from JSON).

        :param data: Dictionary with 'scope' and 'hash_tags' keys
        :type data: Dict[str, Any]
        :return: A new CentralPageHashAddress instance
        :rtype: CentralPageHashAddress
        """
        return cls(scope=data["scope"], hash_tags=tuple(data["hash_tags"]))


_hash_scope_index = {
    "PMGL1": 0,
    "PMGL2": 1,
    "PMGL3": 2,
    "PMGL4": 3,
}


def make_central_page_hash_address(
    scope: str, hash_scope: str, hash_value: str
) -> CentralPageHashAddress:
    index = _hash_scope_index.get(hash_scope, None)
    if index is None:
        raise ValueError(
            f"Unknown hash scope: {hash_scope} (legal ones: {_hash_scope_index.keys()})"
        )
    hash_values: List[Optional[str]] = [None] * 4
    hash_values[index] = hash_value
    return CentralPageHashAddress(scope=scope, hash_tags=tuple(hash_values))


def add_hash_to_addr(
    addr: CentralPageHashAddress, hash_scope: str, hash_value: str
) -> CentralPageHashAddress:
    index = _hash_scope_index.get(hash_scope, None)
    if index is None:
        raise ValueError(
            f"Unknown hash scope: {hash_scope} (legal ones: {_hash_scope_index.keys()})"
        )
    hash_values = list(addr.hash_tags)  # Convert tuple to list for mutation
    hash_values[index] = hash_value
    return CentralPageHashAddress(scope=addr.scope, hash_tags=tuple(hash_values))


def get_tag_combinations(scope_short: str) -> Dict[str, List[str]]:
    """
    Find all tag combinations for reco for full sim and fast sim.

    :param scope_short: The short scope of what we are looking at
    :type scope_short: str
    :return: List of tag combinations
    :rtype: Dict[str, List[str]]
    """
    tagcombs = {}

    # get combinations for full sim
    for stag in SCOPE_TAGS[scope_short].sim.FS:
        for camp in SCOPE_TAGS[scope_short].reco.campaigns:
            for rtag in SCOPE_TAGS[scope_short].reco.campaigns[camp]:
                if f"{camp} - FS" not in tagcombs:
                    tagcombs[f"{camp} - FS"] = [f"_{stag}_{rtag}"]
                else:
                    tagcombs[f"{camp} - FS"].append(f"_{stag}_{rtag}")

    # get combinations for fast sim
    asimtype = [x for x in SCOPE_TAGS[scope_short].sim.AF.keys() if "AF" in x][0]
    for atag in SCOPE_TAGS[scope_short].sim.AF[asimtype]:
        for camp, rtags in SCOPE_TAGS[scope_short].reco.campaigns.items():
            for rtag in rtags:
                if f"{camp} - {asimtype}" not in tagcombs:
                    tagcombs[f"{camp} - {asimtype}"] = [f"_{atag}_{rtag}"]
                else:
                    tagcombs[f"{camp} - {asimtype}"].append(f"_{atag}_{rtag}")

    return tagcombs


def get_campaign(scope_short: str, dataset: str) -> str:
    """
    Infer the campaign and sim type (e.g. "mc23a - FS", "mc23d - AF3") for a
    dataset within a given short scope by matching known tag combinations
    embedded in the dataset name.

    The function builds the tag combinations via ``get_tag_combinations`` and
    searches for any of those substrings (e.g. "_s4162_r15540") in the dataset
    name. If exactly one campaign+simtype key (e.g., "mc23a - FS") matches, that
    key is returned.

    :param scope_short: Short scope key (e.g. "mc23", "mc20")
    :param dataset: Full AMI dataset name to inspect
    :raises ValueError: If no match can be found or if multiple campaigns match
    :return: The inferred campaign and sim type key (e.g., "mc23a - FS")
    """
    combos = get_tag_combinations(scope_short)

    matched_keys = set()
    for key, tag_list in combos.items():
        # key looks like "mc23a - FS" or "mc23d - AF3"
        for tag in tag_list:
            if tag in dataset:
                matched_keys.add(key)
                break  # Don't double-count this key for multiple tags

    if len(matched_keys) == 1:
        return next(iter(matched_keys))
    if len(matched_keys) == 0:
        raise ValueError(
            f"Could not infer campaign from dataset for scope '{scope_short}': {dataset}"
        )
    # Ambiguous
    raise ValueError(
        f"Ambiguous campaign candidates {sorted(matched_keys)} for dataset: {dataset}"
    )
