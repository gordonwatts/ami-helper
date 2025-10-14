# SPDX-FileCopyrightText: 2025-present Gordon Watts <gwatts@uw.edu>
#
# SPDX-License-Identifier: MIT
import typer

app = typer.Typer()

@app.command("list-hash-tuples")
def list_hash_tuples(strings: list[str] = typer.Argument(..., min=1, help="List of strings (at least one)")):
	for s in strings:
		print(s)

if __name__ == "__main__":
	app()

