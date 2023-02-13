#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Armoor-script executable script
"""

import sys
import os

THIS_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(THIS_DIR)

sys.path.insert(0, ROOT_DIR)
from armoor.hmi.run_script import main


if __name__ == '__main__':
    main()