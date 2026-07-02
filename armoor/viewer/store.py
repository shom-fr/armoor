"""In-memory registry of loaded datasets (DatasetStore).

Thread-safe dict {uuid → DatasetEntry}.
"""

import concurrent.futures
import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)


@dataclass
class DatasetEntry:
    """Holds an open xarray Dataset plus extracted metadata."""

    id: str
    path: str
    fmt: str
    ds: xr.Dataset

    # Extracted at load time (no data loaded)
    variables: List[str] = field(default_factory=list)
    time_values: List[str] = field(default_factory=list)  # ISO strings
    depth_values: List[float] = field(default_factory=list)
    lon_range: Optional[List[float]] = None  # [west, east]
    lat_range: Optional[List[float]] = None  # [south, north]
    dims: Dict[str, int] = field(default_factory=dict)


class DatasetStore:
    """Thread-safe in-memory registry of open datasets."""

    def __init__(self):
        self._lock = threading.Lock()
        self._store: Dict[str, DatasetEntry] = {}
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="ds-load")
        self._jobs: Dict[str, dict] = {}
        self._jobs_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_load(self, path: str, fmt: str) -> str:
        """Submit a dataset load in a background thread.  Returns a job_id."""
        job_id = str(uuid.uuid4())
        with self._jobs_lock:
            self._jobs[job_id] = {"status": "loading", "message": "Opening dataset…", "dataset_id": None, "error": None}
        self._executor.submit(self._load_job, job_id, path, fmt)
        return job_id

    def _load_job(self, job_id: str, path: str, fmt: str) -> None:
        try:
            entry = self.load(path, fmt)
            with self._jobs_lock:
                self._jobs[job_id].update({"status": "ready", "dataset_id": entry.id, "message": "Done"})
        except Exception as exc:
            logger.exception("Background load failed for job %s", job_id)
            with self._jobs_lock:
                self._jobs[job_id].update({"status": "error", "error": str(exc), "message": str(exc)})

    def get_job(self, job_id: str) -> dict:
        """Return current status of a load job (raises KeyError if unknown)."""
        with self._jobs_lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return dict(self._jobs[job_id])

    def load(self, path: str, fmt: str) -> DatasetEntry:
        """Open a dataset via armoor.viewer.bridge and register it.

        Parameters
        ----------
        path:
            File-system path (or glob) to the dataset.
        fmt:
            Format string understood by armoor (e.g. ``"zarr"``,
            ``"cmems_model"``).

        Returns
        -------
        DatasetEntry
            The freshly registered entry (includes the generated UUID).
        """
        from armoor.viewer.bridge.loader import open_dataset

        ds = open_dataset(path, fmt)
        entry = _build_entry(path, fmt, ds)
        with self._lock:
            self._store[entry.id] = entry
        return entry

    def get(self, dataset_id: str) -> DatasetEntry:
        """Return the entry for *dataset_id* or raise KeyError."""
        with self._lock:
            if dataset_id not in self._store:
                raise KeyError(f"Dataset not found: {dataset_id}")
            return self._store[dataset_id]

    def update(self, dataset_id: str, ds: xr.Dataset) -> DatasetEntry:
        """Replace the xr.Dataset in an existing entry (after an operation).

        The metadata is re-extracted from the new dataset.

        Parameters
        ----------
        dataset_id:
            ID of the entry to update.
        ds:
            New dataset to attach.
        """
        old = self.get(dataset_id)
        new_entry = _build_entry(old.path, old.fmt, ds, existing_id=dataset_id)
        with self._lock:
            self._store[dataset_id] = new_entry
        return new_entry

    def close(self, dataset_id: str) -> None:
        """Remove a dataset from the registry and close it."""
        with self._lock:
            entry = self._store.pop(dataset_id, None)
        if entry is not None:
            try:
                entry.ds.close()
            except Exception as exc:  # nosec B110
                logger.debug("Could not close dataset %s: %s", dataset_id, exc)

    def list_ids(self) -> List[str]:
        """Return list of all registered dataset IDs."""
        with self._lock:
            return list(self._store.keys())

    def list_entries(self) -> List[DatasetEntry]:
        """Return list of all DatasetEntry objects."""
        with self._lock:
            return list(self._store.values())


# ---------------------------------------------------------------------------
# Module-level singleton used by Flask blueprints
# ---------------------------------------------------------------------------

store = DatasetStore()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_entry(
    path: str,
    fmt: str,
    ds: xr.Dataset,
    existing_id: Optional[str] = None,
) -> DatasetEntry:
    """Extract metadata from *ds* and return a populated DatasetEntry."""
    entry_id = existing_id or str(uuid.uuid4())

    # Data variables (exclude coords)
    variables = list(ds.data_vars)

    # Time axis
    time_values: List[str] = []
    time_dim = _find_dim(ds, ("time",))
    if time_dim and time_dim in ds.coords:
        try:
            times = ds[time_dim].values
            time_values = [str(np.datetime_as_string(t, unit="s")) for t in times]
        except Exception:
            time_values = [str(t) for t in ds[time_dim].values]

    # Depth / vertical axis
    depth_values: List[float] = []
    depth_dim = _find_dim(ds, ("z", "depth", "deptht", "level"))
    if depth_dim:
        if depth_dim in ds.coords:
            try:
                depth_values = [float(v) for v in ds[depth_dim].values]
            except Exception:
                depth_values = list(range(ds.sizes.get(depth_dim, 1)))
        elif depth_dim in ds.dims:
            depth_values = list(range(ds.sizes.get(depth_dim, 1)))

    # Lon / lat ranges
    lon_range: Optional[List[float]] = None
    lat_range: Optional[List[float]] = None

    lon_dim = _find_dim(ds, ("lon", "longitude", "x", "nav_lon"))
    lat_dim = _find_dim(ds, ("lat", "latitude", "y", "nav_lat"))

    if lon_dim and lon_dim in ds.coords:
        try:
            lons = ds[lon_dim].values.ravel()
            lon_range = [float(lons.min()), float(lons.max())]
        except Exception as exc:  # nosec B110
            logger.warning("Could not compute lon range: %s", exc)

    if lat_dim and lat_dim in ds.coords:
        try:
            lats = ds[lat_dim].values.ravel()
            lat_range = [float(lats.min()), float(lats.max())]
        except Exception as exc:  # nosec B110
            logger.warning("Could not compute lat range: %s", exc)

    dims = {str(k): int(v) for k, v in ds.sizes.items()}

    return DatasetEntry(
        id=entry_id,
        path=path,
        fmt=fmt,
        ds=ds,
        variables=variables,
        time_values=time_values,
        depth_values=depth_values,
        lon_range=lon_range,
        lat_range=lat_range,
        dims=dims,
    )


def _find_dim(ds: xr.Dataset, candidates: tuple) -> Optional[str]:
    """Return the first candidate name that appears in ds.dims or ds.coords."""
    for name in candidates:
        if name in ds.dims or name in ds.coords:
            return name
    return None
