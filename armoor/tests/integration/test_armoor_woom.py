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
    try:
        workflow.run(update=True)
    finally:  
        isend = False
        while isend == False:
            time.sleep(2.0)
            df = workflow.get_status(running=True)
            if df.empty:
                isend = True
                workflow.show_status()
        df = workflow.get_status()
        res = df[~df.STATUS.str.contains("SUCCESS")].copy()
        
        if not res.empty:
            for submission_dir in res["SUBMISSION DIR"]:
                for ext in [".out", ".err"]:
                    file = os.path.join(os.path.join(
                        submission_dir, f"job{ext}")
                        )
                    if os.path.exists(file):
                        with open(file, 'r') as f:
                            content = f.read()
                        print(content)
        assert res.empty