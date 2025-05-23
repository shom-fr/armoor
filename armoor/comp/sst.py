import logging
from pathlib import Path

from armoor.__init__ import ArmoorError
from armoor.comp.comp import main_comp

logger = logging.getLogger(__name__)


#% outputs

def comp(ncs, metazones, outputs):
    
    
    
    
    main_comp(ncs, metazones)