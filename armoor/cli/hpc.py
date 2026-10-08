"""HPC job submission for armoor-comp-\* and armoor-data pipelines via woom.

The calling process supervises the full pipeline, waiting for each wave
before submitting the next:

- Wave 0 (LOAD): 1 job per dataset, loads all metazones, writes zarr
  paths JSON. For armoor-data this already includes interpolation, done
  if necessary (see armoor.data.load.load_datasets) -- there is no
  separate interp wave.
- Wave 1: N_metazones jobs in parallel, no plot. filter+coloc+output for
  armoor-comp-\* (stage1_label="comp"); filter+output only for
  armoor-data (stage1_label="output", no coloc stage).
- Wave 2 (MERGE): 1 job, merges per-metazone output JSONs.
- Wave 3 (PLOT): N_otypes jobs in parallel, one otype per job.
- Wave 4 (FINAL): in-process, writes the final user-facing JSON directly.

Each wave waits for the previous one to finish before submitting the next.

Sub-job logs are consolidated into the main log by _log_completed_jobs()
after each wave.

For local/background mode the same wave logic runs via woom's
BackgroundJobManager (each wave is parallel, then we wait before the next).
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from armoor.cli import HPC_DEFAULTS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_hpc(host: Any, scheduler: str, cfgfile: Path, metafile: Path, metazones_list: list[str],
            func_comp: str, jsonfile: Path, ofilter: bool, ocoloc: bool,
            comp_args: dict, kw_dask: tuple, original_argv: list[str],
            run_dir: Optional[Path] = None, ini_schema: Optional[str] = None,
            stage1_label: str = "comp") -> None:
    """Run the armoor comp/data pipeline as HPC jobs, supervising all waves.

    Parameters
    ----------
    host : woom Host object
    scheduler : str  — "slurm", "pbspro" or "background"
    cfgfile, metafile : Path
    metazones_list : list of str
    func_comp : str
    jsonfile : Path — final output JSON path
    ofilter, ocoloc : bool — stage-only flags from original invocation
        (ocoloc is unused when stage1_label != "comp"; armoor-data has no
        colocation stage)
    comp_args : dict — extra args (radius, qc, tbound, …)
    kw_dask : tuple — dask args from original invocation
    original_argv : list — sys.argv of the calling process
    run_dir : Path|None — working directory for job scripts and logs
    ini_schema : str — path to the .ini schema file (COMP_INI or DATA_INI)
    stage1_label : str — internal label for Wave 1 ("comp" for
        armoor-comp-\*, "output" for armoor-data), used for job/log names
        and to look up time_<label>/ncpus_<label> in the [hpc] section.
    """
    from armoor import ArmoorError

    # Resolve template placeholders in jsonfile (e.g. 'ncs_{func_comp}.json').
    jsonfile = Path(str(jsonfile).format(func_comp=func_comp))

    hpc_cfg = _get_hpc_cfg(cfgfile, ini_schema)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    workdir = Path.cwd()
    is_hpc = scheduler != "background"

    if run_dir is not None:
        run_dir = Path(run_dir)
    else:
        run_dir = workdir / f".armoor_hpc_{func_comp}_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

    # Delegate submission and status querying to woom for all modes.
    manager = host.get_jobmanager()

    logger.info(f"HPC pipeline starting — scheduler={scheduler}, run_dir={run_dir}")

    # Collects (wave_label, job_name, status_name) tuples for the final summary.
    all_records = []

    def _submit(script, opts):
        """Submit one job via woom's job manager."""
        return manager.submit(str(script), opts)

    # ------------------------------------------------------------------
    # Wave 0 : load jobs (1 per dataset, covering all metazones)
    # ------------------------------------------------------------------
    mz_str = ",".join(metazones_list)
    dataset_keys = _get_dataset_keys(cfgfile, ini_schema)
    use_wave0 = len(dataset_keys) > 0

    load_jsons = {}  # dataset_key → Path(json)
    try:
        if use_wave0:
            load_jobs = []
            ncpus_load = hpc_cfg.get("ncpus_load", HPC_DEFAULTS["ncpus_load"])
            for dkey in dataset_keys:
                subdir = run_dir / f"load_{dkey}"
                subdir.mkdir(exist_ok=True)
                load_json = run_dir / f"load_{dkey}.json"
                load_jsons[dkey] = load_json
                cmd = _build_load_cmd(original_argv, mz_str, dkey, load_json, n_workers=ncpus_load)
                script = _write_script(subdir, cmd, workdir=workdir)
                job = _submit(script, _opts(hpc_cfg, "load", dkey, host=host, subdir=subdir))
                load_jobs.append(job)

            if is_hpc:
                failed, statuses = _wait_hpc_jobs(load_jobs, "Wave 0 (load)")
                _log_completed_jobs(load_jobs, "Wave 0 (load)")
                for job in load_jobs:
                    st = statuses.get(job)
                    all_records.append(("Wave 0 (load)", job.name, st.name if st else "COMPLETED"))
                if failed:
                    raise ArmoorError(
                        f"Wave 0 load job(s) failed — aborting pipeline. "
                        f"Check stderr files in {run_dir}."
                    )
            else:
                _wait_for_jobs(load_jobs)
                _log_completed_jobs(load_jobs, "Wave 0 (load)")
                for job in load_jobs:
                    all_records.append(("Wave 0 (load)", job.name, "COMPLETED"))

        # ------------------------------------------------------------------
        # Wave 1 : comp jobs (filter+coloc+output, no plot), 1 per metazone
        # ------------------------------------------------------------------
        comp_jobs = []
        wave1_label = f"Wave 1 ({stage1_label})"
        for mz in metazones_list:
            subdir = run_dir / f"{stage1_label}_{mz}"
            subdir.mkdir(exist_ok=True)
            output_json = run_dir / f"output_{mz}.json"
            # Each Wave 1 job receives all dataset JSONs; it picks its own
            # metazone's zarr paths from each JSON at runtime.
            all_jsons = [str(load_jsons[dkey]) for dkey in dataset_keys]
            extra_zarrs = ",".join(all_jsons) if (use_wave0 and all_jsons) else None
            cmd = _build_stage_cmd(
                original_argv, mz,
                no_plot=True,
                plot_only=None,
                input_json=None,
                output_json=output_json,
                input_zarrs=extra_zarrs,
            )
            script = _write_script(subdir, cmd, workdir=workdir)
            job = _submit(script, _opts(hpc_cfg, stage1_label, mz, host=host, subdir=subdir))
            comp_jobs.append(job)

        if is_hpc:
            failed, statuses = _wait_hpc_jobs(comp_jobs, wave1_label)
            _log_completed_jobs(comp_jobs, wave1_label)
            for job in comp_jobs:
                st = statuses.get(job)
                all_records.append((wave1_label, job.name, st.name if st else "COMPLETED"))
            if failed:
                raise ArmoorError(
                    f"{wave1_label} job(s) failed — aborting pipeline. "
                    f"Check stderr files in {run_dir}."
                )
        else:
            _wait_for_jobs(comp_jobs)
            _log_completed_jobs(comp_jobs, wave1_label)
            for job in comp_jobs:
                all_records.append((wave1_label, job.name, "COMPLETED"))

        # ------------------------------------------------------------------
        # Wave 2 : merge — inline JSON merge (no HPC job needed)
        # ------------------------------------------------------------------
        output_jsons = [run_dir / f"output_{mz}.json" for mz in metazones_list]
        merged_json = run_dir / "outputs_all.json"
        merged = {}
        for path in output_jsons:
            if not path.exists():
                logger.warning(f"Wave 2 merge: missing output JSON {path}")
                continue
            with open(path) as f:
                d = json.load(f)
            for otype, mz_dict in d.items():
                merged.setdefault(otype, {}).update(mz_dict)
        with open(merged_json, "w") as f:
            json.dump(merged, f, indent=4)
        logger.info(f"Wave 2 merge: {len(output_jsons)} JSONs -> {merged_json}")
        all_records.append(("Wave 2 (merge)", "merge", "COMPLETED"))

        # ------------------------------------------------------------------
        # Wave 3 : plot jobs, 1 per otype
        # ------------------------------------------------------------------
        otypes = _get_otypes_from_cfg(cfgfile, ini_schema)
        mz_str = ",".join(metazones_list)
        plot_jobs = []
        plot_output_jsons = []
        for otype in otypes:
            subdir = run_dir / f"plot_{otype}"
            subdir.mkdir(exist_ok=True)
            plot_json = run_dir / f"plots_{otype}.json"
            plot_output_jsons.append(plot_json)
            cmd = _build_stage_cmd(
                original_argv, mz_str,
                no_plot=False,
                plot_only=otype,
                input_json=merged_json,
                output_json=plot_json,
            )
            script = _write_script(subdir, cmd, workdir=workdir)
            job = _submit(script, _opts(hpc_cfg, "plot", otype, host=host, subdir=subdir))
            plot_jobs.append(job)

        if is_hpc:
            failed, statuses = _wait_hpc_jobs(plot_jobs, "Wave 3 (plot)")
            _log_completed_jobs(plot_jobs, "Wave 3 (plot)")
            for job in plot_jobs:
                st = statuses.get(job)
                all_records.append(("Wave 3 (plot)", job.name, st.name if st else "COMPLETED"))
            if failed:
                raise ArmoorError(
                    f"Wave 3 plot job(s) failed — aborting pipeline. "
                    f"Check stderr files in {run_dir}."
                )
        else:
            _wait_for_jobs(plot_jobs)
            _log_completed_jobs(plot_jobs, "Wave 3 (plot)")
            for job in plot_jobs:
                all_records.append(("Wave 3 (plot)", job.name, "COMPLETED"))

        # ------------------------------------------------------------------
        # Wave 4 : finalize — write final user-facing JSON (runs in-process)
        # ------------------------------------------------------------------
        # Use plot outputs (PNG paths) if Wave 3 ran, else Wave 2 zarr outputs.
        png_paths = []
        for pj in plot_output_jsons:
            if pj.exists():
                with open(pj) as f:
                    png_paths.extend(json.load(f))

        _finalize(merged_json, jsonfile, cfgfile, ini_schema, png_paths=png_paths or None)
        all_records.append(("Wave 4 (final)", "finalize", "COMPLETED"))

        logger.info(f"Pipeline complete — run_dir: {run_dir}")
        logger.info(f"Final JSON: {jsonfile}")

    finally:
        if all_records:
            _log_pipeline_summary(all_records, run_dir)


# ---------------------------------------------------------------------------
# Pipeline summary
# ---------------------------------------------------------------------------

def _log_pipeline_summary(records, run_dir):
    """Log a one-page summary of all pipeline jobs and their final status.

    Called in a finally block so it prints even when the pipeline aborts.

    Parameters
    ----------
    records : list of (wave_label, job_name, status_name)
    run_dir : Path
    """
    # woom JobStatus enum member names (JobStatus.X.name == "X")
    _FAIL_STATES = {"FAILED", "ERROR"}
    _CANCEL_STATES = {"KILLED", "TERMINATED"}  # KILLED = Slurm CANCELLED or sibling cancel

    col_wave = max((len(r[0]) for r in records), default=10)
    col_job  = max((len(r[1]) for r in records), default=10)
    col_st   = max((len(r[2]) for r in records), default=6)
    sep = f"{'─' * (col_wave + col_job + col_st + 7)}"

    lines = [
        "",
        "╔══ PIPELINE SUMMARY " + "═" * max(0, len(sep) - 20) + "╗",
        f"  {'Wave':<{col_wave}}  {'Job':<{col_job}}  {'Status':<{col_st}}",
        sep,
    ]

    n_ok = n_fail = n_cancel = 0
    prev_wave = None
    for wave, job, status in records:
        if prev_wave and wave != prev_wave:
            lines.append(sep)
        prev_wave = wave
        if status in _FAIL_STATES:
            marker = "✗"
            n_fail += 1
        elif status in _CANCEL_STATES:
            marker = "~"
            n_cancel += 1
        else:
            marker = "✓"
            n_ok += 1
        lines.append(f"  {wave:<{col_wave}}  {job:<{col_job}}  {marker} {status}")

    lines += [
        sep,
        f"  {n_ok} succeeded  |  {n_fail} failed  |  {n_cancel} cancelled",
        f"  run_dir: {run_dir}",
        "╚" + "═" * (len(sep) - 1) + "╝",
        "",
    ]

    for line in lines:
        logger.info(line)


# ---------------------------------------------------------------------------
# Job log collection
# ---------------------------------------------------------------------------

def _log_completed_jobs(jobs, wave_name):
    """Append each completed job's stdout and stderr to the main armoor logger.

    Called after a wave finishes so the orchestrator log contains the full
    execution trace of every sub-job in one consolidated place.
    stdout (job.out) and stderr (job.err) are separate files (see
    _write_script) and are replayed as two distinct sections, each wrapped
    in a clearly delimited header/footer block, so real tracebacks aren't
    buried in routine progress logging.

    Parameters
    ----------
    jobs : list of woom ScheduledJob
        Jobs whose output files to replay.
    wave_name : str
        Wave label used in the log section headers.

    Returns
    -------
    None
    """
    for job in jobs:
        try:
            files = job.files
        except AttributeError:
            continue
        for label, key in (("stdout", "out"), ("stderr", "err")):
            try:
                log_path = Path(files.get(key, ""))
            except TypeError:
                continue
            if not log_path.exists():
                continue
            content = log_path.read_text().strip()
            if not content:
                continue
            jobid = getattr(job, "jobid", "?")
            sep = "─" * 60
            logger.info(f"\n{sep}\n{wave_name} / {job.name}  (jobid={jobid})  [{label}]\n{sep}")
            for line in content.splitlines():
                logger.info(f"  {line}")
            logger.info(sep)


# ---------------------------------------------------------------------------
# Command reconstruction
# ---------------------------------------------------------------------------

def _redirect_log_file_to_devnull(argv):
    """Force sub-job file logging to /dev/null.

    Sub-job stdout/stderr are captured by the scheduler (job.out/job.err)
    and later replayed by _log_completed_jobs().  Writing to the shared
    armoor.log from parallel sub-jobs produces interleaved, unreadable output.

    Parameters
    ----------
    argv : list of str
        Sub-job command-line arguments, modified in place.

    Returns
    -------
    None
    """
    if "--log-file" in argv:
        i = argv.index("--log-file")
        argv[i + 1] = "/dev/null"
    else:
        argv.extend(["--log-file", "/dev/null"])


def _build_stage_cmd(original_argv, mz, no_plot, plot_only, input_json, output_json,
                     input_zarrs=None):
    """Reconstruct the CLI command for a sub-job.

    Parameters
    ----------
    original_argv : list  — sys.argv from the orchestrator process
    mz : str              — single metazone name (or comma-joined list for plot jobs)
    no_plot : bool        — add --no-plot flag
    plot_only : str|None  — otype for --plot-only, or None
    input_json : Path|None
    output_json : Path|None
    input_zarrs : str|None — comma-separated JSON paths for Wave 1 (--input-zarrs)

    Returns
    -------
    list of str — the reconstructed argument list
    """
    argv = list(original_argv)

    # argv[0]: use absolute path of the executable
    argv[0] = str(Path(argv[0]).resolve())

    # argv[1]: replace metazones with the target metazone(s)
    argv[1] = mz

    # Remove existing stage flags that we'll replace
    for flag in ("--filters-only", "--coloc-only", "--no-plot"):
        if flag in argv:
            argv.remove(flag)

    # Remove --plot-only <value> if present
    if "--plot-only" in argv:
        i = argv.index("--plot-only")
        argv.pop(i)  # flag
        if i < len(argv):
            argv.pop(i)  # value

    # Remove --input-json <value> if present
    if "--input-json" in argv:
        i = argv.index("--input-json")
        argv.pop(i)
        if i < len(argv):
            argv.pop(i)

    # Remove existing --input-zarrs <value> if present
    if "--input-zarrs" in argv:
        i = argv.index("--input-zarrs")
        argv.pop(i)
        if i < len(argv):
            argv.pop(i)

    # Replace --jsonfile value (or add it)
    if output_json is not None:
        if "--jsonfile" in argv:
            i = argv.index("--jsonfile")
            argv[i + 1] = str(output_json)
        else:
            argv.extend(["--jsonfile", str(output_json)])
    elif "--jsonfile" in argv:
        # Remove it — plot-only jobs don't write a JSON
        i = argv.index("--jsonfile")
        argv.pop(i)
        if i < len(argv):
            argv.pop(i)

    # Add stage flags
    if no_plot:
        argv.append("--no-plot")
    if plot_only is not None:
        argv.extend(["--plot-only", plot_only])
    if input_json is not None:
        argv.extend(["--input-json", str(input_json)])
    if input_zarrs is not None:
        argv.extend(["--input-zarrs", input_zarrs])

    _redirect_log_file_to_devnull(argv)
    return argv


# ---------------------------------------------------------------------------
# Script writers
# ---------------------------------------------------------------------------

def _build_load_cmd(original_argv, mz_str, dataset_key, output_json, n_workers=None):
    """Reconstruct the CLI command for a Wave 0 load job.

    Parameters
    ----------
    original_argv : list  — sys.argv from the orchestrator process
    mz_str : str          — comma-joined list of all metazones
    dataset_key : str     — dataset key to load (--load-only value)
    output_json : Path    — path where the {mz: [paths]} JSON will be written
    n_workers : int|None  — override --dask-nworkers (should match ncpus_load)

    Returns
    -------
    list of str — the reconstructed argument list
    """
    argv = list(original_argv)
    argv[0] = str(Path(argv[0]).resolve())
    argv[1] = mz_str

    # Remove stage flags
    for flag in ("--filters-only", "--coloc-only", "--no-plot"):
        if flag in argv:
            argv.remove(flag)

    # Remove --hosts-cfg <value>: load jobs must never re-trigger the HPC
    # orchestrator, and _detect_scheduler() adds ~30s of overhead for nothing.
    if "--hosts-cfg" in argv:
        i = argv.index("--hosts-cfg")
        argv.pop(i)
        if i < len(argv):
            argv.pop(i)

    # Remove --plot-only <value>
    if "--plot-only" in argv:
        i = argv.index("--plot-only")
        argv.pop(i)
        if i < len(argv):
            argv.pop(i)

    # Remove --input-json <value>
    if "--input-json" in argv:
        i = argv.index("--input-json")
        argv.pop(i)
        if i < len(argv):
            argv.pop(i)

    # Remove --input-zarrs <value>
    if "--input-zarrs" in argv:
        i = argv.index("--input-zarrs")
        argv.pop(i)
        if i < len(argv):
            argv.pop(i)

    # Remove --load-only <value>
    if "--load-only" in argv:
        i = argv.index("--load-only")
        argv.pop(i)
        if i < len(argv):
            argv.pop(i)

    # Replace --jsonfile
    if "--jsonfile" in argv:
        i = argv.index("--jsonfile")
        argv[i + 1] = str(output_json)
    else:
        argv.extend(["--jsonfile", str(output_json)])

    # Add --load-only
    argv.extend(["--load-only", dataset_key])

    # Override --dask-nworkers to match the CPUs allocated for this load job.
    if n_workers is not None:
        if "--dask-nworkers" in argv:
            i = argv.index("--dask-nworkers")
            argv[i + 1] = str(n_workers)
        else:
            argv.extend(["--dask-nworkers", str(n_workers)])

    _redirect_log_file_to_devnull(argv)
    return argv


def _write_script(subdir, cmd, workdir=None):
    """Write a bash job script in subdir and make it executable.

    stdout and stderr are left separate — the scheduler routes them to
    log_out (job.out) and log_err (job.err) respectively (see _opts()).

    Parameters
    ----------
    subdir : Path
        Directory to write ``job.sh`` into.
    cmd : list
        Command and arguments to run, joined with spaces.
    workdir : str or Path, optional
        Directory to ``cd`` into before running `cmd`.

    Returns
    -------
    Path
        Path to the written, executable script.
    """
    script = subdir / "job.sh"
    cmd_str = " ".join(str(c) for c in cmd)
    cd_line = f"cd {workdir}\n" if workdir else ""
    script.write_text(
        "#!/bin/bash\n"
        "# Generated by armoor — do not edit\n"
        f"{cd_line}"
        f"{cmd_str}\n"
    )
    script.chmod(0o755)
    return script



def _finalize(merged_json, jsonfile, cfgfile, ini_schema, png_paths=None):
    """Write the final user-facing JSON.

    If png_paths is provided (Wave 3 ran), write those directly.
    Otherwise read merged_json ({otype: {mz: [zarr_paths]}}) and write
    zarr or netcdf paths depending on cfgfile [outputs] fmt.
    """
    if png_paths:
        with open(jsonfile, 'w') as f:
            json.dump(png_paths, f, indent=4)
        logger.info(f"Final JSON written to {jsonfile}")
        return

    from xoa.cfgm import ConfigManager
    from armoor.misc import dict_to_list

    with open(merged_json) as f:
        zarr_outputs = json.load(f)

    cfg = ConfigManager(ini_schema).load(str(cfgfile))
    ofmt = cfg['outputs'].get('fmt', 'zarr')
    flat = dict_to_list(zarr_outputs)

    if 'netcdf' in ofmt:
        from armoor.io import zarrs2netcdfs
        outputs = zarrs2netcdfs([str(p) for p in flat])
    else:
        outputs = [str(p) for p in flat]

    with open(jsonfile, 'w') as f:
        json.dump(outputs, f, indent=4)

    logger.info(f"Final JSON written to {jsonfile}")



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opts(hpc_cfg, stage, name, host=None, subdir=None):
    """Build the woom opts dict for a job."""
    time_key = f"time_{stage}"
    walltime = hpc_cfg.get(time_key, HPC_DEFAULTS.get(time_key, "01:00:00"))
    queue_generic = hpc_cfg.get("queue", HPC_DEFAULTS["queue"])
    ncpus_key = f"ncpus_{stage}"
    # Priority: user stage-specific > user general > default stage-specific > default general
    ncpus = hpc_cfg.get(ncpus_key,
            hpc_cfg.get("ncpus",
            HPC_DEFAULTS.get(ncpus_key, HPC_DEFAULTS["ncpus"])))
    queue = host.get_queue(queue_generic) if host is not None else queue_generic
    opts = {
        "name" : f"armoor_{stage}_{name}",
        "queue": queue,
        "time" : walltime,
        "ncpus": ncpus,
    }
    if subdir is not None:
        subdir = Path(subdir)
        opts["log_out"] = str(subdir / "job.out")
        opts["log_err"] = str(subdir / "job.err")
    return opts



def _wait_hpc_jobs(jobs, wave_name, poll_interval=30):
    """Poll HPC jobs until all finish, cancelling siblings on first failure.

    When any job in the wave fails, all still-running siblings are cancelled
    immediately and the polling loop exits early.

    Parameters
    ----------
    jobs : list of woom ScheduledJob
    wave_name : str — label used in log messages
    poll_interval : int — seconds between scheduler queries

    Returns
    -------
    (failed, statuses) : list of failed jobs, dict job → JobStatus
    """
    from woom.job import JobStatus

    if not jobs:
        return [], {}

    pending = list(jobs)
    statuses = {job: None for job in jobs}
    logger.info(f"[{wave_name}] Monitoring {len(jobs)} job(s)…")

    while pending:
        still_running = []
        newly_failed = []
        for job in pending:
            try:
                status = job.query_status()
            except Exception as e:
                logger.warning(
                    f"[{wave_name}] Could not query status of "
                    f"job {job.name} ({job.jobid}): {e}"
                )
                still_running.append(job)
                continue

            statuses[job] = status
            if status.is_running() or status.is_unknown():
                still_running.append(job)
            elif status.has_failed() and not status.has_been_canceled():
                newly_failed.append(job)

        if newly_failed:
            failed_names = ", ".join(f"{j.name}({j.jobid})" for j in newly_failed)
            if still_running:
                logger.warning(
                    f"[{wave_name}] {len(newly_failed)} job(s) failed "
                    f"({failed_names}) — cancelling {len(still_running)} sibling(s)."
                )
                for job in still_running:
                    try:
                        job.cancel()
                        logger.info(f"[{wave_name}] Cancelled job {job.name} ({job.jobid}).")
                    except Exception as e:
                        logger.warning(f"[{wave_name}] Could not cancel {job.name}: {e}")
                    statuses[job] = JobStatus.KILLED
            break

        if still_running:
            summary = ", ".join(f"{j.name}({j.jobid})" for j in still_running)
            logger.info(
                f"[{wave_name}] {len(still_running)}/{len(jobs)} still running: {summary}"
            )
            time.sleep(poll_interval)
            pending = still_running
        else:
            break

    failed = [
        j for j in jobs
        if statuses[j] is not None
        and statuses[j].has_failed()
        and not statuses[j].has_been_canceled()
    ]
    if failed:
        lines = "\n".join(
            f"  {j.name} (jobid={j.jobid})  status={statuses[j].name}"
            f"  stderr → {getattr(j, 'files', {}).get('err', '?')}"
            for j in failed
        )
        logger.error(f"[{wave_name}] {len(failed)} job(s) FAILED:\n{lines}")
    else:
        logger.info(f"[{wave_name}] All {len(jobs)} job(s) completed successfully.")

    return failed, statuses



def _wait_for_jobs(jobs):
    """Wait for all background jobs to complete."""
    for job in jobs:
        job.wait()


def _get_hpc_cfg(cfgfile, ini_schema):
    """Read the [hpc] section from cfgfile, falling back to HPC_DEFAULTS."""
    try:
        from xoa.cfgm import ConfigManager
        cfg = ConfigManager(ini_schema).load(str(cfgfile))
        hpc = cfg.get("hpc")
        if hpc:
            merged = dict(HPC_DEFAULTS)
            merged.update({k: v for k, v in hpc.items() if v is not None})
            return merged
    except Exception:
        pass
    return dict(HPC_DEFAULTS)


def _get_dataset_keys(cfgfile, ini_schema):
    """Return the list of dataset keys from the [data] section of cfgfile."""
    from xoa.cfgm import ConfigManager
    cfg = ConfigManager(ini_schema).load(str(cfgfile))
    return list(cfg["data"].keys())


def _get_otypes_from_cfg(cfgfile, ini_schema):
    """Return the list of otypes defined in the [outputs] section of cfgfile."""
    try:
        from xoa.cfgm import ConfigManager
        cfg = ConfigManager(ini_schema).load(str(cfgfile))
        outputs = cfg.get("outputs", {})
        otypes = []
        for key, section in outputs.items():
            if key == "fmt":
                continue
            if isinstance(section, dict):
                otype = section.get("otype")
                if otype:
                    otypes.append(otype)
        return list(dict.fromkeys(otypes))  # deduplicate preserving order
    except Exception as e:
        logger.warning(f"Could not read otypes from cfg: {e}")
        return []
