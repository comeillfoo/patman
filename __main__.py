#!/usr/bin/env python3
import click, os, shutil, enum, errno, re, subprocess as sp
from typing import Tuple, Optional

class TextStyle:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'


class PatchResult(enum.Enum):
    OK = 0
    REVERSE_APPLIED = 1
    HUNK_SUCCEED = 2
    HUNK_FAILED = 3
    INVALID_FORMAT = 4
    FILE_NOT_FOUND = 5
    EOF = 6
    ERROR = 7

    def is_ok(self) -> bool:
        return self == PatchResult.OK or self == PatchResult.HUNK_SUCCEED


PATCH_ERROR_REASONS = {
    PatchResult.REVERSE_APPLIED: 'Already applied',
    PatchResult.HUNK_FAILED: 'Hunk failed',
    PatchResult.INVALID_FORMAT: 'Invalid format',
    PatchResult.FILE_NOT_FOUND: 'Can\'t find file to patch',
    PatchResult.EOF: 'Unexpected end of patch',
    PatchResult.ERROR: 'Error',
}


VERBOSE = False

OK = f'{TextStyle.BOLD}{TextStyle.GREEN}\u2713{TextStyle.END}'
NOTOK = f'{TextStyle.BOLD}{TextStyle.RED}\u2717{TextStyle.END}'
WARN = f'{TextStyle.BOLD}{TextStyle.YELLOW}\u26a0{TextStyle.END}'


def _echo(text: str):
    if VERBOSE: click.echo(text)


def _print_result(patch: str, rc: PatchResult = PatchResult.ERROR):
    if rc == PatchResult.OK:
        click.echo(f'{OK} {patch}')
    elif rc == PatchResult.HUNK_SUCCEED:
        click.echo(f'{WARN} {patch} (Consider running dehunk command)')
    else:
        click.echo(f'{NOTOK} {patch} ({PATCH_ERROR_REASONS[rc]})')



def _validate_directory(ctx, param, value):
    if not os.path.isdir(value):
        _echo(f'Found file {value}, but expect directory')
        value = os.path.abspath(os.path.join(value, os.pardir))
        _echo(f'Forced to parent directory {value}')
    return value


def _diff(a: str, b: str, extra_args: list[str]) -> Optional[str]:
    cmd = ['diff', '-updrN', *extra_args, a, b]
    _echo(' '.join([cmd[0].upper()] + cmd[1:]))
    p = sp.Popen(cmd,
                 stdout=sp.PIPE, stderr=sp.PIPE, text=True)
    stdout, stderr = p.communicate()
    _echo(f'stdout: {stdout.strip()}')
    _echo(f'stderr: {stderr.strip()}')
    return stdout if p.returncode != 2 else None


def _patch(target: str, patch: str, extra_args: list[str]) -> PatchResult:
    cmd = ['patch', '-p1', '-F0', *extra_args, target]
    _echo(' '.join([cmd[0].upper()] + cmd[1:]))
    p = sp.Popen(cmd,
                 stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
    stdout, stderr = '', ''
    with open(patch, 'rb') as f:
        stdout, stderr = p.communicate(input=f.read())
        stdout, stderr = stdout.decode(), stderr.decode()
    _echo(f'stdout: {stdout.strip()}')
    _echo(f'stderr: {stderr.strip()}')
    if p.returncode == 0:
        if re.search('Hunk\s*#\d+\s*succeeded', stdout) is not None:
            return PatchResult.HUNK_SUCCEED
        return PatchResult.OK
    if 'patch: **** Only garbage was found in the patch input.' in stderr:
        return PatchResult.INVALID_FORMAT
    elif 'patch: **** unexpected end of file in patch' in stderr:
        return PatchResult.EOF

    is_partly_succeeded = 'patching' in stdout
    if 'Assume -R' in stdout:
        return PatchResult.HUNK_FAILED if is_partly_succeeded else PatchResult.REVERSE_APPLIED
    elif 'can\'t find file to patch' in stdout:
        return PatchResult.HUNK_FAILED if is_partly_succeeded else PatchResult.FILE_NOT_FOUND
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
    return ('a', 'b') if dir == '.' else (os.path.join(dir, 'a'), os.path.join(dir, 'b'))


def _isdirs_or_die(*directories):
    for directory in directories:
        if not os.path.isdir(directory):
            click.echo(f'{directory} not found')
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
        rc = _patch(dirb, patch, ['-d'])
        _print_result(patch, rc)
        if not rc.is_ok():
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
        _print_result(patch, rc)
        if not rc.is_ok():
            exit(1)


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
        rc = _patch(dirb, patch, ['-d'])
        _print_result(patch, rc)
        if rc == PatchResult.HUNK_SUCCEED:
            # with hunks to .old
            shutil.copyfile(patch, patch + '.orig')
            dehunked = _diff(dira, dirb, ['-x', '*.orig'])
            if dehunked is None:
                click.echo(f'Failed to dehunk {patch}')
                exit(fails)
            with open(patch, 'w') as p:
                p.write(dehunked)
        elif rc == PatchResult.OK:
            _echo(f'no hunks for {patch} -- SKIP')
        else:
            fails += 1
            _redeploy(dira, dirb)
    exit(fails)



if __name__ == '__main__':
    cli()