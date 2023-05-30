from tests.uni import copy_p2_forecaster_cfg_file, init_status

copy_p2_forecaster_cfg_file()
config_reg = "hycom3d_manga"

class TestTickApproval:

    def test_get_status_no_production(self):
        production_time = "20230321"
        logger, forecaster = init_status(config_reg, production_time, False)
        logger.info('test_get_status_no_production')

        assert forecaster.get_status(config_reg, production_time)['status'] == 'no_production'


    def test_get_status_not_processed(self):
        production_time = "20230322"
        logger, forecaster = init_status(config_reg, production_time)
        logger.info('test_get_status_no_production')

        assert forecaster.get_status(config_reg, production_time)['status'] == 'not_processed'


    def test_get_status_validated(self):
        production_time = "20230323"
        logger, forecaster = init_status(config_reg, production_time)
        logger.info('test_get_status_validated')

        forecaster.set_status(config_reg, production_time, 'validated', 'uni_test_reporter')

        assert forecaster.get_status(config_reg, production_time)['status'] == 'validated'


    def test_get_status_refused(self):
        production_time = "20230324"
        logger, forecaster = init_status(config_reg, production_time)
        logger.info('test_get_status_refused')

        forecaster.set_status(config_reg, production_time, 'refused', 'uni_test_reporter')

        assert forecaster.get_status(config_reg, production_time)['status'] == 'refused'

    def test_get_status_refused_protected(self):
        production_time = "20230325"
        logger, forecaster = init_status(config_reg, production_time)
        logger.info('test_get_status_refused_protected')

        forecaster.set_status(config_reg, production_time, 'refused', 'uni_test_reporter')
        forecaster.set_status(config_reg, production_time, 'validated', 'uni_test_reporter')

        assert forecaster.get_status(config_reg, production_time)['status'] == 'refused'
