# SPDX-FileCopyrightText: 2025-present Gordon Watts <gwatts@uw.edu>
#
# SPDX-License-Identifier: MIT
import typer
from typing import Annotated
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


@app.command("list-hash-tuples")
def list_hash_tuples(
    scope: ScopeEnum = typer.Argument(
        ..., help="Scope for the search. Valid values will be shown in help."
    ),
    hashtags: list[str] = typer.Argument(
        ..., min=1, help="List of hashtags (at least one)"
    ),
):

    from .ami import find_hashtag_tuples

    hashtag_list = find_hashtag_tuples(scope, hashtags[0])
    for possiblehash in hashtag_list:
        print(possiblehash)


if __name__ == "__main__":
    app()
