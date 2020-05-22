import functools
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Union

import alembic
import click as click
from sqlalchemy import MetaData

from .clamp import AlembicClamp


class AlembicGroup(click.Group):
    commands = {}

    def __init__(
        self, name: str, db_settings: Dict, metadata: MetaData,
        migrations_path: Union[str, Path], config_args={},
    ):
        super().__init__(
            name=name,
            help='Migration commands',
            commands=self.commands,
        )
        self.__config = SimpleNamespace(
            db_settings=db_settings,
            models_metadata=metadata,
            migrations_path=migrations_path,
            config_args=config_args,
        )
        self.add_command(init)

    def invoke(self, ctx):
        ctx.obj = self.__config
        super().invoke(ctx)


def get_alembic_clamp():
    ctx = click.get_current_context()

    dsn = ctx.obj.db_settings['dsn']
    metadata = ctx.obj.models_metadata
    migrations_path = ctx.obj.migrations_path

    return AlembicClamp(
        dsn=dsn, metadata=metadata, migrations_path=migrations_path,
        config_args=ctx.obj.config_args,
    )


def command(*args, **kwargs):
    def deco(func):

        @functools.wraps(func)
        def wrapper(**func_args):
            try:
                func(**func_args)
            except alembic.util.exc.CommandError as exc:
                raise click.ClickException(exc)

        cmd = click.command(*args, **kwargs)(wrapper)
        AlembicGroup.commands[cmd.name] = cmd
        return cmd

    return deco


@command(help='Initialize a new scripts directory')
@click.option('-f', '--force', is_flag=True)
def init(force):
    aw = get_alembic_clamp()

    script_dir = Path(aw.script_location)
    if script_dir.exists() and not force:
        raise click.ClickException(
            f'Directory {script_dir} already exists')
    script_dir.mkdir(parents=True, exist_ok=True)

    versions_dir = script_dir.joinpath('versions')
    if not versions_dir.is_dir():
        click.echo(f'Creating directory {versions_dir}')
        versions_dir.mkdir()

    template_dir = Path(aw.config.get_template_directory(), 'generic')
    for file_name in ['script.py.mako']:
        src_path = template_dir.joinpath(file_name)
        dst_path = script_dir.joinpath(file_name)
        if dst_path.is_file():
            click.echo(f'Overwriting existing file {dst_path}')
        else:
            click.echo(f'Generating {dst_path}')
        shutil.copyfile(src_path, dst_path)


@command(help='Create migration script')
@click.option('-m', '--message', help='message to apply to the revision')
@click.option(
    '-e', '--allow-empty', is_flag=True, default=False,
    help='generate empty script if no changes detected'
)
def new_migration(message, allow_empty):
    aw = get_alembic_clamp()
    aw.new_migration(message=message, allow_empty=allow_empty)


@command(help='Run migration to specified revision')
@click.argument('revision', default='head')
def upgrade(revision):
    aw = get_alembic_clamp()
    if ":" in revision:
        raise click.ClickException(
            'Range revision is not allowed for upgrade')
    aw.upgrade(revision)


@command(help='Show SQL for migration')
@click.argument('revision', default='head')
def show_upgrade_sql(revision):
    aw = get_alembic_clamp()

    starting_revision = None
    if ':' in revision:
        starting_revision, revision = revision.split(':', 2)

    aw.show_upgrade_sql(revision=revision, starting_revision=starting_revision)


@command(help='Run migration to specified revision')
@click.argument('revision', default='base')
def downgrade(revision):
    aw = get_alembic_clamp()
    if ":" in revision:
        raise click.ClickException(
            'Range revision is not allowed for downgrade')
    aw.downgrade(revision)


@command(help='Show SQL for migration')
@click.argument('revision', default='base')
def show_downgrade_sql(revision):
    aw = get_alembic_clamp()

    starting_revision = None
    if ':' in revision:
        starting_revision, revision = revision.split(':', 2)

    aw.show_downgrade_sql(
        revision=revision, starting_revision=starting_revision,
    )
