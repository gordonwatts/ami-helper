# SPDX-FileCopyrightText: 2025-present Gordon Watts <gwatts@uw.edu>
#
# SPDX-License-Identifier: MIT
import logging
import typer
from typing import Annotated, Optional
from enum import Enum
from .datamodel import SCOPE_TAGS


# Define valid scopes - can be easily modified in the future
class ScopeEnum(str, Enum):
    MC16_13TEV = "mc16_13TeV"
    MC20_13TEV = "mc20_13TeV"
    MC21_13P6TEV = "mc21_13p6TeV"
    MC23_13P6TEV = "mc23_13p6TeV"


VALID_SCOPES = [scope.value for scope in ScopeEnum]

app = typer.Typer()


def verbose_callback(verbose: int):
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


@app.command("list-hash-tuples")
def list_hash_tuples(
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

    from .ami import find_hashtag

    hashtag_list = find_hashtag(scope, hashtags)

    if len(hashtag_list) > 0:
        from .ami import find_hashtag_tuples

        for ht in hashtag_list:
            all_tags = find_hashtag_tuples(ht)
            for t in all_tags:
                print(", ".join([str(h) for h in t.hash_tags]))


if __name__ == "__main__":
    app()
