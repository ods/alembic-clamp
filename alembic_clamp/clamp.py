from collections import ChainMap
import logging
from pathlib import Path
from typing import Union

from alembic.autogenerate import RevisionContext
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
import sqlalchemy.pool
from sqlalchemy import MetaData

logger = logging.getLogger(__name__)


class AlembicClamp:
    _script_directory = None

    def __init__(
        self, dsn: str, metadata: MetaData, migrations_path: Union[str, Path],
        config_args: dict = {},
    ):
        self.dsn = dsn
        self.metadata = metadata
        self.script_location = Path(migrations_path).resolve()
        config_args = ChainMap(
            config_args,
            {
                'sqlalchemy.url': dsn,
                'script_location': self.script_location,
            },
        )
        self.config = Config(config_args=config_args)

    @property
    def script_directory(self):
        # This won't work before initialization
        if self._script_directory is None:
            self._script_directory = ScriptDirectory.from_config(self.config)
        return self._script_directory

    def _run_env_online(self, e_ctx: EnvironmentContext):
        """
        Equivalent of running env.py script in online mode (with actual
        database connection)
        """
        engine = sqlalchemy.engine_from_config(
            e_ctx.config.get_section(e_ctx.config.config_ini_section),
            prefix='sqlalchemy.',
            poolclass=sqlalchemy.pool.NullPool,
        )
        transaction_per_migration = \
            e_ctx.config.get_main_option('transaction_per_migration', False)

        with engine.connect() as connection:
            e_ctx.configure(
                connection=connection,
                target_metadata=self.metadata,
                transaction_per_migration=transaction_per_migration,
            )

            with e_ctx.begin_transaction():
                e_ctx.run_migrations()

        engine.dispose()

    def _run_env_offline(self, e_ctx: EnvironmentContext):
        """
        Equivalent of running env.py script in offline mode (without connecting
        to database)
        """
        e_ctx.configure(url=self.dsn, target_metadata=self.metadata,
                        literal_binds=True)

        with e_ctx.begin_transaction():
            e_ctx.run_migrations()

    def _new_migration_context(self, *, message=None):
        revision_context = RevisionContext(
            self.config,
            self.script_directory,
            command_args={
                'message': message, 'autogenerate': True, 'sql': False,
                'head': 'head', 'splice': False, 'branch_label': None,
                'version_path': None, 'rev_id': None, 'depends_on': None,
            },
        )

        def retrieve_migrations(rev, context):
            revision_context.run_autogenerate(rev, context)
            return []

        e_ctx = EnvironmentContext(
            self.config,
            self.script_directory,
            fn=retrieve_migrations,
            as_sql=False,
            template_args=revision_context.template_args,
            revision_context=revision_context,
        )
        self._run_env_online(e_ctx)

        return revision_context

    def has_changes(self):
        revision_context = self._new_migration_context()
        return not (
            revision_context.generated_revisions[-1].upgrade_ops.is_empty()
        )

    def new_migration(self, *, message=None, allow_empty=False):
        revision_context = self._new_migration_context(message=message)

        if (
                not allow_empty and
                revision_context.generated_revisions[-1].upgrade_ops.is_empty()
        ):
            logger.info('No changes detected')
            return False

        # Write scripts
        list(revision_context.generate_scripts())
        return True

    def get_current(self):
        revision = None

        def set_revision(rev, context):
            nonlocal revision
            revision = rev
            return []

        e_ctx = EnvironmentContext(
            self.config,
            self.script_directory,
            fn=set_revision,
        )
        self._run_env_online(e_ctx)

        return self.script_directory.revision_map.get_revision(revision)

    def _migrate(self, revision, apply_migration):
        e_ctx = EnvironmentContext(
            self.config,
            self.script_directory,
            fn=apply_migration,
            as_sql=False,
            starting_rev=None,
            destination_rev=revision,
            tag=None,
        )
        self._run_env_online(e_ctx)

    def _show_migrate_sql(self, starting_revision, revision, apply_migration):
        if starting_revision in (None, 'current'):
            current = self.get_current()
            starting_revision = 'base' if current is None else current.revision

        e_ctx = EnvironmentContext(
            self.config,
            self.script_directory,
            fn=apply_migration,
            as_sql=True,
            starting_rev=starting_revision,
            destination_rev=revision,
            tag=None,
        )
        self._run_env_offline(e_ctx)

    def upgrade(self, revision='head'):
        def apply_migration(rev, context):
            return self.script_directory._upgrade_revs(revision, rev)

        return self._migrate(revision, apply_migration)

    def show_upgrade_sql(self, revision='head', starting_revision=None):
        def apply_migration(rev, context):
            return self.script_directory._upgrade_revs(revision, rev)

        self._show_migrate_sql(starting_revision, revision, apply_migration)

    def downgrade(self, revision='base'):
        def apply_migration(rev, context):
            return self.script_directory._downgrade_revs(revision, rev)

        return self._migrate(revision, apply_migration)

    def show_downgrade_sql(self, revision='base', starting_revision=None):
        def apply_migration(rev, context):
            return self.script_directory._downgrade_revs(revision, rev)

        self._show_migrate_sql(starting_revision, revision, apply_migration)
