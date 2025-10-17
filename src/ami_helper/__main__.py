# SPDX-FileCopyrightText: 2025-present Gordon Watts <gwatts@uw.edu>
#
# SPDX-License-Identifier: MIT
import logging
from enum import Enum
from typing import Annotated, Optional

import typer

from .datamodel import SCOPE_TAGS


# Define valid scopes - can be easily modified in the future
class ScopeEnum(str, Enum):
    MC16_13TEV = "mc16_13TeV"
    MC20_13TEV = "mc20_13TeV"
    MC21_13P6TEV = "mc21_13p6TeV"
    MC23_13P6TEV = "mc23_13p6TeV"


VALID_SCOPES = [scope.value for scope in ScopeEnum]

app = typer.Typer()
files_app = typer.Typer()
hash_app = typer.Typer()

app.add_typer(files_app, name="datasets", help="Commands for working with datasets")
app.add_typer(hash_app, name="hashtags", help="Commands for working with AMI hashes")


def verbose_callback(verbose: int) -> None:
    """Configure logging based on verbose flag count."""
    root_logger = logging.getLogger()

    # Remove existing handlers to reconfigure
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create a new handler
    handler = logging.StreamHandler()

    if verbose == 0:
        # Default: WARNING level
        root_logger.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    elif verbose == 1:
        # -v: INFO level
        root_logger.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(name)s: %(message)s"))
    else:
        # -vv or more: DEBUG level
        root_logger.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter(
                "%(levelname)s: %(name)s:%(funcName)s:%(lineno)d: %(message)s"
            )
        )

    root_logger.addHandler(handler)


@hash_app.command("find")
def find_hash_tuples(
    scope: ScopeEnum = typer.Argument(
        ..., help="Scope for the search. Valid values will be shown in help."
    ),
    hashtags: str = typer.Argument(..., help="List of hashtags (at least one)"),
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Increase verbosity (-v for INFO, -vv for DEBUG)",
            callback=verbose_callback,
        ),
    ] = 0,
):
    """
    List all AMI hashtag 4-tuples containing a string.
    """

    from .ami import find_hashtag, find_hashtag_tuples

    hashtag_list = find_hashtag(scope, hashtags)

    if len(hashtag_list) > 0:
        for ht in hashtag_list:
            all_tags = find_hashtag_tuples(ht)
            for t in all_tags:
                print(" ".join([str(h) for h in t.hash_tags]))


@files_app.command("with-hashtags")
def with_hashtags(
    scope: ScopeEnum = typer.Argument(
        ..., help="Scope for the search. Valid values will be shown in help."
    ),
    hashtag_level1: str = typer.Argument(..., help="First hashtag (mandatory)"),
    hashtag_level2: str = typer.Argument(..., help="Second hashtag (mandatory)"),
    hashtag_level3: str = typer.Argument(..., help="Third hashtag (mandatory)"),
    hashtag_level4: str = typer.Argument(..., help="Fourth hashtag (mandatory)"),
    content: str = typer.Option(
        "envt",
        help="Data content of file (evnt, phys, physlite, or custom value like DAOD_LLP1)",
    ),
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Increase verbosity (-v for INFO, -vv for DEBUG)",
            callback=verbose_callback,
        ),
    ] = 0,
):
    """
    Find files with specific hashtags.
    """
    from .ami import find_dids_with_hashtags
    from .datamodel import CentralPageHashAddress

    # Map short names to full DAOD names, but allow any custom value
    content_mapping = {
        "evnt": "EVNT",
        "phys": "DAOD_PHYS",
        "physlite": "DAOD_PHYSLITE",
    }
    actual_content = content_mapping.get(content, content)

    addr = CentralPageHashAddress(
        scope, [hashtag_level1, hashtag_level2, hashtag_level3, hashtag_level4]
    )

    ldns = find_dids_with_hashtags(addr)

    for ldn in ldns:
        print(ldn)


if __name__ == "__main__":
    app()
