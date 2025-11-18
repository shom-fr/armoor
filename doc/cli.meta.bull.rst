.. _clibull:

Commandeline interfaces for generating bulletin
###############################################

Configuration file
------------------

    Armoor executables dedicated to generate bull has to be associated with a configuration file based on `bull.ini`:
        .. literalinclude:: ../armoor/cli/bull.ini
               :language: ini

.. argparse::
    :module: armoor.cli.main
    :func: get_parser_bull
    :prog: armoor-bull
    :nosubcommands:


:download:`Example of a basic html bull <_static/bull.html>` — `See html <_static/bull.html>`_

:download:`Example of a basic pdf bull <_static/bull.pdf>` — `See pdf <_static/bull.pdf>`_

