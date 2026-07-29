:command:`armoor-comp-hydrosection`
===================================

Usage
-----

.. code-block:: bash

    armoor-comp-hydrosection METAZONES CFGFILE [OPTIONS]

.. rubric:: Example

.. code-block:: bash

    armoor-comp-hydrosection MANCHE,GASCOGNE comp_hydrosection.cfg \
        --tbound 2024-08-01 2024-08-31

``METAZONES``
    Comma-separated list of metazone names to process (must exist in
    ``metazones.cfg`` or the file given to ``-m``).

``CFGFILE``
    Path to the comparison configuration file (see :ref:`clicomp`).

Scope
-----

Covers gliders (``fmt=cmems_insitu, platform=glider``) -- a single glider
mission file holds several profiles at their own (time, lon, lat), i.e. a
whole hydrological section -- and ODAR-processed towed-CTD sections
(``fmt=odar``: seasoar today; scanfish/rapidcast/MVP need no new code, just
a bundled sample of their own to confirm against, since ``open_decode_odar``
dispatches purely by each file's own ``ODAR_DATASET_TYPE`` attr, not by
``platform=``). ODAR sections only carry raw conductivity, not salinity --
``sal`` is derived automatically via ``gsw.SP_from_C`` the first time it's
needed.

Geostrophic current normal to the section (an optional CCTP variable) is
computed via dynamic height (``gsw.geo_strf_dyn_height`` /
``gsw.geostrophic_velocity``), independently for the reference and the
product from their own colocated hydrography -- see ``--cgeo-ref`` below.

Colocation
----------

Unlike every other ``armoor-comp-*``, none of the colocation steps are user
configurable -- they are always:

- **Time**: nearest-to-reference (``trange_seq``, same as ``armoor-comp-argo``).
- **Horizontal**: the product is interpolated onto the reference's own
  moving track -- a pointwise (time, lon, lat)-paired interpolation, not a
  fixed cloud of points (see ``HorizontalColocation.track`` /
  ``armoor.base.interp.grid2track``).
- **Vertical**: the product is vinterp'd onto the reference's own
  per-profile depth levels (forced ``vrange``, like
  ``CompMooring``/``CompDrifter``'s depth-based forcing) -- this is what
  keeps the whole depth profile as a single continuous section instead of
  splitting it into per-level files.

Geostrophic current reference pressure (``--cgeo-ref``)
----------------------------------------------------------

``--cgeo-ref DBAR`` sets the reference sea pressure (dbar) for the
dynamic-height calculation, i.e. the depth at which the geostrophic
velocity is assumed to be zero. Defaults to 0 dbar (referenced to the sea
surface) when not given. This is a per-run CLI option, not a metazone.cfg
field.

Pipeline control
----------------

By default all four pipeline stages run in sequence:
*load → coloc → output → plot*.
Each flag short-circuits the pipeline after the named stage:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Flag
     - Effect
   * - ``--filters-only``
     - Stop after loading and filtering.  Zarr files are written to
       ``{comp_name}/metazones/{metazone}/{data}/``.
   * - ``--coloc-only``
     - Stop after colocation.  Zarr files are written to
       ``{comp_name}/coloc/{metazone}/{ref}/{data}/``.
   * - ``--no-plot``
     - Run load + coloc + output computation but skip the plot stage.
   * - ``--plot-only OTYPE``
     - Regenerate plots for a single output type from existing zarr files.
       Requires ``--input-json``.

data formats
------------

    - ``cmems_insitu`` with ``platform=glider``
    - ``odar`` (no ``platform=`` needed; the instrument type is read from
      each file's own ``ODAR_DATASET_TYPE`` attr)

outputs
-------

    - ``sections``: one PNG per comparison variable. Depth-resolved
      variables (``ptemp``, ``sal``, ``temp``, ``pdens``, ``sndspeed``,
      ``cgeo``) are rendered as distance-vs-depth ref/product/diff panels;
      2D variables (``mld``) as ref/product/diff line curves -- both
      against the reference's own cumulative along-track distance.
      ``cgeo`` (geostrophic current normal to the section) is plotted
      against the distance between each pair of consecutive stations
      instead of the stations themselves, since it's a between-station
      quantity by construction.

metazone parameters
--------------------

    - ``tbound``
    - ``polygon``
    - ``oceanvars``
    - ``bathy``

    .. note::
       Other given parameters are ignored -- in particular, ``vlevel``/
       ``vrange``/``href``/``radius``/``cloud`` do not apply: the vertical
       and horizontal colocation are always forced (see above).

.. argparse::
    :module: armoor.cli.main
    :func: get_parser_comp_hydrosection
    :prog: armoor-comp-hydrosection
    :nosubcommands:
