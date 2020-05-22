from pkg_resources import get_distribution, DistributionNotFound

from .clamp import AlembicClamp


try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    pass
