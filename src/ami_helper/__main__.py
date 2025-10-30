# SPDX-FileCopyrightText: 2025-present Gordon Watts <gwatts@uw.edu>
#
# SPDX-License-Identifier: MIT
import logging
from enum import Enum
from typing import Annotated, Optional

import typer

from .datamodel import SCOPE_TAGS
from .ruicio import find_datasets


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
        "evnt",
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
    Find datasets tagged with the four hashtags.
    """
    from .ami import find_dids_with_hashtags
    from .datamodel import CentralPageHashAddress

    # Map short names to full DAOD names, but allow any custom value
    content_mapping = {
        "evnt": "EVNT",
        "phys": "DAOD_PHYS",
        "physlite": "DAOD_PHYSLITE",
        "EVNT": "EVNT",
        "PHYS": "DAOD_PHYS",
        "PHYSLITE": "DAOD_PHYSLITE",
    }
    requested_content = content_mapping.get(content, content)

    addr = CentralPageHashAddress(
        scope, [hashtag_level1, hashtag_level2, hashtag_level3, hashtag_level4]
    )

    evnt_ldns = find_dids_with_hashtags(addr)
    if requested_content == "EVNT":
        for ldn in evnt_ldns:
            print(ldn)
    else:
        for ldn in evnt_ldns:
            print(ldn + ":")
            for found_type, found_ldns in find_datasets(
                ldn, scope, requested_content
            ).items():
                print(f"  {found_type}:")
                for found_ldn in found_ldns:
                    print(f"    {found_ldn}")
        ldns = []


@files_app.command("with-name")
def with_name(
    scope: ScopeEnum = typer.Argument(
        ...,
        help="Scope for the search. Valid values will be shown in help. (mandatory)",
    ),
    name: str = typer.Argument(..., help="Name to search for (mandatory)"),
    non_cp: bool = typer.Option(
        False,
        "--non-cp",
        help="Also search non-Central Page PMG datasets (e.g. exotics signals, etc.)",
    ),
    markdown: bool = typer.Option(
        False,
        "--markdown",
        "-m",
        help="Output as markdown table instead of rich table",
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
    Find datasets tagged with the four hashtags.
    """
    from rich.console import Console
    from rich.table import Table

    from .ami import find_dids_with_name

    ds = find_dids_with_name(scope, name, require_pmg=not non_cp)

    if markdown:
        # Output as markdown table
        print("| Dataset Name | Tag 1 | Tag 2 | Tag 3 | Tag 4 |")
        print("|--------------|-------|-------|-------|-------|")
        for ds_name, cp_address in ds:
            tags = [str(tag) if tag is not None else "" for tag in cp_address.hash_tags]
            while len(tags) < 4:
                tags.append("")
            print(f"| {ds_name} | {tags[0]} | {tags[1]} | {tags[2]} | {tags[3]} |")
    else:
        # Create a rich table
        table = Table(title="Datasets Found")
        table.add_column("Dataset Name", style="cyan", no_wrap=False)
        table.add_column("Tag 1", style="magenta")
        table.add_column("Tag 2", style="magenta")
        table.add_column("Tag 3", style="magenta")
        table.add_column("Tag 4", style="magenta")

        for ds_name, cp_address in ds:
            # Extract the individual tags, handling None values
            tags = [str(tag) if tag is not None else "" for tag in cp_address.hash_tags]
            # Pad with empty strings if we have less than 4 tags
            while len(tags) < 4:
                tags.append("")
            table.add_row(ds_name, tags[0], tags[1], tags[2], tags[3])

        # Print the table
        console = Console()
        console.print(table)


@files_app.command("metadata")
def metadata(
    scope: ScopeEnum = typer.Argument(
        ...,
        help="Scope for the search. Valid values will be shown in help. (mandatory)",
    ),
    name: str = typer.Argument(..., help="Full dataset name (exact match)"),
    markdown: bool = typer.Option(
        False,
        "--markdown",
        "-m",
        help="Output as markdown table instead of rich table",
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
    Given an extact match (EVNT), find the cross section, filter efficiency, etc.
    """
    from rich.console import Console
    from rich.table import Table

    from .ami import get_metadata

    ds = get_metadata(scope, name)

    if markdown:
        # Output as markdown table
        print("| Key | Value |")
        print("|-----|-------|")
        for key, value in ds.items():
            print(f"| {key} | {value} |")
    else:
        # Create a rich table
        table = Table(title=f"Metadata for {name}")
        table.add_column("Key", style="cyan", no_wrap=False)
        table.add_column("Value", style="magenta", no_wrap=False)

        for key, value in ds.items():
            table.add_row(key, value)

        # Print the table
        console = Console()
        console.print(table)


@files_app.command("provenance")
def Provenance(
    scope: ScopeEnum = typer.Argument(
        ...,
        help="Scope for the search. Valid values will be shown in help. (mandatory)",
    ),
    name: str = typer.Argument(..., help="Full dataset name (exact match)"),
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
    Given an extact match dataset, find the history of the dataset.
    """
    from .ami import get_provenance

    ds_list = get_provenance(scope, name)

    for ds in ds_list:
        print(ds)


@files_app.command("with-datatype")
def with_datatype(
    scope: ScopeEnum = typer.Argument(
        ...,
        help="Scope for the search. Valid values will be shown in help. (mandatory)",
    ),
    run_number: int = typer.Argument(
        ..., help="Run number of the dataset you want to look up"
    ),
    datatype: str = typer.Argument(
        ..., help="Exact match of data type (DAOD_PHYSLITE, AOD, etc.)"
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
    Given an extact match dataset, find the history of the dataset.
    """

    from rich.console import Console
    from rich.table import Table

    from .ami import get_by_datatype
    from .ruicio import has_files

    ds_list = get_by_datatype(scope, run_number, datatype)

    good_ds = [ds for ds in ds_list if has_files(scope, ds)]

    for ds in good_ds:
        print(ds)


if __name__ == "__main__":
    app()
