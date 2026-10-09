import gc
import itertools
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Any, Tuple

import dask
import pandas as pd
import xarray as xr
from collections import defaultdict

from armoor import ArmoorError
from armoor.io import get_zarr_encoding, sort_ncs_by_suffix, write_dataset_to_zarr
from armoor.comp import GROUP_SUFFIX
from armoor.comp.comparison import get_comparison
from armoor.comp.stats import StatsComp
from armoor.data.load import StagedDataset
import armoor  # noqa: F401 — registers all xarray accessors
from armoor.diags.parcels import Parcels

logger = logging.getLogger(__name__)

DATA_TYPES = ("prod", "ref", "comp")
EPOCH = "1950-01-01"

# Re-exported for backward compatibility (still imported directly by tests).
_DRIFTER_OTYPE_REMAP = get_comparison("comp_drifter").otype_remap


def _compute_oceanvars(ds, func_comp):
    """Compute derived oceanographic variables on a colocated dataset.

    Derived variables (pdens, sndspeed, temp-from-ptemp, …) are computed
    here rather than during colocation so that the expensive gsw calls
    run on the small colocated data, not the full product grid.

    Parameters
    ----------
    ds : xarray.Dataset
        Colocated dataset to augment in place.
    func_comp : str
        Comparison type identifier (e.g. ``"comp_sst"``).

    Returns
    -------
    xarray.Dataset
        `ds`, with any missing comparison variables added where derivable.
    """
    return get_comparison(func_comp).compute_oceanvars(ds)


def check_output(func_name, outputs):
    """Validate that every requested output type is implemented.

    Parameters
    ----------
    func_name : str
        Comparison type identifier (e.g. ``"comp_sst"``).
    outputs : dict
        Mapping of output name to output configuration.

    Returns
    -------
    dict
        `outputs`, unchanged (or with ``"otype"`` remapped for comp_drifter).

    Raises
    ------
    ArmoorError
        If an output's ``"otype"`` is not implemented for `func_name`.
    """
    return get_comparison(func_name).check_output(outputs)


def _convert_time_to_epoch_seconds(ds, epoch=EPOCH):
    """Convert dataset time coordinates to seconds since epoch."""
    return [
        (pd.to_datetime(time) - pd.to_datetime(epoch)) / pd.to_timedelta("1s")
        for time in ds.time.values
    ]


def _prepare_prod_for_parcels(zprod):
    """Read production zarr, convert time to epoch seconds, write as netcdf."""
    ncprod = str(zprod).replace(".zarr", ".nc")
    with xr.open_dataset(zprod) as dsprod:
        if "z" in dsprod.sizes:
            dsprod = dsprod.squeeze(dim="z")
        dsprod = dsprod.drop("depth")
        dsprod = dsprod[["u", "v"]]
        timeprod = _convert_time_to_epoch_seconds(dsprod)
        dsprod["time"] = xr.DataArray(
            timeprod,
            dims=dsprod.time.dims,
            attrs={
                'dtype': 'float64',
                'units': f'seconds since {EPOCH} 00:00:00',
            },
        )
        dsprod.to_netcdf(ncprod)
    return ncprod, timeprod


def _interpolate_ref_and_run_parcels(zref, odt, timeprod, ncprod, runtime):
    """Interpolate reference dataset and execute Parcels simulation."""
    with xr.open_dataset(zref) as dsref:
        dsref_update = dsref.reset_coords(["lon", "lat"]).drop("depth").interp.tfreq(odt)
    zref = str(zref)
    dsref_update = dsref_update.compute()
    write_dataset_to_zarr(
        dsref_update, zref.replace(".zarr", "_tmp.zarr"), mode="w", consolidated=True, compute=True
    )
    timeref = [
        float((pd.to_datetime(time) - pd.to_datetime(EPOCH)) / pd.to_timedelta("1s")) - timeprod[0]
        for time in dsref_update.time.values
    ]
    ptc_coords_start = {
        "time": timeref,
        "lon": dsref_update.lon.values,
        "lat": dsref_update.lat.values,
    }
    if runtime:
        rruntime = pd.to_timedelta(runtime) / pd.to_timedelta("1s")
    else:
        rruntime = (dsref_update.time.max() - dsref_update.time.min()) / pd.to_timedelta("1s")
    rruntime = float(rruntime)
    del dsref_update
    Parcels(
        ncprod,
        ptc_coords_start,
        rruntime,
        outputdt=odt,
    ).execute()
    return zref


def _rewrite_prod_as_zarr(ncprod, zprod):
    """Remove old prod zarr, rewrite from parcels netcdf output."""
    shutil.rmtree(zprod)
    with xr.open_dataset(ncprod) as dsprod:
        write_dataset_to_zarr(dsprod, zprod, mode="w", consolidated=True, compute=True)


def preproc_comp_drifter(zins, odt, runtime=None):
    """Run the OceanParcels simulation for every colocated drifter/product pair.

    Parameters
    ----------
    zins : dict
        ``{drifter_name: {prod_name: [ref_zarr, prod_zarr]}}`` as produced
        by colocation.
    odt : timedelta or str
        Output timestep for the particle-tracking simulation.
    runtime : timedelta or str, optional
        Simulation runtime; defaults to the product's own time span.

    Returns
    -------
    dict
        `zins`, updated in place, with each product's zarr pair replaced
        by ``[simulated_ref_zarr, rewritten_prod_zarr]``.
    """
    logger.info("Preproc comp_drifter")
    for drifter, prods in zins.items():
        logger.info(drifter)
        for prod, zs in prods.items():
            logger.info(f"Prod: {prod}")
            # "ref"/"prod" is always the filename prefix (`save_datasets`),
            # but the "_<suffix>" part is only appended when a time/vlevel/
            # vrange attr was actually set -- comp_drifter's colocation has
            # no "time" key and no vrange attr, so the plain "ref.zarr"/
            # "prod.zarr" names have no underscore to match on.
            zref = [z for z in zs if Path(z).name.startswith("ref")][0]
            zprod = [z for z in zs if Path(z).name.startswith("prod")][0]
            ncprod, timeprod = _prepare_prod_for_parcels(zprod)
            zref = _interpolate_ref_and_run_parcels(zref, odt, timeprod, ncprod, runtime)
            _rewrite_prod_as_zarr(ncprod, zprod)
            zins[drifter].update({prod: [zref, zprod]})
    return zins


def preproc_comp(func_comp, ncs, **kwargs):
    """Preprocess loaded inputs before output computation.

    Parameters
    ----------
    func_comp : str
        Comparison type identifier (e.g. ``"comp_drifter"``).
    ncs : list of str
        Paths to the loaded/colocated input files.
    **kwargs
        Comparison-specific extra arguments (e.g. ``freq_drift``).

    Returns
    -------
    None or object
        See `armoor.comp.comparison.Comparison.preproc`.
    """
    return get_comparison(func_comp).preproc(ncs, **kwargs)


def concat_then_merge(datasets, dim="time"):
    """
    Merge and concatenate a list of heterogeneous xarray datasets.

    This function is designed for datasets that may contain variables
    with different dimension structures (e.g., (time, z, member) and
    (time, member)). It ensures a safe combination by:

    1. Grouping datasets by the dimensional structure of their variables
    2. Concatenating datasets within each homogeneous group along a given dimension
    3. Merging the resulting grouped datasets into a single Dataset

    Parameters
    ----------
    datasets : list of xr.Dataset
        List of xarray datasets to be combined. Each dataset may contain
        variables with different dimensionalities.
    dim : str, optional
        Dimension along which to concatenate datasets (default is "time").

    Returns
    -------
    xr.Dataset
        A single merged dataset containing all variables concatenated
        along the specified dimension where applicable.

    Notes
    -----
    - Variables sharing the same dimensional structure are concatenated
      together.
    - Variables with different dimensions are handled in separate groups
      and merged afterward. Groups whose length along `dim` doesn't match
      the dominant group (e.g. mld vs. vertical-range-split ptemp/sal) get
      their dim/coord names suffixed with `GROUP_SUFFIX` so they still
      merge in without a bogus label alignment or being dropped.
    - This is particularly useful for oceanographic or atmospheric datasets
      with mixed 2D/3D variables.

    """

    groups = defaultdict(list)

    for ds in datasets:
        signature = tuple(sorted(frozenset(ds[var].dims) for var in ds.data_vars))
        groups[signature].append(ds)

    concat_groups = [xr.concat(dss, dim=dim, combine_attrs="override") for dss in groups.values()]

    if len(concat_groups) > 1:
        # Variables with a dims signature that doesn't include the vertical
        # ranging axis (e.g. mld, which has no "z" dim) only get one
        # sub-dataset per real time step, while variables split per
        # vertical-range bin (e.g. ptemp, sal) get one per bin -- all
        # sharing the same timestamp. Their concatenated groups then have
        # mismatched lengths along `dim` with duplicate coordinate values,
        # which xr.merge cannot align by label. Rather than dropping the
        # minor group(s) (which would silently lose e.g. mld from every
        # plot/output built on this otype), give them private dim/coord
        # names so every variable survives the merge; diagdisp() and
        # friends only care about raw values, not dim/coord names.
        max_len = max(cg.sizes[dim] for cg in concat_groups)
        dominant = [cg for cg in concat_groups if cg.sizes[dim] == max_len]
        minor = [cg for cg in concat_groups if cg.sizes[dim] != max_len]
        shared_names = set().union(*(set(cg.dims) | set(cg.variables) for cg in dominant))
        renamed_minor = []
        for i, cg in enumerate(minor):
            overlap = shared_names & (set(cg.dims) | set(cg.variables))
            if overlap:
                logger.debug(
                    "concat_then_merge: renaming %s on group %s "
                    "(vars=%s) to avoid a '%s' cardinality mismatch",
                    sorted(overlap),
                    i,
                    list(cg.data_vars),
                    dim,
                )
                cg = cg.rename({name: f"{name}{GROUP_SUFFIX}{i}" for name in overlap})
            renamed_minor.append(cg)
        concat_groups = dominant + renamed_minor

    return xr.merge(concat_groups, combine_attrs="override")


class OutputProcessor:
    """
    A class to handle output processing with statistical comparisons between
    production and reference datasets.
    """

    def __init__(self, func_comp=None):
        """Initialize the OutputProcessor.

        Parameters
        ----------
        func_comp : str, optional
            Comparison type identifier (e.g. ``"comp_sst"``), used to look
            up the `Comparison` instance driving output/compatibility rules.
        """
        self.func_comp = func_comp
        self.comparison = get_comparison(func_comp)

    def process_output(self, ocfg: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
        """
        Process output configurations to generate statistical comparisons.

        This function processes production and reference datasets to generate
        statistical comparisons and save them in various output formats.

        Parameters
        ----------
        ocfg
            List containing [metazone_config, output_config] dictionaries

        Returns
        -------
        dict
            Dictionary mapping output types to metazones to list of output file paths.
            Structure: {output_name: {metazone_name: [file_path1, file_path2, ...]}}

        Raises
        ------
        ArmoorError
            When processing fails due to configuration or data issues

        Examples
        --------
        >>> ocfg = [
        ...     {'atlantic': {'ncins': {'ref1': {'prod1': ['file1.nc']}}}},
        ...     {'comparison': {'otype': 'stats_comp'}}
        ... ]
        >>> processor = OutputProcessor()
        >>> result = processor.process_output(ocfg, 'validation')
        >>> print(result)
        {'stats_comp': {'atlantic': ['validation/output/atlantic/ref1/stats_comp/all.zarr']}}
        """
        # Extract configuration components
        config = self._parse_configuration(ocfg)
        metazone, output, mparams, oparams = config

        logger.info(f"{metazone} -- {output}")

        # Validate output compatibility
        if not self._validate_output_compatibility(oparams, mparams, metazone, output):
            return {output: {metazone: []}}

        # Get output parameters and initialize result structure
        output_params = self.comparison.outputs_params[output]
        ncouts = {output: {metazone: []}}
        ref_ncins = mparams.get("ncins")

        # Process each reference dataset
        for ref_name, prods in ref_ncins.items():
            logger.info(f"Process {output} for {ref_name}")

            # Sort and organize input files
            sorted_prods = self._sort_products(prods, output_params)

            # Generate statistics and comparisons
            processed_datasets = self._generate_statistics_and_comparisons(
                sorted_prods, mparams, output_params, output
            )
            # Save outputs
            staged = StagedDataset("", metazone=metazone, comp_func=self.func_comp, stage="output")
            output_files = self._save_outputs(
                processed_datasets, sorted_prods, staged, ref_name, output, output_params
            )

            ncouts[output][metazone].extend(output_files)

            # Cleanup
            del processed_datasets
            gc.collect()
        return ncouts

    def _parse_configuration(
        self, ocfg: List[Dict[str, Any]]
    ) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """
        Parse and extract configuration components.

        Parameters
        ----------
        ocfg
            Configuration list containing metazone and output configs

        Returns
        -------
        Tuple of (metazone_name, output_name, metazone_params, output_params)
        """
        metazone = next(iter(ocfg[0]))
        output_key = next(iter(ocfg[1]))

        mparams = ocfg[0][metazone]
        oparams = ocfg[1][output_key]
        output = oparams.get("otype")

        return metazone, output, mparams, oparams

    def _validate_output_compatibility(
        self, oparams: Dict[str, Any], mparams: Dict[str, Any], metazone: str, output: str
    ) -> bool:
        """
        Validate if output type is compatible with metazone parameters.

        Parameters
        ----------
        oparams
            Output parameters
        mparams
            Metazone parameters
        metazone
            Metazone name
        output
            Output type name

        Returns
        -------
        True if compatible, False otherwise
        """
        return self.comparison.validate_output_compatibility(oparams, mparams, metazone, output)

    def _sort_products(
        self, prods: Dict[str, Dict[str, List]], output_params: Dict[str, Any]
    ) -> Dict[str, Dict[str, Dict]]:
        """
        Sort and organize product files by type (prod/ref) and sorting criteria.

        Parameters
        ----------
        prods
            Dictionary mapping product names to their file lists
        output_params
            Output configuration parameters

        Returns
        -------
        Dictionary with sorted products organized by type
        """
        logger.info("Sorting products")
        sorted_prods = {}
        sort_dim = output_params.get("sort")

        for prod_name, ncins in prods.items():
            logger.info(f"Sorting {prod_name}")
            sorted_prods[prod_name] = {}

            for file_type in ["prod", "ref"]:
                # Filter files by type (prod or ref), matching the
                # "ref[_<suffix>].zarr"/"prod[_<suffix>].zarr" filename
                # convention itself (the suffix is empty for an untagged
                # signature group, e.g. hydrosection's "mld" -- see
                # armoor.comp.coloc.save_datasets), not a substring check
                # anywhere in the path -- a metazone name containing "ref"
                # (e.g. "modelzone_href") would otherwise match every file
                # under it, misclassifying every product as a second
                # reference (same bug class already fixed in coloc.py).
                type_files = [nc for nc in ncins if Path(str(nc)).name.startswith(file_type)]

                # Sort files by the specified dimension
                sorted_files = sort_ncs_by_suffix(type_files, sort_dim=sort_dim)
                sorted_prods[prod_name][file_type] = sorted_files

        return sorted_prods

    def _generate_statistics_and_comparisons(
        self,
        sorted_prods: Dict[str, Dict],
        mparams: Dict[str, Any],
        output_params: Dict[str, Any],
        output,
    ) -> Dict[str, Dict]:
        """
        Generate statistics and comparisons for all products.

        Parameters
        ----------
        sorted_prods
            Sorted product files organized by type
        mparams
            Metazone parameters
        output_params
            Output configuration parameters

        Returns
        -------
        Dictionary containing processed datasets organized by product and data type
        """
        logger.info("Computing statistics & concatenations")

        dss = {}
        concat_dim = output_params.get("concat")

        for prod_name in sorted_prods.keys():
            logger.info(f"Processing {prod_name}")
            dss[prod_name] = {dt: {} for dt in DATA_TYPES}

            # Process each sorting group
            sort_keys = sorted_prods[prod_name]["prod"].keys()
            for sort_key in sort_keys:
                # Generate statistics for this sorting group
                stats_data = self._compute_statistics_for_sort_group(
                    sorted_prods[prod_name], sort_key, mparams, output_params, output
                )
                # Concatenate datasets for each data type
                for data_type in DATA_TYPES:
                    concatenated_data = self._concatenate_datasets(
                        stats_data[data_type], concat_dim, output
                    )
                    dss[prod_name][data_type][sort_key] = concatenated_data

        return dss

    def _compute_statistics_for_sort_group(
        self,
        prod_files: Dict[str, Dict],
        sort_key: str,
        mparams: Dict[str, Any],
        output_params: Dict[str, Any],
        output,
    ) -> Dict[str, List]:
        """
        Compute statistics for a specific sorting group.

        Parameters
        ----------
        prod_files
            Product files organized by type (prod/ref)
        sort_key
            Sorting key identifier
        mparams
            Metazone parameters
        output_params
            Output parameters
        output
            Output type name (``otype``), forwarded to
            `Comparison.compute_comparison` for comparison types that
            override the generic statistics (e.g. comp_drifter).

        Returns
        -------
        Dictionary containing lists of computed statistics for each data type
        """
        prod_files_list = prod_files["prod"][sort_key]
        ref_files_list = prod_files["ref"][sort_key]
        num_files = len(prod_files_list)

        # Initialize storage for computed data trees
        computed_data = {data_type: [] for data_type in DATA_TYPES}

        # Open all files upfront to avoid repeated open/close overhead
        prod_datasets = []
        ref_datasets = []
        try:
            prod_datasets = [xr.open_dataset(f) for f in prod_files_list]
            ref_datasets = [xr.open_dataset(f) for f in ref_files_list]

            # Process each file pair
            for file_idx in range(num_files):
                ds_prod = prod_datasets[file_idx]
                ds_ref = ref_datasets[file_idx]
                # Colocation runs once per metazone and is shared by every
                # otype, so a sort_key bucket here can also hold the
                # mld-only file (no "z", split apart upstream by dims
                # signature) alongside the real vertical-profile file --
                # uvprofiles/udiagts only plot the latter, and mixing the
                # two would misalign the "data"/"closest" bin lists below.
                if output in ("uvprofiles", "udiagts") and "z" not in ds_ref.dims:
                    continue

                # uvprofiles/udiagts need one entry per real profile, but
                # colocation runs once per metazone (shared by every
                # otype) so it cannot itself guarantee that: a trange bin
                # can bundle several distinct observation times into the
                # same coloc file. Split those apart here, scoped to just
                # these two otypes, instead of hardening the shared coloc
                # stage for everyone.
                if output in ("uvprofiles", "udiagts") and ds_ref.sizes.get("time", 1) > 1:
                    pairs = [
                        (ds_prod.isel(time=[it]), ds_ref.isel(time=[it]))
                        for it in range(ds_ref.sizes["time"])
                    ]
                else:
                    pairs = [(ds_prod, ds_ref)]

                for ds_prod_i, ds_ref_i in pairs:
                    self._process_coloc_pair(
                        ds_prod_i,
                        ds_ref_i,
                        mparams,
                        output_params,
                        output,
                        computed_data,
                    )
        finally:
            # Close all files at end
            for ds in prod_datasets + ref_datasets:
                ds.close()

        return computed_data

    def _process_coloc_pair(self, ds_prod, ds_ref, mparams, output_params, output, computed_data):
        """Compute stats (and, for uvprofiles/udiagts, the closest-member
        profile) for a single ref/prod pair, appending results in place to
        `computed_data`.
        """
        # Set depth/pres as coordinate if needed
        for vcoord in ["depth", "pres"]:
            if vcoord in ds_ref.data_vars:
                ds_ref = ds_ref.set_coords(vcoord)
            if vcoord in ds_prod.data_vars:
                ds_prod = ds_prod.set_coords(vcoord)

        # Resolve the nearest model member to the reference location once,
        # before StatsComp's own member-mean reduction -- only uvprofiles/
        # udiagts read a single representative profile instead of the
        # ensemble mean/std.
        closest_ds = None
        if (
            output in ("uvprofiles", "udiagts")
            and "member" in ds_prod.dims
            and "depth" in ds_prod.variables
        ):
            # Colocation runs once per metazone and is shared by every
            # otype, so a sort_key bucket here can also hold the mld-only
            # file (no "z"/"depth", split apart upstream by dims signature)
            # alongside the real vertical-profile file -- skip it, same as
            # plot.py later skips mld for lacking a "depth" coord.
            ds_closest = ds_prod
            if "member" in ds_closest.depth.dims:
                ds_closest = ds_closest.reset_coords("depth")
            closest_ds = ds_closest.filters.sel_closest(ds_ref)

        # Prepare statistics configuration
        stats = output_params.get("stat").copy() if output_params.get("stat") else None
        # Compute statistics and comparisons
        dt_prod, dt_ref, dt_comps = StatsComp(mparams, ds_prod, ds_ref, stats).compute()
        dt_comps = self.comparison.compute_comparison(dt_comps, ds_ref, ds_prod, output)
        if closest_ds is not None:
            dt_prod.update(xr.DataTree.from_dict({"closest": closest_ds}))

        # Store results
        computed_data["prod"].append(dt_prod)
        computed_data["ref"].append(dt_ref)
        computed_data["comp"].append(dt_comps)

    def _concatenate_datasets(
        self, data_trees: List[Any], concat_dim: List[str], output: str = None
    ) -> Dict[str, xr.Dataset]:
        """
        Concatenate datasets from data trees along specified dimensions.

        Parameters
        ----------
        data_trees
            List of data trees to concatenate
        concat_dim
            Dimensions to concatenate along
        output
            Output type name (otype). Only "uvprofiles"/"udiagts" are
            allowed to keep several unfused datasets per sort_key (see
            below) -- for every other otype a cardinality mismatch here
            is still a hard error.

        Returns
        -------
        Dictionary of concatenated datasets
        """
        concatenated_data = {}

        # Filter out None entries (e.g. from _drifter for map outputs)
        data_trees = [dt for dt in data_trees if dt is not None]
        if not data_trees:
            return concatenated_data

        # Process each dataset in the data trees
        for ds_name in data_trees[0].keys():
            datasets = [dt[ds_name].to_dataset() for dt in data_trees]

            if concat_dim == ["time"]:
                concatenated_dataset = self._concatenate_time_datasets(datasets)
            elif len(datasets) == 1:
                concatenated_dataset = datasets[0]
            elif output in ("uvprofiles", "udiagts", "sections"):
                # No fusion requested: keep one dataset per dims-signature
                # group sharing this sort_key (e.g. sections always splits
                # a "mld"-only group -- no "z" dim -- from the depth-
                # resolved ptemp/sal/... group) instead of merging them
                # into a single object along a fake "time" axis.
                # `_save_combined_output`/`_save_separate_outputs` fan this
                # list out into numbered children of `ds_name`.
                concatenated_dataset = datasets
            else:
                logger.info("Concatenation request: %s datasets: %s", len(datasets), datasets)
                raise ArmoorError("Multi-dataset concatenation not implemented")

            concatenated_data[ds_name] = concatenated_dataset

        return concatenated_data

    def _concatenate_time_datasets(self, datasets: List[xr.Dataset]) -> xr.Dataset:
        """
        Concatenate datasets along the time dimension.

        Parameters
        ----------
        datasets
            List of datasets to concatenate

        Returns
        -------
        Concatenated dataset
        """
        # Handle multi-time datasets by splitting into individual time slices
        if any(ds.sizes["time"] > 1 for ds in datasets):
            time_slices = []
            for ds in datasets:
                time_slices.extend(
                    [ds.isel(time=[time_idx]) for time_idx in range(ds.sizes["time"])]
                )
            datasets = time_slices

        # Concatenate along time dimension
        concatenated = concat_then_merge(datasets)

        # Preserve vrange attributes if present in any dataset -- de-duplicate
        # first: concatenating many single-time slices of the same vrange
        # bin (e.g. uvprofiles/udiagts's "concat": ["time"]) would otherwise
        # repeat the same value once per slice. Compare by equality (not a
        # set/dict) since vrange_value may itself be an unhashable list.
        vrange_attrs = [ds.range.vrange_value for ds in datasets if ds.range.vrange_value]
        if vrange_attrs:
            deduped = []
            for v in vrange_attrs:
                if v not in deduped:
                    deduped.append(v)
            concatenated.attrs["vrange"] = deduped

        return concatenated

    def _save_outputs(
        self,
        processed_datasets: Dict[str, Dict],
        sorted_prods: Dict[str, Dict],
        staged: StagedDataset,
        ref_name: str,
        output: str,
        output_params: Dict[str, Any],
    ) -> List[str]:
        """
        Save processed datasets to output files.

        Parameters
        ----------
        processed_datasets
            Processed datasets organized by product and type
        sorted_prods
            Sorted product information
        staged
            Pipeline context (comp_func/metazone) for this output run
        ref_name
            Reference dataset name
        output
            Output type name
        output_params
            Output configuration parameters

        Returns
        -------
        List of saved output file paths
        """
        output_files = []

        # Create base output directory
        dirout = staged.output_dir("output", ref_name=ref_name, output=output)

        # Get all sorting keys
        sort_keys = list(sorted_prods[list(sorted_prods.keys())[0]]["prod"].keys())

        # Save outputs for each sorting group
        for sort_key in sort_keys:
            sort_dir = dirout / sort_key
            sort_dir.mkdir(parents=True, exist_ok=True)

            if output_params.get("output"):
                # Save all products in a single file
                output_file = self._save_combined_output(
                    processed_datasets, sort_key, sort_dir, sorted_prods
                )
                output_files.append(str(output_file))
            else:
                # Save each product separately
                separate_files = self._save_separate_outputs(
                    processed_datasets, sort_key, sort_dir, sorted_prods
                )
                output_files.extend([str(f) for f in separate_files])

        return output_files

    def _save_combined_output(
        self,
        processed_datasets: Dict[str, Dict],
        sort_key: str,
        sort_dir: Path,
        sorted_prods: Dict[str, Dict],
    ) -> Path:
        """
        Save all products in a combined output file.

        Parameters
        ----------
        processed_datasets
            Processed datasets
        sort_key
            Sorting key
        sort_dir
            Output directory for this sort group
        sorted_prods
            Sorted product information

        Returns
        -------
        Path to saved combined file
        """
        dt = xr.DataTree()

        for prod_name in sorted_prods.keys():
            # Create product node in data tree
            dt.update(xr.DataTree.from_dict({prod_name: xr.DataTree()}))

            # Add data for each type (prod, ref, comp)
            for data_type in DATA_TYPES:
                datasets = processed_datasets[prod_name][data_type][sort_key]
                # A ds_name maps to a list, rather than a single dataset,
                # when `_concatenate_datasets` left several vrange-bin
                # datasets unfused (no "concat" configured for this
                # otype) -- fan those out into numbered children instead.
                tree_dict = {}
                for ds_name, ds_or_list in datasets.items():
                    if isinstance(ds_or_list, list):
                        for i, ds in enumerate(ds_or_list):
                            tree_dict[f"{ds_name}/{i}"] = ds
                    else:
                        tree_dict[ds_name] = ds_or_list
                data_tree = xr.DataTree.from_dict(tree_dict)
                dt[prod_name].update(xr.DataTree.from_dict({data_type: data_tree}))

        # Save combined file
        output_file = sort_dir / "all.zarr"
        encoding = get_zarr_encoding(dt)
        dt.to_zarr(output_file, mode="w", encoding=encoding)
        logger.info(f"{output_file} saved")
        return output_file

    def _save_separate_outputs(
        self,
        processed_datasets: Dict[str, Dict],
        sort_key: str,
        sort_dir: Path,
        sorted_prods: Dict[str, Dict],
    ) -> List[Path]:
        """
        Save each product in a separate output file.

        Parameters
        ----------
        processed_datasets
            Processed datasets
        sort_key
            Sorting key
        sort_dir
            Output directory for this sort group
        sorted_prods
            Sorted product information

        Returns
        -------
        List of paths to saved files
        """
        output_files = []

        for prod_name in sorted_prods.keys():
            dt = xr.DataTree()

            # Create product node in data tree
            dt.update(xr.DataTree.from_dict({prod_name: xr.DataTree()}))

            # Add data for each type (prod, ref, comp)
            for data_type in DATA_TYPES:
                datasets = processed_datasets[prod_name][data_type][sort_key]
                if datasets:
                    data_tree = xr.DataTree.from_dict(datasets)
                    dt[prod_name].update(xr.DataTree.from_dict({data_type: data_tree}))

            # Save product file
            output_file = sort_dir / f"{prod_name}.zarr"
            encoding = get_zarr_encoding(dt)
            dt.to_zarr(output_file, mode="w", encoding=encoding)
            output_files.append(output_file)
            logger.info(f"{output_file} saved")

        return output_files


class OutputPipelineManager:
    """
    Manager class for handling the complete output processing pipeline with parallelization.
    """

    def __init__(self, func_comp=None):
        """Initialize the OutputPipelineManager.

        Parameters
        ----------
        func_comp : str, optional
            Comparison type identifier (e.g. ``"comp_sst"``), used to look
            up the `Comparison` instance driving output/preproc rules.
        """
        self.processor = OutputProcessor(func_comp=func_comp)
        self.func_comp = func_comp
        self.comparison = get_comparison(func_comp)

    def process_and_extract(
        self, output_config: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Process output configuration and extract non-empty results.

        This method is designed to be used with Dask for parallel processing.

        Parameters
        ----------
        output_config
            Output configuration

        Returns
        -------
        Dictionary with only non-empty results
        """
        # Process the output
        results = self.processor.process_output(output_config)

        # Filter out empty results
        filtered_results = {}
        for output_name, metazones in results.items():
            for metazone_name, file_paths in metazones.items():
                if len(file_paths) > 0:
                    if output_name not in filtered_results:
                        filtered_results[output_name] = {}
                    filtered_results[output_name][metazone_name] = file_paths

        return filtered_results

    def process_all_outputs(
        self, ncs: Dict[str, Any], metazones_in: Dict[str, Any], outputs: Dict[str, Any], **kwargs
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Process all output configurations with parallel execution.

        Parameters
        ----------
        ncs
            NetCDF files organized by metazone
        metazones_in
            Input metazone configurations
        outputs
            Output configurations

        Returns
        -------
        Dictionary mapping output types to metazones to file paths

        Examples
        --------
        >>> manager = OutputPipelineManager()
        >>> ncs = {'atlantic': {'ref1': {'prod1': ['file1.nc']}}}
        >>> metazones = {'atlantic': {'param1': 'value1'}}
        >>> outputs = {'comparison': {'otype': 'stats_comp'}}
        >>> result = manager.process_all_outputs(ncs, metazones, outputs, 'validation')
        """
        # Prepare configurations
        output_configs = self._prepare_output_configurations(ncs, metazones_in, outputs, **kwargs)
        # Create delayed tasks for parallel processing
        delayed_tasks = [
            dask.delayed(self.process_and_extract)(config) for config in output_configs
        ]

        # Execute all tasks in parallel
        results = dask.compute(*delayed_tasks)

        # Merge all results
        results = self._merge_results(results)
        return results

    def _prepare_output_configurations(
        self, ncs: Dict[str, Any], metazones_in: Dict[str, Any], outputs: Dict[str, Any], **kwargs
    ) -> List[List[Dict[str, Any]]]:
        """
        Prepare output configurations for processing.

        Parameters
        ----------
        ncs
            NetCDF files organized by metazone
        metazones_in
            Input metazone configurations
        outputs
            Output configurations

        Returns
        -------
        List of output configurations ready for processing
        """
        # Remove format specification and validate outputs
        output_configs = outputs.copy()
        output_configs.pop("fmt", None)
        output_configs = self.comparison.check_output(output_configs)
        preproc = self.comparison.outputs_params.get("preproc")
        # Prepare metazone configurations
        prepared_metazones = {}
        for metazone_name, metazone_config in metazones_in.items():
            if metazone_config:
                ncins = ncs.get(metazone_name)
                if not ncins:
                    # No colocation output for this metazone at all (e.g. no
                    # drifter/mooring/argo profile actually fell inside it
                    # for the requested period) -- skip it instead of
                    # crashing deep inside preproc() on a None ncins.
                    logger.warning(f"No colocated input for metazone '{metazone_name}', skipping")
                    continue
                if preproc:
                    self.comparison.preproc(ncins, **kwargs)
                prepared_metazones[metazone_name] = {
                    "ncins": ncins,
                    "vars": self.comparison.comp_vars,
                    **metazone_config.copy(),
                }

        # Convert to list format expected by the processor
        metazone_list = [{key: value} for key, value in prepared_metazones.items()]
        output_list = [{key: value} for key, value in output_configs.items()]

        # Create all combinations of metazones and outputs
        output_combinations = list(itertools.product(metazone_list, output_list))

        return output_combinations

    def _merge_results(
        self, results: List[Dict[str, Dict[str, List[str]]]]
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Merge results from parallel processing.

        Parameters
        ----------
        results
            List of result dictionaries from parallel tasks

        Returns
        -------
        Merged results dictionary
        """
        merged_results = {}

        for result in results:
            for output_name, metazones in result.items():
                if output_name not in merged_results:
                    merged_results[output_name] = {}
                for mz_name, file_paths in metazones.items():
                    if mz_name in merged_results[output_name]:
                        merged_results[output_name][mz_name].extend(file_paths)
                    else:
                        merged_results[output_name][mz_name] = file_paths

        return merged_results


def main_output(
    ncs: Dict[str, Any],
    metazones_in: Dict[str, Any],
    outputs: Dict[str, Any],
    func_comp: str,
    **kwargs,
) -> Dict[str, Dict[str, List[str]]]:
    """
    Main function for processing all output configurations with parallel execution.

    This function maintains backward compatibility while providing improved structure
    and parallel processing capabilities.

    Parameters
    ----------
    ncs
        Dictionary mapping metazone names to their NetCDF files
    metazones_in
        Dictionary of metazone configurations
    outputs
        Dictionary of output configurations (fmt key will be removed)
    func_comp
        Function component identifier for directory structure

    Returns
    -------
    Dictionary mapping output names to metazones to lists of output file paths.
    Structure
        {output_name: {metazone_name: [file_path1, file_path2, ...]}}

    Examples
    --------
    >>> ncs = {'atlantic': {'ref1': {'prod1': ['file1.nc', 'file2.nc']}}}
    >>> metazones = {'atlantic': {'param1': 'value1'}}
    >>> outputs = {'monthly_stats': {'otype': 'statistics'}, 'fmt': 'zarr'}
    >>> result = main_output(ncs, metazones, outputs, 'validation')
    >>> print(result)
    {'statistics': {'atlantic': ['validation/output/atlantic/ref1/statistics/file1.zarr']}}
    """
    manager = OutputPipelineManager(func_comp=func_comp)
    fouts = manager.process_all_outputs(ncs, metazones_in, outputs, **kwargs)
    return fouts
