#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Armoor-bull-report executable script
"""

import sys
import os

THIS_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(THIS_DIR)

sys.path.insert(0, ROOT_DIR)
from armoor.bull.run_script import only_report as main


if __name__ == '__main__':
    main()
