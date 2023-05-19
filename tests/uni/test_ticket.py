from tests.uni import copy_p2_forecaster_cfg_file, init_status, change_path_p2, get_auth_spec
from armoor.tick.ticket import Ticket
import pytest
import time

pytest.ticket_issue_id = -1

class TestTicket:

    def test_get_template_numeric(self):
        logger = change_path_p2()
        logger.info('test_get_template_numeric')
        ticket = Ticket()
        numeric = {'kind': 'numeric',
                   'reporting_level': '100',
                   'title': None,
                   'production_time': None,
                   'comment': None,
                   'reporter': None,
                   'model': None,
                   'related': None,
                   'version': None,
                   'config': None,
                   'hpc': None,
                   'lon': None,
                   'lat': None,
                   'depth': None,
                   'time': None,
                   'standard_name': None,
                   'src_file': None,
                   'blocking': None}

        numeric_template = ticket.get_template("numeric")

        logger.info(f'numeric :: {numeric_template}')

        assert numeric_template == numeric

    def test_get_template_nodata(self):
        logger = change_path_p2()
        logger.info('test_get_template_nodata')
        ticket = Ticket()
        nodata = {'kind': 'nodata',
                  'title': None,
                  'production_time': None,
                  'comment': None,
                  'reporter': None,
                  'reporting_level': None,
                  'model': None,
                  'related': None,
                  'version': None,
                  'config': None,
                  'hpc': None,
                  'lon': None,
                  'lat': None,
                  'depth': None,
                  'time': None,
                  'standard_name': None,
                  'blocking': None}

        nodata_template = ticket.get_template("nodata")

        logger.info(f'nodata :: {nodata_template}')

        assert nodata_template == nodata

    def test_get_template_field_value(self):
        logger = change_path_p2()
        logger.info('test_get_template_field_value')
        ticket = Ticket()
        field_value = {'kind': 'field_value',
                       'title': None,
                       'production_time': None,
                       'comment': None,
                       'reporter': None,
                       'reporting_level': None,
                       'model': None,
                       'related': None,
                       'version': None,
                       'config': None,
                       'hpc': None,
                       'lon': None,
                       'lat': None,
                       'depth': None,
                       'time': None,
                       'standard_name': None,
                       'delta_clim': None,
                       'clim_value': None,
                       'clim_name': None,
                       'blocking': None}

        field_value_template = ticket.get_template("field_value")

        logger.info(f'field_value :: {field_value_template}')

        assert field_value_template == field_value

    def test_connect_to_project(self):
        cfgm_auth = get_auth_spec()

        logger = change_path_p2()
        logger.info('test_connect_to_project')


        auth = cfgm_auth.load("auth.cfg")

        logger.info(f'auth from local auth.cfg :: {auth["gitlab"]["project"]}')

        ticket = Ticket()

        object_ticket = ticket.connect_to_project()

        logger.info(f"id project from gitlab server object :: {object_ticket.__dict__['_attrs']['id']}")

        assert object_ticket.__dict__['_attrs']['id'] == auth["gitlab"]["project"]

    def test_create_ticket(self):
        logger = change_path_p2()
        logger.info('test_create_ticket')

        formatted_ticket = {'title': 'Test unitaire : gestion des anomalies',
                            'kind': 'nodata',
                            'production_time': '25/04/2023',
                            'comment': 'Ceci est un commentaire dans le ticket gitlab',
                            'reporter': 'test_create_ticket',
                            'reporting_level': '0',
                            'model': 'hycom3d',
                            'version': 'v1.2',
                            'config': 'med',
                            'lon': '72.0, 73.0',
                            'lat': '5.7, 5.8',
                            'depth': '123.123',
                            'time': '22/11/2022 09:02:00',
                            'standard_name': 'uv',
                            'blocking': 'False'}


        ticket = Ticket()
        issue_id = ticket.create_ticket(formatted_ticket)
        pytest.ticket_issue_id = issue_id

        logger.info(f'issue_id :: {issue_id}')

        assert isinstance(issue_id, int)

    def test_search_tickets(self):
        logger = change_path_p2()
        logger.info('test_search_tickets')

        time.sleep(60)

        ticket = Ticket()

        config = 'hycom3d_med'
        request = 'Test unitaire : gestion des anomalies'
        out_search = ticket.search_tickets(config, request)

        logger.info(f'output with config : {config} and request : {request} :: {out_search}')
        logger.info(f'out_search only issue {pytest.ticket_issue_id} :: {out_search[pytest.ticket_issue_id]}')

        assert out_search[pytest.ticket_issue_id]['title'] == 'hycom3d_med - 25/04/2023 - Test unitaire : gestion des anomalies'

    def test_get_description(self):
        logger = change_path_p2()
        logger.info('test_search_tickets')

        description_expected = f'| Champ                | Description                                                                                          |\n'\
                               f'| :---                 | :---                                                                                                 |\n'\
                               f'| title                | Test unitaire : gestion des anomalies                                                                |\n'\
                               f'| kind                 | nodata                                                                                               |\n'\
                               f'| production_time      | 25/04/2023                                                                                           |\n'\
                               f'| comment              | Ceci est un commentaire dans le ticket gitlab                                                        |\n'\
                               f'| reporter             | test_create_ticket                                                                                   |\n'\
                               f'| reporting_level      | 0                                                                                                    |\n'\
                               f'| model                | hycom3d                                                                                              |\n'\
                               f'| version              | v1.2                                                                                                 |\n'\
                               f'| config               | med                                                                                                  |\n'\
                               f'| lon                  | 72.0, 73.0                                                                                           |\n'\
                               f'| lat                  | 5.7, 5.8                                                                                             |\n'\
                               f'| depth                | 123.123                                                                                              |\n'\
                               f'| time                 | 22/11/2022 09:02:00                                                                                  |\n'\
                               f'| standard_name        | uv                                                                                                   |\n'\
                               f'| blocking             | False                                                                                                |'

        ticket = Ticket()
        description = ticket.get_description(pytest.ticket_issue_id)

        logger.info(f'description {pytest.ticket_issue_id} :: {description}')

        print(f'description :: {description}')

        assert description == description_expected

    def test_get_links(self):
        logger = change_path_p2()
        logger.info('test_get_links')

        formatted_ticket = {'title': 'Test unitaire : gestion des anomalies',
                            'kind': 'nodata',
                            'production_time': '25/04/2023',
                            'comment': 'Ceci est un commentaire dans le ticket gitlab',
                            'reporter': 'test_create_ticket',
                            'reporting_level': '0',
                            'model': 'hycom3d',
                            'related' : [pytest.ticket_issue_id],
                            'version': 'v1.2',
                            'config': 'med',
                            'lon': '72.0, 73.0',
                            'lat': '5.7, 5.8',
                            'depth': '123.123',
                            'time': '22/11/2022 09:02:00',
                            'standard_name': 'uv',
                            'blocking': 'False'}


        ticket = Ticket()
        issue_id = ticket.create_ticket(formatted_ticket)

        links = ticket.get_links(issue_id)
        logger.info(f'links :: {links}')

        assert links == [pytest.ticket_issue_id]
