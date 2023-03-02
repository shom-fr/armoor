from setuptools import find_namespace_packages, setup
# test
setup(
    name='armoor',
    packages=['armoor',
              'armoor/base',
              'armoor/algo',
              'armoor/bull',
              'armoor/cli',
              'armoor/hmi',
              'armoor/tick',
              'tests',
              'bin',
              'config'],

    package_dir={'armoor': 'armoor',
                 'armoor/base': 'armoor/base',
                 'armoor/algo': 'armoor/algo',
                 'armoor/bull': 'armoor/bull',
                 'armoor/cli': 'armoor/cli',
                 'armoor/hmi': 'armoor/hmi',
                 'armoor/tick': 'armoor/tick',
                 'tests': 'tests',
                 'bin': 'bin',
                 'config': 'config'
                 },
    package_data={'armoor': ['cli/code_text.json',
                             'bull/templates/index.html.jinja',
                             'bull/templates/index-metazones.html.jinja',
                             'bull/templates/functionality.html.jinja',
                             'bull/templates/metazone.html.jinja',
                             'bull/templates/raw-html.html.jinja',
                             'bull/templates/logo_shom.png',
                             'bull/bull.ini'
                             ],
                  'config' : ['log.cfg',
                              'cf.cfg',
                             'cli/cli.ini',
                             'hmi/hmi.ini',
                             'tick/auth.ini',
                             'tick/fields.ini',
                             'tick/search.ini',
                             'tick/forecaster.ini',
                             'numeric.cfg',
                             'nodata.cfg',
                             'field_value.cfg',
                             'forecaster.cfg'],
                  'bin' : ['armoor',
                           'armoor-tick-create',
                           'armoor-tick-search',
                           'armoor-tick-description',
                           'armoor-tick-authentication-info',
                           'armoor-tick-authentication',
                           'armoor-script',
                           'armoor-bull',
                           'armoor-bull-report',
                           'armoor-api']},
    include_package_data=True,
    version='0.0.3',
    description='armoor lib SHOM',
    author='Noveltis',
    license='MIT to define',
    install_requires=['xoa',
                      'python-gitlab'],

    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    test_suite='armoor',
    entry_points={
        'console_scripts': [
            'armoor = armoor.cli.run:main',
            'armoor2 = armoor.cli.run:main_2',
            'armoor-tick-create = armoor.tick.run:create',
            'armoor-tick-search = armoor.tick.run:search',
            'armoor-tick-description = armoor.tick.run:description',
            'armoor-tick-authentication-info = armoor.tick.run:authentication_info',
            'armoor-tick-authentication = armoor.tick.run:authentication_update',
            'armoor-script = armoor.hmi.run_script:main',
            'armoor-bull = armoor.bull.run_script:main',
            'armoor-bull-report = armoor.bull.run_script:only_report',
            'armoor-api = armoor.tick.forecaster_api:app'
        ]
    },
)

# Running tests :
# Run python setup.py pytest

# Deploying lib from whl file located in \armoor\dist directory
# Run python -m build on root where setup.py is.
# install armoor lib with pip install armoor-version-py3-none-any.whl on a new env
# Then you can run : armoor --file example.ini
