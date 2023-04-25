from tests.uni import copy_p2_forecaster_cfg_file, init_status, change_path_p2
from armoor.tick.ticket import Ticket


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
