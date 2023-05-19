from tests.int.base import change_path_bull, copy_bull_test_files

from armoor.bull.run_script import main

test = 'f3'
copy_bull_test_files(test)


class TestBulletins:

    def test_f3(self):
        out_path, logger = change_path_bull(test)
        logger.info(f'Test bulletin {test}')
        main(['-o', '.', '-c', 'Bulletin.ini'])
        assert True