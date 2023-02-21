"""
Forecaster class created when using the forecasting web interface
"""
import os
import json

from datetime import datetime
import pytz

from xoa import cfgm


class Forecaster:
    """
    Class to handle approvals and configuration file for the forecast web interface
    """

    def __init__(self):
        self.approval_path = ''
        self.origins = []
        self.ldap_server_url = ''
        self.domain = ''
        self.search_base = ''
        self.authorized_user_group = ''

        rootdir = os.path.abspath(os.path.dirname(__file__))
        cfgm_forecaster = cfgm.ConfigManager(os.path.join(rootdir, "../../config/tick/forecaster_spec.ini"))
        self.cfg_forecaster = cfgm_forecaster.load(os.path.join(rootdir, "../../config/tick/forecaster.cfg"))
        self.initialization()

    def initialization(self):
        """
        Initializing class attributes from configuration file : forecaster.cfg
        Returns
        -------
        None
        """
        self.approval_path = self.cfg_forecaster['approval_path']
        self.origins = self.cfg_forecaster['origins']
        self.ldap_server_url = self.cfg_forecaster['ldap_server_url']
        self.domain = self.cfg_forecaster['domain']
        self.search_base = self.cfg_forecaster['search_base']
        self.authorized_user_group = self.cfg_forecaster['authorized_user_group']

    def get_status(self, config_reg, production_time) -> dict:
        """
        This function retrieves the status of approbation of a given model and production time.
        The status can be one of the four states :
            - no_production : something went wrong during the production of the regional parameters
            - not_processed : nothing has be done yet (no feedback)
            - refused : the production of the model at this time is not satisfactory
            - validated : the production of the model at this time is satisfactory
        Parameters
        ----------
        config_reg : regional configuration
        production_time : time of production

        Returns
        -------
        status of the approbation
        """
        status = {"status": "no_production", "last_update": "", "reporter": ""}
        approbation_file = f'{self.approval_path}/{config_reg}_{production_time}/data.json'

        if os.path.isfile(approbation_file):
            status = self.read_status(approbation_file)

        return status

    def set_status(self, config_reg, production_time, new_status, reporter):
        """
        Set the status of the regional configuration at a production time
        Parameters
        ----------
        config_reg : regional configuration
        production_time : time of production
        new_status : status to update to
        reporter : who update the status

        Returns
        -------
        None
        """
        approbation_file = f'{self.approval_path}/{config_reg}_{production_time}/data.json'

        protected_status = ['validated', 'refused']
        old_status = self.get_status(config_reg, production_time)['status']
        status_not_protected = old_status not in protected_status

        production_exist = os.path.isfile(approbation_file)

        if production_exist and status_not_protected:
            self.write_status(approbation_file, new_status, reporter)

    def read_status(self, status_file_path) -> dict:
        """
        Get status information from status file
        Parameters
        ----------
        status_file_path : path to retrieve the status of the production

        Returns
        -------
        The approval status data
        """
        # Opening JSON file
        with open(status_file_path, "r", encoding="utf-8") as status_file:
            # returns JSON object as
            # a dictionary
            data = json.load(status_file)

            # Closing file
            status_file.close()
            return data['approval']

    def write_status(self, status_file_path, status, reporter):
        """
        Update status
        Parameters
        ----------
        status_file_path : Status file to update
        status : new status
        reporter : who updated the status

        Returns
        -------
        None
        """
        with open(status_file_path, "r", encoding="utf-8") as status_file:
            data = json.load(status_file)

        # new status
        data['approval']["status"] = status
        # who updated the status
        data['approval']["reporter"] = reporter
        # when was the status updated
        tz_paris = pytz.timezone('Europe/Paris')
        now = datetime.now(tz_paris)
        data['approval']["last_update"] = now.strftime("%d/%m/%Y %H:%M:%S")

        with open(status_file_path, "w", encoding="utf-8") as status_file:
            json.dump(data, status_file)
