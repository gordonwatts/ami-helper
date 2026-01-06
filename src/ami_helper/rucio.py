import logging
from pathlib import Path
from typing import Dict, List

from rucio.client import Client
from rucio.common.exception import DataIdentifierNotFound

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
    if Path("/opt/rucio/etc/rucio.cfg").exists():
        rucio_homes.append(Path("/opt/rucio"))
    for path in Path(
        "/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase/aarch64-Linux/rucio-clients"
    ).rglob("rucio.cfg"):
        rucio_homes.append(path.parent.parent)

    init_rucio = True
    if len(rucio_homes) == 0:
        logging.error(
            "Could not find rucio config file! Will continue, but any direct rucio access will fail"
        )
        rucio_home = Path("/tmp/nonexistent_rucio_home")
        init_rucio = False
    else:
        rucio_home = sorted(rucio_homes, key=lambda p: str(p))[-1]
    os.environ.setdefault("RUCIO_HOME", str(rucio_home))

    uid = os.getuid()
    os.environ.setdefault("X509_USER_PROXY", f"/tmp/x509up_u{uid}")

    os.environ.setdefault("RUCIO_AUTH_TYPE", "x509_proxy")

    # Setup rucio account name - the user really has to do this. We can
    # guess, but depending on the environment, it may be very wrong.
    if "RUCIO_ACCOUNT" not in os.environ:
        import getpass

        default_account = os.environ.get("USER")
        if not default_account:
            try:
                default_account = getpass.getuser()
            except Exception:
                default_account = "unknown"
        os.environ["RUCIO_ACCOUNT"] = default_account
        logging.warning(
            f"RUCIO_ACCOUNT not set; defaulting to '{default_account}'. If this does not match "
            "your X509 cert, rucio operations may fail later on."
        )

    # Find cert directory
    cvmfs_cert_dir = "/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase/etc/grid-security-emi/certificates"
    fallback_cert_dir = "/etc/grid-security/certificates/"

    if Path(cvmfs_cert_dir).exists():
        os.environ.setdefault("X509_CERT_DIR", cvmfs_cert_dir)
    elif Path(fallback_cert_dir).exists():
        os.environ.setdefault("X509_CERT_DIR", fallback_cert_dir)
    else:
        logging.error(
            "X509 cert dir not set, can't find certificates, g_rucio is going to fail when used"
        )
        init_rucio = False

    # Setup the g_rucio
    if init_rucio:
        global g_rucio
        g_rucio = Client()


# If we are importing this, we'll be using rucio - so init atlas access
g_rucio = None
init_atlas_access()


def find_datasets(ldn: str, scope: str, content: str) -> Dict[str, List[str]]:
    # What step and content do we want to go after?
    step = g_step_info.get(content, "deriv")
    if step == "deriv" and not content.startswith("DAOD_"):
        raise ValueError(
            f"Content '{content}' not recognized as a derivation name!"
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
    try:
        return len(list(g_rucio.list_content(scope, ds_name))) > 0
    except DataIdentifierNotFound:
        return False
