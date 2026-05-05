"""Shared woom fixtures for integration tests."""

import os
import shutil

import pytest
import woom.ext as wext
import woom.hosts as whosts
import woom.tasks as wtasks


THISDIR = os.path.dirname(__file__)
WOOMDIR = os.path.join(THISDIR, "woom")
WOOMTMPDIR = os.path.join(os.path.expanduser("~"), "woom")


@pytest.fixture(scope="session")
def woom_env():
    """Copy woom config to a temp dir, initialise hosts and tasks.

    Session-scoped so the copy and host detection happen once per test run.
    The ``scratch_dir`` (``$HOME/armoor_tests``) is shared across all
    workflows: CMEMS downloads with ``--skip-existing`` are therefore only
    performed once even when several individual-comp tests run sequentially.
    """
    shutil.copytree(WOOMDIR, WOOMTMPDIR, dirs_exist_ok=True)

    jobs_dir = os.path.join(WOOMTMPDIR, "jobs")
    if os.path.exists(jobs_dir):
        shutil.rmtree(jobs_dir)
    os.chdir(WOOMTMPDIR)

    wext.load_jinja_filters(os.path.join(WOOMTMPDIR, "ext/jinja_filters.py"))

    hostmanager = whosts.HostManager()
    hostmanager.load_config(os.path.join(WOOMTMPDIR, "hosts.cfg"))
    host = hostmanager.infer_host()
    print(f"Woom inferred host: {host}")

    taskmanager = wtasks.TaskManager(host)
    taskmanager.load_config(os.path.join(WOOMTMPDIR, "tasks.cfg"))

    return taskmanager, WOOMTMPDIR
