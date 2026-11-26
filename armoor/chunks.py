"""Chunking strategies of the zarr stores written by armoor.

A `ChunkType` states how a dataset will be read (e.g. time series at a few
points, or full maps), not chunk sizes: those are computed by
`ChunkType.resolve` from the dimensions and dtype of each dataset. It is
declared as ``chunk_type`` on `armoor.comp.comparison.Comparison` and
`armoor.data.datatype.DataType` classes, see `select_chunk_type`.

This module must not import from ``armoor.comp`` or ``armoor.data``.
"""

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChunkType:
    """One way of splitting a dataset into chunks.

    Attributes
    ----------
    name : str
        Name, for logging.
    full : tuple of str
        Dimensions that are never split.
    weights : dict
        Relative chunk lengths of the other dimensions (1 if absent): a
        dimension of weight 4 gets chunks 4 times longer than one of weight 1.
    target_mb : float
        Upper bound of the uncompressed size in MiB of a chunk of the largest
        variable. Exceeded only when the `full` dimensions alone are larger.
    """

    name: str
    full: tuple = ()
    weights: dict = field(default_factory=dict)
    target_mb: float = 64

    def resolve(self, ds):
        """Compute the chunk sizes for a dataset.

        Parameters
        ----------
        ds : xarray.Dataset
            Dataset to chunk. The largest data variable sets the sizes, so
            that all the variables have aligned chunks.

        Returns
        -------
        dict
            Chunk length of every dimension of the dataset.
        """
        sizes = dict(ds.sizes)
        if not ds.data_vars or any(size == 0 for size in sizes.values()):
            return sizes
        largest = max(ds.data_vars.values(), key=lambda var: var.nbytes)
        chunks = dict(sizes)
        split = [dim for dim in largest.dims if dim not in self.full]
        fixed = math.prod(sizes[dim] for dim in largest.dims if dim in self.full)
        budget = self.target_mb * 1024**2 / largest.dtype.itemsize / fixed

        def lengths(scale):
            return {
                dim: max(1, min(sizes[dim], int(self.weights.get(dim, 1) * scale))) for dim in split
            }

        # Largest scale that fits; dimensions shorter than their share are
        # kept whole, which leaves room for the other ones.
        low, high = 0.0, float(max([sizes[d] / self.weights.get(d, 1) for d in split], default=0))
        if math.prod(lengths(high).values()) <= budget:
            low = high
        else:
            for _ in range(60):
                mid = (low + high) / 2
                if math.prod(lengths(mid).values()) <= budget:
                    low = mid
                else:
                    high = mid
        for dim, length in lengths(low).items():
            # Same number of chunks, but balanced: no sliver at the end.
            chunks[dim] = math.ceil(sizes[dim] / math.ceil(sizes[dim] / length))
        return chunks


DEFAULT = ChunkType("default", full=("z",))
POINT = ChunkType("point", full=("z",), weights={"time": 4})
MAP = ChunkType("map", full=("y", "x"))


def select_chunk_type(comparison=None, data_type=None):
    """Choose the chunk type of a dataset.

    Parameters
    ----------
    comparison : armoor.comp.comparison.Comparison, optional
        Comparison the dataset is prepared for. It has priority, as it knows
        how the data will be read.
    data_type : armoor.data.datatype.DataType, optional
        Type of the dataset.

    Returns
    -------
    ChunkType
        `DEFAULT` if neither declares one.
    """
    for owner in (comparison, data_type):
        chunk_type = getattr(owner, "chunk_type", None)
        if chunk_type is not None:
            return chunk_type
    return DEFAULT

