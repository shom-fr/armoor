from tests.int.base import change_path_bull, copy_bull_test_files

from armoor.cli.bull import main, only_report

test = 'multi'
copy_bull_test_files(test)


class TestBulletins:

    def test_multi(self):
        out_path, logger = change_path_bull(test)
        logger.info(f'Test bulletin {test}')
        main(['-o', './', '-c', 'Bulletin.cfg'])
        assert True

    def test_multi_only_report(self):
        out_path, logger = change_path_bull(test)
        logger.info(f'Test bulletin {test}')
        only_report(['-o', './', '-c', 'Bulletin.cfg'])
        assert False