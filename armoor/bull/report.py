"""
Class report to generate reports
"""

import json
import os
import shutil
import tempfile

from jinja2 import Environment, FileSystemLoader
from PyPDF2 import PdfMerger
from weasyprint import HTML

import logging

logger = logging.getLogger(__name__)


class Report:
    """
    Class to handle reports
    """

    def __init__(self, output_folder_path):
        self.output_folder_path = os.path.join(output_folder_path, 'sources')
        self.rootdir = os.path.abspath(os.path.dirname(__file__))
        self.copy_logo()

        with open(os.path.join(self.output_folder_path, 'data.json'), "r", encoding="utf-8") as file:
            # returns JSON object as
            # a dictionary
            logger.info('Loading parameters from configuration file.')
            self.data_report = json.load(file)
            file.close()

    def copy_logo(self):
        """
        Copy logo from env to sources folder
        Returns
        -------
        None
        """
        src = os.path.join(self.rootdir, 'templates', 'logo_shom.png')
        logger.info(f'source logo : {src}')
        dst = os.path.join(self.output_folder_path, 'logo_shom.png')
        logger.info(f'destination logo : {dst}')
        shutil.copyfile(src, dst)

    def __format_metazone_properties(self, properties: dict, translations: dict) -> list:
        """
        Format the metazone's properties into a list of tuples
        Parameters
        ----------
        properties : the properties to format
        translations : the translations for the properties

        Returns
        ----------
        formatted_properties : the list of tuples
        """
        formatted_properties = []
        for entry in properties:
            if entry not in ['description', 'path', 'name']:
                translation = translations[entry]
                translation = translation if translation else entry
                formatted_properties.append(
                    (translation, str(properties[entry])))
        return formatted_properties

    def __generate_pdf_report(self):
        """
        Generate the report in PDF format
        """
        logger.info('Creating pdf')
        # Initialize Jinja
        loader = FileSystemLoader(self.rootdir)
        env = Environment(loader=loader)

        # Create a temporary directory in the output folder
        tmp_directory = tempfile.mkdtemp()

        # The list of temporary pdf files
        generated_pdfs = []
        generated_pdfs_func = {}

        # Generate the report index
        template = env.get_template(os.path.join('templates', 'index.html.jinja'))
        render = template.render(self.data_report)
        html = HTML(string=render, base_url=self.output_folder_path)
        output_pdf = os.path.join(tmp_directory, 'index.pdf')
        html.write_pdf(target=output_pdf)
        generated_pdfs.append(output_pdf)

        # Generate the report metazones index
        template = env.get_template(os.path.join('templates', 'index-metazones.html.jinja'))
        render = template.render(self.data_report)
        html = HTML(string=render, base_url=self.output_folder_path)
        output_pdf = os.path.join(tmp_directory, 'index-metazones.pdf')
        html.write_pdf(target=output_pdf)
        generated_pdfs.append(output_pdf)

        # Generate each metazone
        logger.info("Generate each metazone")
        for index_metazone, metazone in enumerate(self.data_report['report']['metazones']):

            meta_zone_name = metazone['properties']['name']
            logger.info(meta_zone_name)
            generated_pdfs_func.update({meta_zone_name: []})

            # Then each functionalities
            for index_functionality, functionality in enumerate(metazone['functionalities']):
                template = env.get_template(os.path.join('templates', 'functionality.html.jinja'))
                render = template.render(self.data_report,
                                         metazone=metazone,
                                         functionality=functionality
                                         )

                base_name = os.path.join(tmp_directory,
                                         f'metazone{index_metazone}functionality{index_functionality}.pdf')

                html = HTML(string=render, base_url=self.output_folder_path)
                html.write_pdf(target=base_name)
                generated_pdfs_func[meta_zone_name].append(base_name)

        # Merge the generated pdfs
        logger.info("Merge the generated pdfs")
        merger = PdfMerger()
        for pdf in generated_pdfs:
            merger.append(pdf)

        for meta_zone_name, pdf_list in generated_pdfs_func.items():
            logger.info(meta_zone_name)
            logger.info(pdf_list)
            first_time = True
            for pdf in pdf_list:
                if first_time:
                    merger.append(pdf, outline_item=str(meta_zone_name))
                    first_time = False
                else:
                    merger.append(pdf)

        merger.write(os.path.join(self.output_folder_path, '..', 'output.pdf'))
        merger.close()

    def __generate_html_report(self):
        """
        Generate the report in HTML format report
        """
        logger.info('Creating html')
        # Initialize Jinja
        loader = FileSystemLoader(self.rootdir)
        env = Environment(loader=loader)

        # Get template
        template = env.get_template(os.path.join('templates', 'raw-html.html.jinja'))

        # Render template
        render = template.render(self.data_report)

        with open(os.path.join(self.output_folder_path, '..', 'report.html'), "w", encoding="utf-8") as output:
            output.write(render)
            output.close()

    def generate_report(self):
        """
        Select type of report to be made
        Returns
        -------
        None
        """
        if self.data_report['report']['format'] == 'pdf':
            self.__generate_pdf_report()
        elif self.data_report['report']['format'] == 'html':
            self.__generate_html_report()
        elif self.data_report['report']['format'] == 'all':
            self.__generate_pdf_report()
            self.__generate_html_report()
        else:
            logger.error('Error: unexpected format')
