"""Woom integration test for armoor-data — mirrors test_comps_woom.py's shape.

Builds a minimal ``workflow_data.cfg`` on the fly (only the data downloads
required by armoor-data + the data task itself), then runs the full woom
execution loop.

Exercises armoor-data against every metazone shape used by the comp_*
integration tests, plus a fully unconfigured one, via three tasks:

- ``data`` (meta1, meta2): reuses the comp_* metazones.cfg entries, so
  vlevel (meta1) and vrange+trange_seq (meta2) are exercised too — one
  output/plot per vertical level or bin. Since armoor-data has no colocation
  step, metazones.cfg's static ``tbound`` (meant to be overridden by
  armoor-comp-*'s own ``--tbound``) would otherwise filter out all of
  today's downloaded data; ``--tbound`` is passed here for the same reason.
- ``data_native`` (meta3): no vlevel/vrange/tbound at all, so armoor-data
  must fall back to the data's own native vertical levels and time steps.
- ``data_mapseries`` (meta3): dedicated ``data_mapseries.cfg`` for the
  ``mapseries`` otype — a model source (cmems_glo12, ptemp/sal/curr), a
  second "obs" source with the same ptemp (cmems_sst_l4, a satellite SST
  product -- armoor.data.datatype.DataSstSatellite/PlotSstSatellite, both
  thin DataOceanModel/PlotOceanModel subclasses), and a woa18 climatology
  referenced via "clim". Exercises the climatology self-plotting guard,
  the "clim" min/max table row, and "cbar_group" pooling the color scale
  between the obs and model ptemp series, all against real (sample) data
  end to end.

Data downloads use ``--skip-existing`` so they are performed only once across
the session, even when this test runs alongside the comp_* integration tests.
The shared data lives in ``scratch_dir`` (``$HOME/armoor_tests``) regardless
of which workflow file triggered the download.
"""

import glob
import os
import time

import woom.workflow as wworkflow


# ---------------------------------------------------------------------------
# Geographic extent — must cover the polygon defined in metazones.cfg.
# ---------------------------------------------------------------------------
REGION = {"lon_min": -14.0, "lon_max": -7.0, "lat_min": 45.0, "lat_max": 49.0}

# ---------------------------------------------------------------------------
# Data dependencies (get_data tasks only) for armoor-data's data.cfg
# ---------------------------------------------------------------------------
DATA_GET_DATA = "get_cmems_glo12_temp,get_cmems_glo12_sal,get_cmems_glo12_curr"

# Data dependencies for data_mapseries.cfg (model + obs + climatology)
DATA_MAPSERIES_GET_DATA = (
    "get_cmems_glo12_temp,get_cmems_glo12_sal,get_cmems_glo12_curr,"
    "get_cmems_sst_l4,get_woa18"
)


def _write_workflow_cfg(woomtmpdir):
    """Write a minimal workflow cfg for armoor-data into *woomtmpdir*."""
    cfg_path = os.path.join(woomtmpdir, "workflow_data.cfg")
    content = f"""\
[app]
name=TEST_DATA

[params]
rundate=2026-07-08
lon_min={REGION['lon_min']}
lon_max={REGION['lon_max']}
lat_min={REGION['lat_min']}
lat_max={REGION['lat_max']}

[stages]
    [[prolog]]
    get_data={DATA_GET_DATA}
    data=data
    #,data_native
"""
    with open(cfg_path, "w") as f:
        f.write(content)
    return cfg_path


def _write_mapseries_workflow_cfg(woomtmpdir):
    """Write a minimal workflow cfg for the mapseries otype into *woomtmpdir*."""
    cfg_path = os.path.join(woomtmpdir, "workflow_data_mapseries.cfg")
    content = f"""\
[app]
name=TEST_DATA_MAPSERIES

[params]
rundate=2026-07-08
lon_min={REGION['lon_min']}
lon_max={REGION['lon_max']}
lat_min={REGION['lat_min']}
lat_max={REGION['lat_max']}

[stages]
    [[prolog]]
    get_data={DATA_MAPSERIES_GET_DATA}
    data_mapseries=data_mapseries
"""
    with open(cfg_path, "w") as f:
        f.write(content)
    return cfg_path


def _run_and_assert(workflow):
    """Dry-run then real run; print logs of failed tasks and assert success."""
    workflow.show_overview()
    try:
        workflow.run(dry=True)
    except Exception as e:
        print(e)
        assert False, f"dry-run failed: {e}"

    skip_tasks = []
    for stage_content in workflow.task_tree.values():
        for parallel_groups in stage_content.values():
            for group in parallel_groups:
                for task_name in group:
                    artifacts = workflow.get_task_artifacts(task_name)
                    if artifacts and isinstance(artifacts, dict):
                        paths = [v for v in artifacts.values() if isinstance(v, str)]
                        if paths and all(os.path.exists(p) for p in paths):
                            skip_tasks.append(task_name)
    if skip_tasks:
        print(f"Skipping tasks with existing artifacts: {skip_tasks}")

    try:
        workflow.run(skip=skip_tasks or None)
    finally:
        is_done = False
        while not is_done:
            time.sleep(2.0)
            df = workflow.get_status(running=True)
            if df.empty:
                is_done = True
                workflow.show_status()

        df = workflow.get_status()
        failures = df[~df.STATUS.str.contains("SUCCESS|SKIPPED")].copy()

        if not failures.empty:
            for submission_dir in failures["SUBMISSION DIR"]:
                for ext in [".out", ".err", ".sh"]:
                    job_file = os.path.join(submission_dir, f"job{ext}")
                    if os.path.exists(job_file):
                        with open(job_file) as f:
                            print(f.read())
                        print("--" * 30)
            print("==" * 10)

        assert failures.empty


def _assert_nonempty_plots(run_dir, task):
    """A SUCCESS status doesn't mean the plots are real; catch empty/corrupt files too."""
    pngs = glob.glob(os.path.join(run_dir, task, "plot", "**", "*.png"), recursive=True)
    assert pngs, f"no plot output found under {run_dir}/{task}/plot"
    for f in pngs:
        assert os.path.getsize(f) > 0, f"empty output file: {f}"


def test_data(woom_env):
    """Run a minimal woom workflow for armoor-data and assert all tasks
    succeed and produce non-empty plots."""
    taskmanager, woomtmpdir = woom_env

    cfg_path = _write_workflow_cfg(woomtmpdir)

    workflow = wworkflow.Workflow(cfg_path, taskmanager)
    _run_and_assert(workflow)
    _assert_nonempty_plots(workflow.get_task_run_dir("data"), "data")


def test_data_mapseries(woom_env):
    """Run the mapseries otype (model + obs + climatology) and assert
    success and non-empty plots."""
    taskmanager, woomtmpdir = woom_env

    cfg_path = _write_mapseries_workflow_cfg(woomtmpdir)

    workflow = wworkflow.Workflow(cfg_path, taskmanager)
    _run_and_assert(workflow)
    _assert_nonempty_plots(workflow.get_task_run_dir("data_mapseries"), "data_mapseries")
