from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping


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
