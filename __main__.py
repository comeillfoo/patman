#!/usr/bin/env python3
import click, os, shutil, enum, errno, subprocess as sp


class PatchResult(enum.Enum):
    OK = 0
    REVERSE_APPLIED = 1
    HUNK_SUCCEED = 2
    HUNK_FAILED = 3
    INVALID_FORMAT = 4
    ERROR = 5


VERBOSE = False

OK='\u2713'
NOTOK='\u274c'


def _echo(text: str):
    if VERBOSE: click.echo(text)


def _validate_directory(ctx, param, value):
    if not os.path.isdir(value):
        _echo(f'Found file {value}, but expect directory')
        value = os.path.abspath(os.path.join(value, os.pardir))
        _echo(f'Forced to parent directory {value}')
    return value


def _patch(target: str, patch: str, extra_args: list[str]) -> int:
    p = sp.Popen(['patch', '-p1', '-F0', *extra_args, target],
                 stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
    stdout, stderr = '', ''
    with open(patch, 'rb') as f:
        stdout, stderr = p.communicate(input=f.read())
    _echo(stdout.decode())
    _echo(stderr.decode())
    if p.returncode == 0:
        return PatchResult.OK
    return PatchResult.ERROR


@click.group()
@click.option('-v', '--verbose', count=True)
def cli(verbose: bool):
    global VERBOSE
    VERBOSE = verbose


@cli.command()
@click.option('-C', '--directory', default=os.getcwd(),
              type=click.Path(exists=True),
              callback=_validate_directory,
              help='Path where to put the compared directories')
@click.argument('project_path', type=click.Path(exists=True))
def deploy(directory: str, project_path: str):
    dira = os.path.join(directory, 'a')
    shutil.copytree(project_path, dira)
    shutil.copytree(dira, os.path.join(directory, 'b'))


@cli.command()
@click.option('-C', '--directory', default=os.getcwd(),
              type=click.Path(exists=True),
              callback=_validate_directory,
              help='Path where compared directories (a, b)')
@click.argument('patches', nargs=-1,
                type=click.Path(exists=True))
def apply(directory: str, patches) -> int:
    fails = 0
    dira = os.path.join(directory, 'a')
    dirb = os.path.join(directory, 'b')
    if not os.path.isdir(dira) or not os.path.isdir(dirb):
        _echo(f'no a and b found in {directory}, run deploy firstly')
        exit(errno.ENOENT)

    for patch in patches:
        _echo(f'applying {patch}...')
        rc = _patch(dirb, patch, ['-d'])
        if rc != PatchResult.OK:
            click.echo(f'{NOTOK} {patch}')
            fails += 1
            shutil.rmtree(dirb)
            shutil.copytree(dira, dirb)
        else:
            click.echo(f'{OK} {patch}')
    exit(fails)


if __name__ == '__main__':
    cli()