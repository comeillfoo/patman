# patman

Patch manager

## Usage:

`patman [OPTIONS] COMMAND [ARGS]...`

## Options:
  * `-v, --verbose`
    * Output extra information.
  * `--help`
    * Show this message and exit.

## Commands:
  * `apply`
    * Tries to apply patches.
  * `dehunk`
    * Excludes succesful hunks in patches.
  * `deploy`
    * Replicates project to folders that are used for testing patches.
  * `revert`
    * Reverts patches.