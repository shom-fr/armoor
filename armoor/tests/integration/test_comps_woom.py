"""Parametrized woom integration tests — one test per comp function.

Each test builds a minimal ``workflow_<comp>.cfg`` on the fly (only the data
downloads required by that comp + the comp task itself), then runs the full
woom execution loop.

Data downloads use ``--skip-existing`` so they are performed only once across
the session, even when several comp tests run sequentially.  The shared data
lives in ``scratch_dir`` (``$HOME/armoor_tests``) regardless of which
workflow file triggered the download.
"""

import os
import time

import pytest
import woom.workflow as wworkflow


# ---------------------------------------------------------------------------
# Geographic extent — must cover the polygon defined in metazones.cfg.
# All comp functions use the same region.
# ---------------------------------------------------------------------------
REGION = {"lon_min": -14.0, "lon_max": -10.0, "lat_min": 45.0, "lat_max": 49.0}

# ---------------------------------------------------------------------------
# Per-comp data dependencies (get_data tasks only)
# ---------------------------------------------------------------------------
COMP_DATA_DEPS = {
    "comp_mooring": "get_cmems_insitu,get_cmems_glo12_temp,get_cmems_glo12_sal",
    "comp_argo":    "get_cmems_insitu,get_cmems_glo12_temp,get_cmems_glo12_sal",
    "comp_clim":    "get_woa18,get_cmems_glo12_temp,get_cmems_glo12_sal",
    "comp_sst":     "get_cmems_sst_l4,get_cmems_sst_l3,get_cmems_glo12_temp",
    "comp_drifter": "get_cmems_insitu,get_cmems_glo12_temp,get_cmems_glo12_sal,get_cmems_glo12_curr",
}


def _write_workflow_cfg(woomtmpdir, comp, get_data):
    """Write a minimal workflow cfg for *comp* into *woomtmpdir*."""
    cfg_path = os.path.join(woomtmpdir, f"workflow_{comp}.cfg")
    content = f"""\
[app]
name=TEST_{comp.upper()}

[params]
rundate=today
lon_min={REGION['lon_min']}
lon_max={REGION['lon_max']}
lat_min={REGION['lat_min']}
lat_max={REGION['lat_max']}

[stages]
    [[prolog]]
    copernicus_login=copernicus_login
    get_data={get_data}
    comp={comp}
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


@pytest.mark.parametrize("comp", COMP_DATA_DEPS.keys())
def test_comp(comp, woom_env):
    """Run a minimal woom workflow for *comp* and assert all tasks succeed."""
    taskmanager, woomtmpdir = woom_env

    get_data = COMP_DATA_DEPS[comp]
    cfg_path = _write_workflow_cfg(woomtmpdir, comp, get_data)

    workflow = wworkflow.Workflow(cfg_path, taskmanager)
    _run_and_assert(workflow)
