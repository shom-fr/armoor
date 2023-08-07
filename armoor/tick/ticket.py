"""
Ticket class created when using gitlab
"""
import os
import sys
import pathlib

import gitlab
import requests
from xoa import cfgm

import logging
logger = logging.getLogger(__name__)

class Ticket:
    """
    Class to handle the gitlab tickets from forecaster api or from command line
    """

    def __init__(self, data=None):
        self.ticket = data
        self.gitlab_token = ''
        self.gitlab_url = ''
        self.gitlab_project_id = -1
        self.gitlab_proxies = None
        self.project = None
        self.rootdir = os.path.abspath(os.path.dirname(__file__))
        cfgm_auth = cfgm.ConfigManager(os.path.join(self.rootdir, "auth.ini"))

        current_dir = pathlib.Path().resolve()
        self.cfg_auth = cfgm_auth.load(
            os.path.join(current_dir, "auth.cfg"))

        self.try_connection_to_project()

    def try_connection_to_project(self):
        """
        Tries to connect with current authentication information
        Returns
        -------

        """
        more_info = 'More information with : armoor-tick-authentication -h'
        try:
            self.project = self.connect_to_project()
            logger.info('Connection to project : OK.')
        except gitlab.exceptions.GitlabGetError as e:
            logger.error('--- Error : Please update gitlab project id ---')
            logger.error(more_info)
            logger.error(e)
        except gitlab.exceptions.GitlabAuthenticationError as e:
            logger.error('--- Error : Please update gitlab token ---')
            logger.error(more_info)
            logger.error(e)
        except requests.exceptions.ConnectionError as e:
            logger.error('--- Error : Please update gitlab url ---')
            logger.error(more_info)
            logger.error(e)

    def connect_to_project(self):
        """
        Connection to project with url, token and project id
        Returns
        -------
            The project
        """
        self.get_gitlab_authentication_information()

        session = None
        if self.gitlab_proxies:
            session = requests.Session()
            session.proxies.update(self.gitlab_proxies)

        gitlab_project = gitlab.Gitlab(self.gitlab_url, self.gitlab_token, session=session)
        gitlab_project.auth()

        return gitlab_project.projects.get(self.gitlab_project_id)

    def get_gitlab_authentication_information(self):
        """
        Retrieve connection information and update the class attributes
        Returns
        -------

        """
        self.gitlab_token = self.cfg_auth['gitlab']['token']
        self.gitlab_url = self.cfg_auth['gitlab']['url']
        self.gitlab_project_id = self.cfg_auth['gitlab']['project']
        self.gitlab_proxies = self.cfg_auth['gitlab'].get('proxies')
        if self.gitlab_proxies:
            for proxy in self.gitlab_proxies:
                self.gitlab_proxies[proxy] = f"{self.gitlab_proxies[proxy]['address']}:{self.gitlab_proxies[proxy]['port']}"
            logger.info(f'Proxies : {self.gitlab_proxies}')

    def format_ticket_for_gitlab(self, data: dict) -> str:
        """
        Format description for gilab ticket description
        Parameters
        ----------
        data : information that will be contain in the gitlab ticket

        Returns
        -------
        Ticket description
        """
        title_column_1 = "Champ"
        title_column_2 = "Description"
        alignment = ":---"
        gitlab_ticket = f"| {title_column_1 : <20} | {title_column_2 : <100} |\n" \
                        f"| {alignment : <20} | {alignment : <100} |"
        for field in data:
            gitlab_ticket += f"\n| {field : <20} | {data[field] : <100} |"

        return gitlab_ticket

    def print_auth_info(self):
        """
        Print authentication information
        Returns
        -------
        None
        """
        print(f'token : {self.gitlab_token}')
        print(f'url : {self.gitlab_url}')
        print(f'id : {self.gitlab_project_id}')
        print(f'proxies : {self.gitlab_proxies}')

    def get_template(self, kind: str) -> dict:
        """
        Generate template with active fields
        Parameters
        ----------
        kind : kind of anomaly

        Returns
        -------
        Template
        """
        cfgm_fields = cfgm.ConfigManager(os.path.join(self.rootdir, "fields.ini"))

        kinds = {'numeric': os.path.join(self.rootdir, '..', '..', 'config', 'numeric.cfg'),
                 'nodata': os.path.join(self.rootdir, '..', '..', 'config', 'nodata.cfg'),
                 'field_value': os.path.join(self.rootdir, '..', '..', 'config', 'field_value.cfg')}
        cfg_fields = cfgm_fields.load(kinds[kind])
        cfg_fields.update({'kind': kind})

        return self.format_template(cfg_fields)

    def format_template(self, template: dict) -> dict:
        """
        Remove inactive fields from template
        Parameters
        ----------
        template

        Returns
        -------
        Formatted template
        """
        for field in template:
            if template[field] == 'inactive_field':
                template.pop(field)
        return template

    def create_ticket(self, ticket_data: dict) -> int:
        """
        Create a ticket (issue in gitlab)
        Parameters
        ----------
        ticket_data : all the information to create an issue

        Returns
        -------
        issue id of the ticket created
        """
        # title with labels and T0
        model = ticket_data.get("model" '')
        config = ticket_data.get("config", '')
        production_time = ticket_data.get("production_time", '')
        issue_title = ticket_data.get("title", '')

        title = f'{model}_{config} - '
        title += ' - '.join([production_time, issue_title])

        # retrieve linked issues
        related = ticket_data.get('related')
        if related:
            if isinstance(related, list):
                links = [f'#{link}' for link in related]
                ticket_data.update({'related': " ".join(links)})
            else:  # instance of string
                # clean the string
                for char in [',', ';', ':', '.', '/', '-', '|']:
                    related = related.replace(char, ' ')
                related = related.split()
                links = [f'#{link}' for link in related]
                ticket_data.update({'related': " ".join(links)})

        else:
            related = []

        # Create ticket
        issue = self.project.issues.create(
            {'title': title, 'description': self.format_ticket_for_gitlab(ticket_data)})

        # Create links to freshly created issue
        issue_id = issue.get_id()
        self.create_links(issue_id, related)
        return issue_id

    def search_tickets(self, config_reg, request, state='opened') -> dict:
        """
        Search for tickets
        Parameters
        ----------
        config_reg : the regional configuration
        request : input search request
        state : state off issues : opened (default), closed, all

        Returns
        -------
        Issues meeting search requirements with the following information for each issue: id, title,
        state, labels, created at, linked issues.
        """

        full_request = ' '.join([config_reg, request])

        print(f'Searching... in GitLab : {full_request}')
        tickets = self.project.search(
            gitlab.const.SearchScope.ISSUES, full_request, state=state, all=True)
        return self.format_input_issues(tickets)

    def format_input_issues(self, issues) -> dict:
        """
        Retrieve and format issue information
        Parameters
        ----------
        issues : List of issues retrieved from gitlab

        Returns
        -------
        Format issues from search
        """
        new_issues = {}
        for issue in issues:
            new_issues.update({issue['iid']: {'title': issue['title'],
                                              'state': issue['state'],
                                              'created_at': issue['created_at'][:-5],
                                              'linked_issues': self.get_links(issue['iid'])}
                               })
        return new_issues

    def get_description(self, target_id):
        """
        Get description from gitlab
        Parameters
        ----------
        target_id : issue id

        Returns
        -------
        Content of issue description
        """
        return self.project.issues.get(target_id).description

    def get_description_api(self, target_id):
        """
        Get description from gitlab for forecaster web interface
        Parameters
        ----------
        target_id : issue id

        Returns
        -------
        content of issue description formatted for the api
        """
        # Get the ticket's description
        description = self.get_description(target_id)
        # Split it into lines
        lines = description.split('\n')
        # Remove the first two lines (header and ---)
        lines = lines[2:]
        # For each line, remove the first two characters (that are '| ')
        # Then separate field and description and remove the last element which is empty
        lines = [line[2:].split('|')[:-1] for line in lines]
        # Strip the whitespaces of the field and description
        lines = [list(map(lambda word: word.strip(), line)) for line in lines]
        # Convert the list [[field0, description0], [field1, description1], ...] to
        # a list of dicts [{'field': field0, 'description': description0}, ...]
        result = [{'field': line[0], 'description': line[1]}
                  for line in lines]
        return result

        # One line version
        # return [(lambda l: {'field': l[0], 'description': l[1]})(list(map(lambda c: c.strip(),
        # field[2:].split('|')[:-1])))
        #         for field in self.project.issues.get(target_id).description.split('\n')[2:]]

    def get_links(self, target_id):
        """
        Retrieve linked issues
        Parameters
        ----------
        target_id : target issue id

        Returns
        -------
        List of related issues
        """
        target_id = self.project.issues.get(target_id)
        links = target_id.links.list()
        return [link.iid for link in links]

    def create_lincked_issue(self, target_id, link_id):
        """
        create link between two issues
        Parameters
        ----------
        target_id : target issue id
        link_id : id issue to be link to

        Returns
        -------

        """
        target = self.project.issues.get(target_id)
        link = self.project.issues.get(link_id)

        data = {
            'target_project_id': link.project_id,
            'target_issue_iid': link.iid
        }

        target.links.create(data)

    def create_links(self, target_id, id_links):
        """
        create links between a target issue and issues from a ids list
        Parameters
        ----------
        target_id : target issue id
        id_links : ids list of issue to be link to

        Returns
        -------

        """
        for link_id in id_links:
            self.create_lincked_issue(target_id, link_id)

    def format_ticket_from_cli(self, cfg_ticket_lines):
        """
        Format the ticket fields from command line
        Parameters
        ----------
        cfg_ticket_lines :

        Returns
        -------

        """
        for ticket_value in cfg_ticket_lines:
            if cfg_ticket_lines[ticket_value] is None:
                cfg_ticket_lines.pop(ticket_value)
        return cfg_ticket_lines

    def query_yes_no(self, question, default="yes"):
        """Ask a yes/no question via raw_input() and return their answer.

        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
                It must be "yes" (the default), "no" or None (meaning
                an answer is required of the user).

        The "answer" return value is True for "yes" or False for "no".
        """
        valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
        if default is None:
            prompt = " [y/n] "
        elif default == "yes":
            prompt = " [Y/n] "
        elif default == "no":
            prompt = " [y/N] "
        else:
            raise ValueError(f"invalid default answer: '{default}'")

        while True:
            sys.stdout.write(question + prompt)
            choice = input().lower()

            if default is not None and choice == "":
                return valid[default]

            if choice in valid:
                return valid[choice]

            sys.stdout.write(
                "Please respond with 'yes' or 'no' (or 'y' or 'n').\n")
