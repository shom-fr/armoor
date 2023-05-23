from tests.int.base import change_path_bull, copy_bull_test_files

from armoor.cli.bull import main

test = 'multi'
copy_bull_test_files(test)


class TestBulletins:

    def test_multi(self):
        out_path, logger = change_path_bull(test)
        logger.info(f'Test bulletin {test}')
        main(['-o', './', '-c', 'Bulletin.cfg'])
        assert True