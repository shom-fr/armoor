import logging, os
import time, shutil

import woom.ext as wext
import woom.tasks as wtasks
import woom.hosts as whosts
import woom.workflow as wworkflow


THISDIR = os.path.dirname(__file__)
WOOMDIR = os.path.join(THISDIR, "woom")
WOOMTMPDIR = os.path.join(os.path.expanduser("~"), "woom")
WOOM_CFG_PATTERN = os.path.join(WOOMTMPDIR, "{}.cfg")

def test():

    shutil.copytree(
        WOOMDIR,
        WOOMTMPDIR,
        dirs_exist_ok=True
        )
    # Remove stale job scripts so woom regenerates them for the current host.
    # Old scripts generated under a different host (e.g. gitlab-ci) would
    # reference wrong conda/module paths and cause immediate failures.
    jobs_dir = os.path.join(WOOMTMPDIR, "jobs")
    if os.path.exists(jobs_dir):
        shutil.rmtree(jobs_dir)
    os.chdir(WOOMTMPDIR)
    
    wext.load_jinja_filters(os.path.join(WOOMTMPDIR, "ext/jinja_filters.py"))
    
    hostmanager = whosts.HostManager()
    hostmanager.load_config(WOOM_CFG_PATTERN.format("hosts"))
    host = hostmanager.infer_host()
    print(f"Woom infered host : {host}")
    
    taskmanager = wtasks.TaskManager(host)
    taskmanager.load_config(WOOM_CFG_PATTERN.format("tasks"))
    
    workflow = wworkflow.Workflow(
        WOOM_CFG_PATTERN.format("workflow"),
        taskmanager
        )
    
    workflow.show_overview()
    try:
        workflow.run(dry=True)
    except Exception as e:
        print(e)
        assert False
    else:
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
            isend = False
            while isend == False:
                time.sleep(2.0)
                df = workflow.get_status(running=True)
                if df.empty:
                    isend = True
                    workflow.show_status()
            df = workflow.get_status()
            res = df[~df.STATUS.str.contains("SUCCESS|SKIPPED")].copy()
            
            if not res.empty:
                for submission_dir in res["SUBMISSION DIR"]:
                    for ext in [".out", ".err", ".sh"]:
                        file = os.path.join(os.path.join(
                            submission_dir, f"job{ext}")
                            )
                        if os.path.exists(file):
                            with open(file, 'r') as f:
                                content = f.read()
                            print(content)
                            print("--" * 30)
                    print("==" * 10)
            assert res.empty
