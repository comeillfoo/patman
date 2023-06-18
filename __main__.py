#!/usr/bin/env python3
import click, os, shutil, enum, errno, re, subprocess as sp
from typing import Tuple

class PatchResult(enum.Enum):
    OK = 0
    REVERSE_APPLIED = 1
    HUNK_SUCCEED = 2
    HUNK_FAILED = 3
    INVALID_FORMAT = 4
    EOF = 5
    ERROR = 6

REASONS = {
    PatchResult.REVERSE_APPLIED: 'Already applied',
    PatchResult.HUNK_FAILED: 'Hunk failed',
    PatchResult.INVALID_FORMAT: 'Invalid format',
    PatchResult.EOF: 'Unexpected end of patch',
    PatchResult.ERROR: 'Error',
}


VERBOSE = False

OK = '\u2713'
NOTOK = '\u274c'
WARN = '\u26a0'


def _echo(text: str):
    if VERBOSE: click.echo(text)


def _validate_directory(ctx, param, value):
    if not os.path.isdir(value):
        _echo(f'Found file {value}, but expect directory')
        value = os.path.abspath(os.path.join(value, os.pardir))
        _echo(f'Forced to parent directory {value}')
    return value


def _patch(target: str, patch: str, extra_args: list[str]) -> PatchResult:
    p = sp.Popen(['patch', '-p1', '-F0', *extra_args, target],
                 stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
    stdout, stderr = '', ''
    with open(patch, 'rb') as f:
        stdout, stderr = p.communicate(input=f.read())
        stdout, stderr = stdout.decode(), stderr.decode()
    _echo(f'stdout: {stdout}')
    _echo(f'stderr: {stderr}')
    if p.returncode == 0:
        if re.search('Hunk\s*#\d+\s*succeeded', stdout) is not None:
            return PatchResult.HUNK_SUCCEED
        return PatchResult.OK
    # TODO: parse stdout/stderr for proper return codes
    if 'patch: **** Only garbage was found in the patch input.' in stderr:
        return PatchResult.INVALID_FORMAT
    elif 'patch: **** unexpected end of file in patch' in stderr:
        return PatchResult.EOF
    elif 'Assume -R' in stdout:
        if 'patching' in stdout:
            return PatchResult.HUNK_FAILED
        return PatchResult.REVERSE_APPLIED
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
    _echo(f'copied {project_path} to {dira}')
    shutil.copytree(dira, os.path.join(directory, 'b'))
    _echo(f'replicated {dira} to b')
    click.echo(f'{project_path} successfully deployed')


def _redeploy(src: str, dst: str):
    shutil.rmtree(dst)
    shutil.copytree(src, dst)

def _make_pathes(dir: str) -> Tuple[str, str]:
    return (os.path.join(dir, 'a'), os.path.join(dir, 'b'))


def _isdirs_or_die(*directories):
    for directory in directories:
        if not os.path.isdir(directory):
            _echo(f'{directory} not found')
            exit(errno.ENOENT)
        _echo(f'{directory} exists')


@cli.command()
@click.option('-C', '--directory', default=os.getcwd(),
              type=click.Path(exists=True),
              callback=_validate_directory,
              help='Path where compared directories (a, b)')
@click.argument('patches', nargs=-1,
                type=click.Path(exists=True))
def apply(directory: str, patches):
    fails = 0
    dira, dirb = _make_pathes(directory)
    _isdirs_or_die(dira, dirb)

    for patch in patches:
        _echo(f'applying {patch}...')
        rc = _patch(dirb, patch, ['-d'])
        if rc == PatchResult.OK:
            click.echo(f'{OK} {patch}')
        elif rc == PatchResult.HUNK_SUCCEED:
            click.echo(f'{WARN} {patch}')
        else:
            click.echo(f'{NOTOK} {patch} ({REASONS[rc]})')
            fails += 1
            _redeploy(dira, dirb)
    exit(fails)


def _revert(target: str, patch: str, extra_args: list[str]) -> PatchResult:
    return _patch(target, patch, ['-R', *extra_args])


@cli.command()
@click.option('-C', '--directory', default=os.getcwd(),
              type=click.Path(exists=True),
              callback=_validate_directory,
              help='Patched directory')
@click.argument('patches', nargs=-1,
                type=click.Path(exists=True))
def revert(directory: str, patches):
    for patch in reversed(patches):
        _echo(f'reverting {patch}...')
        rc = _revert(directory, patch, ['-d'])
        if rc != PatchResult.OK:
            click.echo(f'{NOTOK} {patch}')
            exit(1)
        else:
            click.echo(f'{OK} {patch}')


@cli.command()
@click.option('-C', '--directory', default=os.getcwd(),
              type=click.Path(exists=True),
              callback=_validate_directory,
              help='Path where compared directories (a, b)')
@click.argument('patches', nargs=-1,
                type=click.Path(exists=True))
def dehunk(directory: str, patches):
    fails = 0
    dira, dirb = _make_pathes(directory)
    _isdirs_or_die(dira, dirb)
    for patch in patches:
        _echo(f'applying {patch}...')
        rc = _patch(dirb, patch, ['-d'])
        if rc == PatchResult.HUNK_SUCCEED:
            # with hunks to .old
            shutil.copyfile(patch, patch + '.old')
            # TODO: generate patch from diff
            click.echo(f'{OK} {patch}')
        elif rc == PatchResult.OK:
            _echo(f'no hunks {patch} SKIP')
        else:
            fails += 1
            _redeploy(dira, dirb)
            click.echo(f'{NOTOK} {patch}')
    exit(fails)



if __name__ == '__main__':
    cli()