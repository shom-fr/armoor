.. _viewer:

Interactive Ocean Data Viewer
==============================

``armoor-viewer`` is an interactive web-based visualisation tool bundled with
armoor.  It serves an iTowns 3D globe with an offline Blue Marble basemap and
lets you explore any xarray/zarr ocean dataset directly in the browser —
no internet connection required.

.. contents:: Contents
   :local:
   :depth: 2


Quick start
-----------

.. code-block:: bash

   armoor-viewer                   # starts on http://127.0.0.1:5000
   armoor-viewer --port 8080       # custom port
   armoor-viewer --host 0.0.0.0    # listen on all interfaces

Open a browser at the printed URL, then use the **Dataset** panel to load a
Zarr store or any supported format.


Render mode: 2D vs 3D
----------------------

``armoor-viewer`` can display data on either an **iTowns 3D globe**
(default when supported) or a **Leaflet 2D planisphere**.  The 3D globe
requires **WebGL2** in the browser; the 2D mode needs nothing beyond plain
Canvas/DOM support and works on any machine, including headless HPC login
nodes whose graphics stack is a remote-management chip (e.g. ASPEED BMC) or
an old software Mesa/llvmpipe build capped below OpenGL ES 3.0.

Both modes expose the same features (dataset loading, scalar overlay,
point/time-series/section diagnostics, particle animation for currents) —
2D mode simply skips the globe rendering, since the underlying data and API
are identical.

**Selecting the mode**

By default the browser auto-detects WebGL2 support and picks 3D if
available, 2D otherwise.  This can be overridden in three ways, in order of
priority:

1. URL query parameter, for a single session: ``http://host:5000/?mode=2d``
2. The **2D / 3D toggle** in the sidebar header (persisted in the browser's
   ``localStorage``, applies to future visits from that browser).
3. The server's default, set for all users of a deployment:

   .. code-block:: bash

      armoor-viewer --render-mode 2d
      # or
      export ARMOOR_VIEWER_RENDER_MODE=2d
      armoor-viewer

   Useful when deploying on a compute node known to lack WebGL2 support
   (see *Deployment on an HPC cluster* below) — forcing ``2d`` avoids
   every user hitting the ``WebGL2 does not seem to be supported`` error
   individually.

When the 2D mode is active, the iTowns/Three.js bundles (~2.4 MB) are never
downloaded — only Leaflet (~150 KB) is loaded.


Basemap setup
-------------

The viewer ships without the Blue Marble image (it is ~30 MB and would bloat
the package).  Without it, ocean tiles render as a uniform dark background,
which is harmless but not very useful.

**Step 1 – download the image**

Download the NASA Blue Marble Next Generation (21600 × 10800 px, ~30 MB):

.. code-block:: bash

   mkdir -p ~/.local/share/armoor-viewer/img
   wget -O ~/.local/share/armoor-viewer/img/earth-blue-marble.jpg \
     "https://eoimages.gsfc.nasa.gov/images/imagerecords/73000/73909/world.topo.bathy.200412.3x21600x10800.jpg"

**Step 2 – pre-generate the tile pyramid** *(optional but recommended)*

Pre-generating tiles avoids on-the-fly cropping on the first request for each
zoom level.  Run this once after placing the image:

.. code-block:: bash

   python -c "
   from armoor.viewer.api.basemap import _globe_image, _crop_tile, _cache_put
   from armoor.viewer import config as cfg
   import math, io
   for z in range(1, 7):
       nx, ny = 2**(z+1), 2**z
       for x in range(nx):
           for y in range(ny):
               west  =  x      / nx * 360 - 180
               east  = (x + 1) / nx * 360 - 180
               north = 90 -  y      / ny * 180
               south = 90 - (y + 1) / ny * 180
               _cache_put(z, x, y, _crop_tile(west, south, east, north))
   print('done')
   "

Or use the helper script shipped with the armoor source tree:

.. code-block:: bash

   python tools/generate_tiles.py --max-zoom 6


Data directory
--------------

By default the viewer stores the Blue Marble image and the generated tile
cache in:

.. code-block:: text

   ~/.local/share/armoor-viewer/
   ├── img/
   │   └── earth-blue-marble.jpg
   └── tiles/
       └── geo/
           └── {z}/{x}/{y}.jpg     ← disk cache, auto-populated on first use

Override the location with the ``ARMOOR_VIEWER_DATA`` environment variable:

.. code-block:: bash

   export ARMOOR_VIEWER_DATA=/data/armoor-viewer
   armoor-viewer


User interface
--------------

The interface is split into a **3D globe** on the left and a collapsible
**sidebar** on the right.  A status bar at the bottom of the globe shows the
current operation.


Dataset panel
~~~~~~~~~~~~~

Enter the path to a dataset and choose the format, then click **Load**.
Opening large datasets (CROCO, NEMO, HYCOM …) is done asynchronously: the
server decodes the file in a background thread and the browser polls for
completion, showing progress messages in the status bar.  The interface
remains fully usable while the dataset is loading.

Click **Unload** to release the dataset and free server memory.


Variable panel
~~~~~~~~~~~~~~

Select the variable to display, the colormap, and optional ``vmin``/``vmax``
bounds.  Click **Render** to fetch and overlay the scalar field on the globe.

* Values that are NaN or masked are rendered **fully transparent**, letting
  the basemap show through.
* The field is rendered as a PNG when transparency is required (NaN pixels)
  and as JPEG otherwise for faster transfer.
* An opacity slider controls the blending of the scalar layer over the
  basemap.
* A color legend is displayed below the controls.

The scalar field is rendered server-side: the 2-D array slice is resampled
to the output tile size using **bilinear interpolation** (``PIL.Image.BILINEAR``
via Pillow), then colormapped to RGBA.


Time & Depth panel
~~~~~~~~~~~~~~~~~~

Use the **Time step** and **Z level** sliders (or the ‹/› arrow buttons) to
navigate the dataset's temporal and vertical dimensions.  Changing either
slider triggers an automatic re-render.

**Playback** — click **▶ Play** to animate through all time steps at the
chosen FPS.  Frames are pre-fetched in the background before playback starts.
Click **■ Stop** to halt.


Diagnostics panel
~~~~~~~~~~~~~~~~~

Three interaction modes are available:

Point inspection (click on the globe)
  Without any diagnostic mode active, clicking on the globe places a dot
  marker and opens a small tooltip.  The value displayed is obtained by
  **nearest-neighbour lookup** in the dataset's native grid at the clicked
  (lon, lat) coordinates.  The tooltip shows the variable value, coordinates,
  time step, and depth.

Time series (⏱ Time series)
  Click **⏱ Time series** to enter time-series mode, then click any point on
  the globe.  A dot marker is placed and a time-series chart appears at the
  bottom of the globe.  The time series is extracted by **nearest-neighbour
  lookup** at the clicked location across all available time steps.

Section (↔ Section)
  Click **↔ Section** to draw a vertical section along an arbitrary polyline:

  * **Left-click** adds a waypoint (shown as a dot on the globe).  A growing
    line connects the waypoints in real time; each segment is drawn as a
    great-circle arc (32 intermediate points per segment).
  * **Right-click** finalises the section.  The server extracts a vertical
    slice along the polyline and displays a depth–distance diagram in the
    chart panel.
  * Any number of waypoints can be added before finalising (broken-line /
    multi-segment sections).
  * The section line and waypoint dots remain visible on the globe after the
    chart is displayed.

  **Section sampling** — the requested number of horizontal points
  (``n_points``, default 150) is distributed across segments proportionally
  to each segment's geographic length (great-circle distance).  Along each
  segment the sampling points are placed at linearly spaced longitudes and
  latitudes, and the data value at each point is retrieved by
  **nearest-neighbour lookup** in the native grid.  The vertical axis
  uses the depth coordinate as-is (no interpolation).

Click **✕** to exit diagnostic mode.


Currents panel (particle animation)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **Currents** panel drives a canvas-based particle animation that
visualises 2-D velocity fields (e.g. surface currents):

1. Expand the **Currents** panel.
2. Select the **U variable** (zonal) and **V variable** (meridional).
3. Toggle **Enable particle animation** on.

Particles are rendered as white semi-transparent trails on a canvas overlay
above the globe.  Trails fade at a rate that is consistent regardless of the
browser's actual frame rate.  Rotating or panning the globe instantly clears
the particle canvas so that trails do not appear misaligned.

**Velocity interpolation** — the U and V fields are first regridded from the
dataset's native grid onto a regular lon/lat grid (default 512 × 256) using
``scipy.interpolate.RegularGridInterpolator`` with **bilinear interpolation**.
At each animation frame, each particle's velocity is obtained by **bilinear
interpolation** within this regular grid, then its position is advanced using
the interpolated velocity scaled by the *Speed scale* parameter and the actual
elapsed time (time-based integration, independent of frame rate).

Tunable parameters:

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Parameter
     - Description
   * - Nb. particles
     - Number of simultaneous particles (default 3 000).
   * - Speed scale
     - Visual speed amplification in degrees per second per m/s
       (default 5).  Increase for slow datasets, decrease for fast ones.
   * - Trail opacity
     - Per-frame opacity multiplier at 60 fps reference (default 0.92).
       Lower values give shorter trails.


Deployment on an HPC cluster (Datarmor)
----------------------------------------

The viewer can be run on a compute node and accessed from a local machine via
an SSH tunnel.

**Step 1 – start an interactive job on a compute node**

.. code-block:: bash

   qsub -I -l select=1:ncpus=2:mem=8gb -l walltime=04:00:00

Once the node is allocated, note its hostname:

.. code-block:: bash

   hostname
   # → datarmor18  (example)

**Step 2 – launch armoor-viewer on the compute node**

.. code-block:: bash

   module load armoor-py3.11
   armoor-viewer --host 0.0.0.0 --port 5000

``--host 0.0.0.0`` is required so the server accepts connections from outside
the node.

**Step 3 – open an SSH tunnel from your local machine**

In a new terminal on your local machine:

.. code-block:: bash

   ssh -L 5000:datarmor18:5000 <user>@datarmor.ifremer.fr

This forwards ``localhost:5000`` on your machine to port 5000 on the compute
node, routed through the login node.

**Step 4 – open the viewer in Firefox**

.. code-block:: bash

   firefox http://localhost:5000

**Notes**

* If port 5000 is already in use, choose another port (e.g. 8080) and use the
  same port in both ``armoor-viewer --port 8080`` and ``-L 8080:...:8080``.
* To run the tunnel in the background:

  .. code-block:: bash

     ssh -fNL 5000:datarmor18:5000 <user>@datarmor.ifremer.fr
     # To close it:
     kill $(lsof -ti:5000)

* For a batch job, add ``echo "Node: $(hostname)"`` to the job script and read
  the node name from the job's stdout file once the job starts.
* If the browser must run directly on the cluster (remote graphical session
  — NoMachine/VNC/X2Go — instead of a local browser via SSH tunnel) and that
  session has no WebGL2-capable GPU, force the 2D mode. See *Deployment on
  Météo-France Belenos* below for a concrete example of this setup.


Deployment on Météo-France Belenos
------------------------------------

Belenos is reached through Météo-France's internal remote-access chain,
not a local browser + SSH tunnel:

1. Remote Desktop (RDP) connection through the ``wab-calcul.meteo.fr``
   bastion.
2. This lands on an ephemeral, blank session on
   ``rrdp01-partenaires.meteo.fr``.
3. From that session, ``ssh -X`` to Belenos (this is Météo-France's
   protocol for authorizing X11 through the chain above) — optionally
   with a ``-L`` port forward if ``armoor-viewer`` runs on an allocated
   compute node rather than the login node:

   .. code-block:: bash

      ssh -L 5000:belenos59:5000 -X belenos

   (``belenos59`` here is an example compute node name — substitute the
   node you were allocated, or drop ``-L ...`` entirely and just
   ``ssh -X belenos`` if running the server directly on the login node.)

4. Firefox is then opened **inside that ``ssh -X`` session** — it actually
   *runs* on Belenos and its display is forwarded back through the whole
   chain to the Remote Desktop window.

Because Firefox executes on Belenos itself, it is subject to whatever
graphics stack that machine exposes.  On the login nodes this is a
remote-management chip (ASPEED BMC, no real GPU) plus an old software
Mesa/llvmpipe build (confirmed: 18.3.4, capped at OpenGL ES 2.0) —
**WebGL2 is unavailable**, so the 3D globe (and iTowns' ``PlanarView``,
which relies on the same rendering engine) fails with a
*"Your graphics card does not seem to support WebGL 2"* error.  Force the
2D render mode so the viewer works without hitting it:

.. code-block:: bash

   module load armoor-py3.11
   armoor-viewer --render-mode 2d
   # add --host 0.0.0.0 --port 5000 if running on an allocated compute
   # node reached through the -L forward from step 3

Then, still inside the ``ssh -X`` session:

.. code-block:: bash

   firefox http://127.0.0.1:5000

Confirmed working through this chain on Belenos (2D mode), as well as on
Datarmor via a direct SSH tunnel from a local machine (3D or 2D).

If a node with a real, WebGL2-capable GPU is reached through this chain
(e.g. a future GPU-backed interactive partition), the 3D mode can be used
the same way — just drop ``--render-mode`` (or set it to ``auto``) and the
browser will auto-detect WebGL2 support.


Supported dataset formats
-------------------------

The viewer understands the same formats as armoor's ``open_decode`` function:

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Format key
     - Description
   * - ``zarr``
     - Zarr store (handled natively via xarray)
   * - ``armoor``
     - armoor-native format
   * - ``cmems_model``
     - Copernicus Marine model output
   * - ``hycom``
     - HYCOM model output
   * - ``croco``
     - CROCO (Coastal and Regional Ocean COmmunity model)
   * - ``croco_xios``
     - CROCO output via XIOS
   * - ``woa18``
     - World Ocean Atlas 2018


CLI reference
-------------

.. code-block:: text

   usage: armoor-viewer [-h] [--host HOST] [--port PORT] [--debug]
                         [--render-mode {auto,2d,3d}]

   Interactive web viewer for armoor / xarray ocean datasets.

   options:
     -h, --help            show this help message and exit
     --host HOST           Bind address (default 127.0.0.1)
     --port PORT           TCP port (default 5000)
     --debug               Enable Flask debug mode
     --render-mode {auto,2d,3d}
                           Frontend render mode: 'auto' (client-side WebGL2
                           detection, default), '2d' (Leaflet planisphere, no
                           GPU required), '3d' (iTowns globe, requires
                           WebGL2). Overrides $ARMOOR_VIEWER_RENDER_MODE.


Python API
----------

The viewer can also be launched programmatically:

.. code-block:: python

   from armoor.viewer import serve

   serve(host="127.0.0.1", port=5000)

Or use the factory directly to integrate with an existing WSGI server:

.. code-block:: python

   from armoor.viewer import create_app

   app = create_app()
   # app is a standard Flask application
