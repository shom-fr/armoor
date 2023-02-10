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
              'armoor/test',
              'config'],

    package_dir={'armoor': 'armoor',
                 'armoor/base': 'armoor/base',
                 'armoor/algo': 'armoor/algo',
                 'armoor/bull': 'armoor/bull',
                 'armoor/cli': 'armoor/cli',
                 'armoor/hmi': 'armoor/hmi',
                 'armoor/tick': 'armoor/tick',
                 'armoor/test': 'armoor/test',
                 'config': 'config'
                 },
    package_data={'armoor': ['cli/code_text.json',
                             'cli/config_spec.ini',
                             'base/cf.cfg',
                             'hmi/configuration_spec.ini',
                             'hmi/configuration.ini',
                             'tick/config/auth_spec.ini',
                             'tick/config/auth.ini',
                             'tick/config/fields_spec.ini',
                             'tick/config/numeric.ini',
                             'tick/config/nodata.ini',
                             'tick/config/field_value.ini',
                             'tick/config/search_spec.ini',
                             'tick/config/forecaster_spec.ini',
                             'tick/config/forecaster.ini',
                             'bull/bull_spec.ini',
                             'bull/templates/index.html.jinja',
                             'bull/templates/index-metazones.html.jinja',
                             'bull/templates/functionality.html.jinja',
                             'bull/templates/metazone.html.jinja',
                             'bull/templates/raw-html.html.jinja',
                             'bull/templates/logo_shom.png'
                             ],
                  'config' : ['log.ini']},
    include_package_data=True,
    version='0.0.3',
    description='armoor lib SHOM',
    author='Noveltis',
    license='MIT to define',
    install_requires=['xarray',
                      'shapely',
                      'netCDF4',
                      'matplotlib',
                      'xoa',
                      'fastapi'],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    test_suite='armoor',
    entry_points={
        'console_scripts': [
            'armoor = armoor.cli.run:main',
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
