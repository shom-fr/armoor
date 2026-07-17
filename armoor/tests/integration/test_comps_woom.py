"""Parametrized woom integration tests — one test per comp function.

Each test builds a minimal ``workflow_<comp>.cfg`` on the fly (only the data
downloads required by that comp + the comp task itself), then runs the full
woom execution loop.

Data downloads use ``--skip-existing`` so they are performed only once across
the session, even when several comp tests run sequentially.  The shared data
lives in ``scratch_dir`` (``$HOME/armoor_tests``) regardless of which
workflow file triggered the download.

``test_bull`` (defined last) exercises ``make_bull`` on its own, relying on
the ``comp_sst``/``comp_argo``/``comp_mooring``/``comp_drifter`` run
directories left in ``scratch_dir`` by the parametrized ``test_comp`` tests
above — see its docstring. The production ``workflow.cfg`` no longer runs
``comp``/``bull`` itself (this file is now the only place that does), since
``comp_*``/``make_bull`` task run-dir lookups (``workflow.get_task_run_dir``)
resolve through the shared taskmanager and ``scratch_dir`` regardless of
which workflow/app triggered them — they don't need to be declared in the
same workflow.cfg that runs make_bull.
"""

import os
import time

import pytest
import woom.workflow as wworkflow


# ---------------------------------------------------------------------------
# Geographic extent — must cover the polygon defined in metazones.cfg.
# All comp functions use the same region.
# ---------------------------------------------------------------------------
REGION = {"lon_min": -14.0, "lon_max": -7.0, "lat_min": 45.0, "lat_max": 49.0}

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

# comp_* tasks that make_bull (tasks.cfg) links artifacts from — comp_clim is
# deliberately excluded, matching make_bull's own commandline.
BULL_COMP_DEPS = ("comp_sst", "comp_argo", "comp_mooring", "comp_drifter")


def _write_workflow_cfg(woomtmpdir, comp, get_data):
    """Write a minimal workflow cfg for *comp* into *woomtmpdir*."""
    cfg_path = os.path.join(woomtmpdir, f"workflow_{comp}.cfg")
    content = f"""\
[app]
name=TEST_{comp.upper()}

[params]
rundate=2026-07-08
lon_min={REGION['lon_min']}
lon_max={REGION['lon_max']}
lat_min={REGION['lat_min']}
lat_max={REGION['lat_max']}

[stages]
    [[prolog]]
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


def _write_bull_workflow_cfg(woomtmpdir):
    """Write a workflow cfg that runs only ``make_bull`` into *woomtmpdir*."""
    cfg_path = os.path.join(woomtmpdir, "workflow_bull.cfg")
    content = f"""\
[app]
name=TEST_BULL

[params]
rundate=2026-07-08
lon_min={REGION['lon_min']}
lon_max={REGION['lon_max']}
lat_min={REGION['lat_min']}
lat_max={REGION['lat_max']}

[stages]
    [[prolog]]
    bull=make_bull
"""
    with open(cfg_path, "w") as f:
        f.write(content)
    return cfg_path


def test_bull(woom_env):
    """Run make_bull alone, on top of the comp_* runs from ``test_comp``.

    ``make_bull`` (see ``tasks.cfg``) locates its inputs via
    ``workflow.get_task_run_dir('comp_sst')`` and friends, which resolve
    through the shared taskmanager + ``scratch_dir`` — not through this
    workflow's own task tree. So it finds the run directories that
    ``test_comp[comp_sst|comp_argo|comp_mooring|comp_drifter]`` already
    populated earlier in this same session, without re-running them.
    This test therefore depends on those four ``test_comp`` cases having
    already run in this session (guaranteed by top-to-bottom pytest
    ordering within this module) and will fail if run in isolation.
    """
    taskmanager, woomtmpdir = woom_env
    cfg_path = _write_bull_workflow_cfg(woomtmpdir)

    workflow = wworkflow.Workflow(cfg_path, taskmanager)

    missing = [
        c for c in BULL_COMP_DEPS
        if not os.path.isdir(workflow.get_task_run_dir(c))
    ]
    assert not missing, (
        f"comp_* run dirs missing for {missing}: run test_comp for these "
        "comps (or the full module) before test_bull"
    )

    _run_and_assert(workflow)
