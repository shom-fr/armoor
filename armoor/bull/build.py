import base64
import os
import glob
import logging
from datetime import datetime
from typing import Dict, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import json

from . import BULL_TPL

logger = logging.getLogger(__name__)


class Bull:
    """
    Generator for ocean forecast qualification bulletins using ConfigObj and Jinja2.
    """

    def __init__(self, config, template_file: Optional[str] = BULL_TPL):
        """
        Initialize bulletin from configuration files.

        Parameters
        ----------
        config
            Dict of bull configuration
        template_file
            Optional custom Jinja2 template file path
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
        # Encode logo if one is given in [header]
        logo_data = None
        logo_mime = None
        logo_path = self.config['header'].get('logo')
        if logo_path and os.path.exists(logo_path):
            logo_data = self._encode_image_base64(logo_path)
            ext = os.path.splitext(logo_path)[1].lower()
            logo_mime = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.svg': 'image/svg+xml',
                '.gif': 'image/gif',
            }.get(ext, 'image/png')
        elif logo_path:
            logger.warning(f"Logo not found: {logo_path}")

        # Process images for each comparison type, section, output and zone
        processed_images = {}
        for comp_type in self.config['comparison_types'].sections:
            logger.debug(
                f"Comparison type {comp_type}: {dict(self.config['comparison_types'][comp_type])}"
            )
            processed_images[comp_type] = {
                "label": self._get_label(self.config['comparison_types'], comp_type),
                "sections": {},
            }

            if 'images' not in self.config:
                continue
            if comp_type not in self.config['images'].sections:
                continue
            comp_cfg = self.config['images'][comp_type]

            for section in comp_cfg.sections:
                section_cfg = comp_cfg[section]
                processed_section = processed_images[comp_type]["sections"][section] = {
                    "label": self._get_label(comp_cfg, section),
                    "outputs": {},
                }

                for output in section_cfg.sections:
                    output_cfg = section_cfg[output]
                    if 'path' in output_cfg.scalars:
                        raise ValueError(
                            f"[images] [[{comp_type}]] [[[{section}]]] [[[[{output}]]]]: "
                            "'path' found at the output level. [images] now expects "
                            "type / section / output / zone / path: add a section level "
                            "to your bull config."
                        )
                    processed_output = processed_section["outputs"][output] = {
                        "label": self._get_label(section_cfg, output),
                        "zones": {},
                    }

                    for zone in output_cfg.sections:
                        image_paths = output_cfg[zone]['path']
                        if len(image_paths) == 1 and "*" in image_paths[0]:
                            image_paths = sorted(glob.glob(image_paths[0]))

                        images_list = []
                        for image_path in image_paths:
                            if os.path.exists(image_path):
                                images_list.append(
                                    {
                                        'data': self._encode_image_base64(image_path),
                                        'path': image_path,
                                        'found': True,
                                    }
                                )
                            else:
                                logger.warning(f"Image not found : {image_path}")
                                images_list.append(
                                    {
                                        'data': None,
                                        'path': image_path,
                                        'found': False,
                                    }
                                )
                        processed_output["zones"][zone] = {
                            "label": self._get_label(output_cfg, zone),
                            "images": images_list,
                        }

        if logger.isEnabledFor(logging.DEBUG):
            images_tree = {
                k: {
                    "label": v["label"],
                    "sections": {
                        s: {"label": sd["label"], "outputs": list(sd["outputs"].keys())}
                        for s, sd in v["sections"].items()
                    },
                }
                for k, v in processed_images.items()
            }
            logger.debug("Images tree:\n" + json.dumps(images_tree, indent=2, ensure_ascii=False))

        # Process ocean-features (main ocean features per zone)
        processed_ocean_features = None
        if 'ocean-features' in self.config:
            processed_ocean_features = {}
            for zone in self.config['ocean-features'].sections:
                zone_label = self._get_label(self.config['ocean-features'], zone)
                processed_ocean_features[zone] = {"label": zone_label, "features": {}}
                for feature in self.config['ocean-features'][zone].sections:
                    feat_label = self._get_label(self.config['ocean-features'][zone], feature)
                    feat_desc = self.config['ocean-features'][zone][feature].get('description', '')
                    processed_ocean_features[zone]["features"][feature] = {
                        "label": feat_label,
                        "description": feat_desc,
                    }

        return {
            'header': {
                'title': self.config['header']['title'],
                'subtitle': self.config['header']['subtitle'],
                'period': self.config['header'].get('period'),
                'logo_data': logo_data,
                'logo_mime': logo_mime,
                'date': self.date,
            },
            'summary': dict(self.config['summary']) if self.config.get("summary") else None,
            'comparison_types': dict(self.config['comparison_types']),
            'zones': dict(self.config['zones']),
            'ocean_features': processed_ocean_features,
            'ocean_features_title': self.config.get('ocean-features', {}).get(
                'title', 'Main ocean features'
            ),
            'images': processed_images,
        }

    def generate_html(self, output_path: str = "my_bull.html") -> None:
        """Generate HTML bulletin."""
        data = self._prepare_template_data()
        template_dir = os.path.dirname(self.template_file)
        template_name = os.path.basename(self.template_file)
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=select_autoescape())
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
                "weasyprint is required for PDF generation. Install it with: pip install weasyprint"
            )

        temp_html = "temp_bulletin.html"
        self.generate_html(temp_html)
        HTML(temp_html).write_pdf(output_path)
        os.remove(temp_html)
        logger.info(f"PDF bulletin generated: {output_path}")

    def _get_label(self, section_obj, key: str) -> str:
        """Retourne le label lisible si defini, sinon la cle brute."""
        try:
            label = section_obj[key].get('label', '').strip()
            return label if label else key
        except (KeyError, AttributeError, TypeError):
            return key
