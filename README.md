# ami-helper

[![PyPI - Version](https://img.shields.io/pypi/v/ami-helper.svg)](https://pypi.org/project/ami-helper)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ami-helper.svg)](https://pypi.org/project/ami-helper)

-----

## Table of Contents

- [Installation](#installation)
- [License](#license)

## Installation

```console
pip install ami-helper
```

## Usage

1. Use an `atlas_al9` image.
1. Make sure that there is a valid x509 cert in the standard place. This will need it to access AMI and rucio.
  - You can usually do this using `lsetup rucio` and then `voms-proxy-init -voms atlas` in any window.

At this point `ami-helper` commands should work. Long-term this is a bit unstable - the environment variables that are set here could change with future implementations (e.g. tokens, etc.)

## License

`ami-helper` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
