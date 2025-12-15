import base64
import os, glob
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from configobj import ConfigObj
from validate import Validator
from jinja2 import Environment, FileSystemLoader, Template

from . import BULL_TPL, SHOM_LOGO_PATH

logger = logging.getLogger(__name__)

class Bull:
    """
    Generator for ocean forecast qualification bulletins using ConfigObj and Jinja2.
    """

    def __init__(self, config, template_file: Optional[str] = BULL_TPL):
        """
        Initialize bulletin from configuration files.
        
        Args:
            config: Dict of bull configuration
            template_file: Optional custom Jinja2 template file path
        """
        self.config = config
        self.template_file = template_file
        self.date = datetime.now().strftime("%Y-%m-%d")
    
    def _encode_image_base64(self, image_path: str) -> Optional[str]:
        """Encode image to base64."""
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except FileNotFoundError:
            logger.warning(f"Image not found: {image_path}")
            return None
    
    def _prepare_template_data(self) -> Dict:
        """Prepare data dictionary for Jinja2 template."""
        # Encode logo if present
        logo_data = None
        logo_mime = None
        logo_path = SHOM_LOGO_PATH
        if os.path.exists(logo_path):
            logo_data = self._encode_image_base64(logo_path)
            ext = os.path.splitext(logo_path)[1].lower()
            logo_mime = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.svg': 'image/svg+xml',
                '.gif': 'image/gif'
            }.get(ext, 'image/png')
        
        # Process images for each comparison type and zone
        processed_images = {}
        for comp_type in self.config['comparison_types'].sections:
            processed_images[comp_type] = {}
            if 'images' in self.config and comp_type in self.config['images'].sections:
                for output in self.config['images'][comp_type].sections:
                    processed_images[comp_type][output] = {}
                    for zone in self.config['images'][comp_type][output].sections:
                        processed_images[comp_type][output][zone] = []
                        image_pathes = self.config['images'][comp_type][output][zone]['path']
                        if len(image_pathes) == 1 and "*" in image_pathes[0]:
                            image_pathes = glob.glob(image_pathes[0])
                        for image_path in image_pathes:
                            if os.path.exists(image_path):
                                image_data = self._encode_image_base64(image_path)
                                processed_images[comp_type][output][zone].append({
                                    'data': image_data,
                                    'path': image_path,
                                    'found': True
                                })
                            else:
                                processed_images[comp_type][output][zone].append({
                                    'data': None,
                                    'path': image_path,
                                    'found': False
                                })
        
        return {
            'header': {
                'title': self.config['header']['title'],
                'subtitle': self.config['header']['subtitle'],
                'period': self.config['header'].get('period'),
                'logo_data': logo_data,
                'logo_mime': logo_mime,
                'date': self.date
            },
            'summary': dict(self.config['summary']) if self.config.get("summary") else None,
            'comparison_types': dict(self.config['comparison_types']),
            'zones': dict(self.config['zones']),
            'images': processed_images
        }
    
    def generate_html(self, output_path: str = "my_bull.html") -> None:
        """Generate HTML bulletin."""
        data = self._prepare_template_data()
        template_dir = os.path.dirname(self.template_file)
        template_name = os.path.basename(self.template_file)
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template(template_name)

        html_content = template.render(**data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
        logger.info(f"HTML bulletin generated: {output_path}")
    
    def generate_pdf(self, output_path: str = "my_bull.pdf") -> None:
        """Generate PDF bulletin."""
        try:
            from weasyprint import HTML
        except ImportError:
            raise ImportError(
                "weasyprint is required for PDF generation. "
                "Install it with: pip install weasyprint"
            )
        
        temp_html = "temp_bulletin.html"
        self.generate_html(temp_html)
        HTML(temp_html).write_pdf(output_path)
        os.remove(temp_html)
        logger.info(f"PDF bulletin generated: {output_path}")