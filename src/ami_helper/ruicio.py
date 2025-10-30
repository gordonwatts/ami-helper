import logging
from pathlib import Path
from typing import Dict, List

from rucio.client import Client

from .datamodel import SCOPE_TAGS, get_tag_combinations

# Track non-deriv data formats
g_step_info = {"AOD": "recon"}


def init_atlas_access():
    """
    Get everything setup for ATLAS access.

    NOTE: This is a bit of a heuristic - we did `lsetup rucio` and compared
    the env variables before and after to see what was set. We then
    determined the following were important by trial and error.
    """
    import os

    # Find the rucio config file
    rucio_homes = []
    for path in Path(
        "/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase/aarch64-Linux/rucio-clients"
    ).rglob("rucio.cfg"):
        rucio_homes.append(path.parent.parent)
    rucio_home = sorted(rucio_homes, key=lambda p: str(p))[-1]
    os.environ["RUCIO_HOME"] = str(rucio_home)

    uid = os.getuid()
    os.environ["X509_USER_PROXY"] = f"/tmp/x509up_u{uid}"

    os.environ["RUCIO_AUTH_TYPE"] = "x509_proxy"
    os.environ["X509_CERT_DIR"] = (
        "/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase/etc/grid-security-emi/certificates"
    )


# If we are importing this, we'll be using rucio - so init atlas access
init_atlas_access()


# The rucio client (for effiency, create once)
g_rucio = Client()


def find_datasets(ldn: str, scope: str, content: str) -> Dict[str, List[str]]:
    # What step and content do we want to go after?
    step = g_step_info.get(content, "deriv")
    if step == "deriv" and not content.startswith("DAOD_"):
        raise ValueError(
            f"Content '{content}' not recognised as a derivation name!"
            " Must start with DAOD_."
        )
    stepformat = f".{step}.{content}."

    # Change the ldn into a search string for rucio
    scope_short = scope.split("_")[0]
    evgen_short = SCOPE_TAGS[scope_short].evgen.short
    reco_short = SCOPE_TAGS[scope_short].reco.short

    # Look at all tags
    tag_combinations = get_tag_combinations(scope_short)
    result = {}
    for tag_type, tag_comb in tag_combinations.items():
        for tag in tag_comb:
            rucio_search_string = (
                ldn.replace(f"{evgen_short}_", f"{reco_short}_").replace(
                    ".evgen.EVNT.", stepformat
                )
                + tag
                + "%"
            )

        logging.debug(f"Rucio search string: {rucio_search_string}")
        # Grab all the did's from rucio that have files
        dids = [
            x
            for x in g_rucio.list_dids(
                scope, [{"name": rucio_search_string}], did_type="container"
            )
            if isinstance(x, str) and len(list(g_rucio.list_content(scope, x))) > 0
        ]
        if len(dids) > 0:
            result[tag_type] = dids

    return result


def has_files(scope: str, ds_name: str):
    """
    Return True if the dataset has any files.

    :param scope: Description
    :type scope: str
    :param ds_name: Description
    :type ds_name: str
    """
    return len(list(g_rucio.list_content(scope, ds_name))) > 0


# def getOutputFormat(rucio, dsformat, ldns, scopeshort, tagcombs):
#     aods = {}

#     step = None
#     if dsformat == "AOD":
#         step = "recon"
#     elif "DAOD" in dsformat:
#         step = "deriv"
#     else:
#         print("ERROR: Non-recognised format entered! Should be AOD or DAOD_*.")
#         return

#     stepformat = f".{step}.{dsformat}."

#     evgenshort = scopetag_dict[scopeshort]["evgen"]["short"]
#     simshort = scopetag_dict[scopeshort]["sim"]["short"]
#     recshort = scopetag_dict[scopeshort]["reco"]["short"]

#     for ldn in ldns:
#         if ldn not in aods:
#             aods[ldn] = OrderedDict()

#         for tagcomb in tagcombs:
#             scope = ldn.replace(f"{evgenshort}_", f"{recshort}_").split(".")[0]
#             # if opts.verbose: print "DEBUG: Search term for %s is %s"%(ldn,search)
#             # dsfound=[x for x in rucio.list_dids(scope,{'name':search},type='container')]
#             # print(search)
#             dsfound = []
#             for tag in tagcombs[tagcomb]:
#                 search = (
#                     ldn.replace(f"{evgenshort}_", f"{recshort}_").replace(
#                         ".evgen.EVNT.", stepformat
#                     )
#                     + "%s" % tag
#                     + "%"
#                 )
#                 # dsfound.extend([x for x in rucio.list_dids(scope,{'name':search},did_type='container')])
#                 nonemptyds = []
#                 for x in rucio.list_dids(scope, {"name": search}, did_type="container"):
#                     if len(list(rucio.list_content(scope, x))):
#                         nonemptyds.append(x)

#                 dsfound.extend(nonemptyds)

#             aods[ldn][tagcomb] = dsfound
#     return aods
