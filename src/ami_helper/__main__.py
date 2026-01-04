# SPDX-FileCopyrightText: 2025-present Gordon Watts <gwatts@uw.edu>
#
# SPDX-License-Identifier: MIT
import json
import logging
from enum import Enum
from typing import Annotated, Any, Callable, Mapping, Sequence

import typer

from .utils import ensure_and_import, normalize_derivation_name

# Make sure installation has completed
ensure_and_import("pyAMI_atlas")


# Define valid scopes - can be easily modified in the future
class ScopeEnum(str, Enum):
    MC16_13TEV = "mc16_13TeV"
    MC20_13TEV = "mc20_13TeV"
    MC21_13P6TEV = "mc21_13p6TeV"
    MC23_13P6TEV = "mc23_13p6TeV"


class OutputFormat(str, Enum):
    RICH = "rich"
    MARKDOWN = "markdown"
    JSON = "json"


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


def render_output(
    rows: Sequence[Mapping[str, Any]],
    output_format: OutputFormat,
    *,
    title: str | None = None,
    json_transform: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> None:
    """Render rows in the desired output format."""

    if not rows:
        if output_format is OutputFormat.JSON:
            print("[]")
        return

    if output_format is OutputFormat.JSON:
        serializable_rows = [
            dict(json_transform(row)) if json_transform else dict(row) for row in rows
        ]
        print(json.dumps(serializable_rows, indent=2))
        return

    header_keys = list(rows[0].keys())

    if output_format is OutputFormat.MARKDOWN:
        header_line = "| " + " | ".join(header_keys) + " |"
        separator_line = "|" + "|".join([" --- " for _ in header_keys]) + "|"
        print(header_line)
        print(separator_line)
        for row in rows:
            row_values = [str(row.get(key, "")) for key in header_keys]
            print("| " + " | ".join(row_values) + " |")
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title=title)
    for index, key in enumerate(header_keys):
        style = "cyan" if index == 0 else "magenta"
        table.add_column(key, style=style, no_wrap=False)

    for row in rows:
        table.add_row(*[str(row.get(key, "")) for key in header_keys])

    console = Console()
    console.print(table)


@hash_app.command("find")
def find_hash_tuples(
    scope: ScopeEnum = typer.Argument(
        ..., help="Scope for the search. Valid values will be shown in help."
    ),
    hashtags: str = typer.Argument(..., help="List of hashtags (at least one)"),
    ignore_cache: bool = typer.Option(
        False, "--ignore-cache", help="Bypass the on-disk AMI cache."
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
    List all AMI hashtag 4-tuples containing a string.
    """

    from .ami import find_hashtag, find_hashtag_tuples

    hashtag_list = find_hashtag(scope, hashtags, ignore_cache=ignore_cache)

    if len(hashtag_list) > 0:
        for ht in hashtag_list:
            all_tags = find_hashtag_tuples(ht, ignore_cache=ignore_cache)
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
    ignore_cache: bool = typer.Option(
        False, "--ignore-cache", help="Bypass the on-disk AMI cache."
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
    from .rucio import find_datasets

    requested_content = normalize_derivation_name(content)

    addr = CentralPageHashAddress(
        scope, (hashtag_level1, hashtag_level2, hashtag_level3, hashtag_level4)
    )

    evnt_ldns = find_dids_with_hashtags(addr, ignore_cache=ignore_cache)
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
    output_format: OutputFormat = typer.Option(
        OutputFormat.RICH,
        "--output-format",
        "-o",
        case_sensitive=False,
        help="Choose the output format (rich, markdown, json)",
    ),
    ignore_cache: bool = typer.Option(
        False, "--ignore-cache", help="Bypass the on-disk AMI cache."
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
) -> None:
    """
    Find datasets containing the given name.
    """
    from .ami import find_dids_with_name

    ds = find_dids_with_name(
        scope, name, require_pmg=not non_cp, ignore_cache=ignore_cache
    )

    def _dataset_json_transform(row: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "dataset": row["Dataset Name"],
            "tag_1": row["Tag 1"],
            "tag_2": row["Tag 2"],
            "tag_3": row["Tag 3"],
            "tag_4": row["Tag 4"],
        }

    table_rows: list[dict[str, Any]] = []
    for ds_name, cp_address in ds:
        tags = [str(tag) if tag is not None else "" for tag in cp_address.hash_tags]
        while len(tags) < 4:
            tags.append("")
        table_rows.append(
            {
                "Dataset Name": ds_name,
                "Tag 1": tags[0],
                "Tag 2": tags[1],
                "Tag 3": tags[2],
                "Tag 4": tags[3],
            }
        )

    render_output(
        table_rows,
        output_format,
        title="Datasets Found",
        json_transform=_dataset_json_transform,
    )


@files_app.command("metadata")
def metadata(
    scope: ScopeEnum = typer.Argument(
        ...,
        help="Scope for the search. Valid values will be shown in help. (mandatory)",
    ),
    name: str = typer.Argument(..., help="Full dataset name (exact match)"),
    output_format: OutputFormat = typer.Option(
        OutputFormat.RICH,
        "--output-format",
        "-o",
        case_sensitive=False,
        help="Choose the output format (rich, markdown, json)",
    ),
    ignore_cache: bool = typer.Option(
        False, "--ignore-cache", help="Bypass the on-disk AMI cache."
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
) -> None:
    """
    Given an exact match (EVNT), find the cross section, filter efficiency, etc.
    """
    from .ami import get_metadata

    ds = get_metadata(scope, name, ignore_cache=ignore_cache)
    metadata_rows = [{"Key": key, "Value": value} for key, value in ds.items()]

    render_output(metadata_rows, output_format, title=f"Metadata for {name}")


@files_app.command("provenance")
def Provenance(
    scope: ScopeEnum = typer.Argument(
        ...,
        help="Scope for the search. Valid values will be shown in help. (mandatory)",
    ),
    name: str = typer.Argument(..., help="Full dataset name (exact match)"),
    ignore_cache: bool = typer.Option(
        False, "--ignore-cache", help="Bypass the on-disk AMI cache."
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
    Given an exact match dataset, find the history of the dataset.
    """
    from .ami import get_provenance

    ds_list = get_provenance(scope, name, ignore_cache=ignore_cache)

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
    output_format: OutputFormat = typer.Option(
        OutputFormat.RICH,
        "--output-format",
        "-o",
        case_sensitive=False,
        help="Choose the output format (rich, markdown, json)",
    ),
    ignore_cache: bool = typer.Option(
        False, "--ignore-cache", help="Bypass the on-disk AMI cache."
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
) -> None:
    """
    Given a run number, see what datasets exist with the derivation type.
    """

    from .ami import get_by_datatype
    from .datamodel import get_campaign
    from .rucio import has_files

    ds_list = get_by_datatype(
        scope, run_number, datatype, ignore_cache=ignore_cache
    )

    good_ds = [ds for ds in ds_list if has_files(scope, ds)]

    # Determine short scope (e.g., "mc23") from enum value (e.g., "mc23_13p6TeV")
    short_scope = scope.split("_")[0]

    # Prepare rows with campaign lookup (safe against errors)
    rows: list[tuple[str, str]] = []
    for ds in good_ds:
        campaign = ""
        if short_scope:
            try:
                campaign = get_campaign(short_scope, ds)
            except Exception:
                campaign = ""
        rows.append((ds, campaign))

    def _datatype_json_transform(row: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"dataset": row["Dataset Name"], "campaign": row["Campaign"]}

    table_rows = [
        {"Dataset Name": dataset_name, "Campaign": campaign}
        for dataset_name, campaign in rows
    ]

    render_output(
        table_rows,
        output_format,
        title="Datasets with datatype",
        json_transform=_datatype_json_transform,
    )


if __name__ == "__main__":
    app()
