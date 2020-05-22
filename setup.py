from setuptools import find_packages, setup

install_requires = [
    'alembic>=1.4.1',
    'asyncpg>=0.20.1',
    'asyncpgsa>=0.26.1',
    'psycopg2-binary>=2.7.7',
    'click>=7.0'
    'SQLAlchemy>=1.3.15',
]

setup_requires = [
    'setuptools_scm>=3.3.3',
]

tests_require = [
    'pytest>=5.3.5',
    'pytest-cov>=2.8.1',
]

setup(
    name='alembic_clamp',
    use_scm_version=True,
    description='A wrapper around alembic (SQLAlchemy migration tool), that is configurable from code instead of alembic.ini file.',
    packages=find_packages(include=['alembic_clamp', 'alembic_clamp.*']),
    include_package_data=True,
    install_requires=install_requires,
    setup_requires=setup_requires,
    tests_require=tests_require,
    extras_require={
        'test': tests_require,
    },
)
