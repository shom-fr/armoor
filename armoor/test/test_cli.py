from armoor import cli


class TestCLI:

    def test_cli_models(self):
        ref_data = {"functionality": "sst",
                    "colocate": "auto",
                    "observation": {
                        "name": "SST L3",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc",
                        "method": "nearest"
                    },
                    "models": [{"name": "NEMO",
                                "path": '../../shared_data/example/nemo.nc',
                                "method": "nearest"},
                               {"name": "CROCO",
                                "path": '../../shared_data/example/croco.south-africa.meridional.nc',
                                "method": "linear"}],
                    "meta_zones": {"name": "Meta-zone",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)]
                                   }
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--obs-method", 'nearest',
                                             "--obs-name", "SST L3",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--mod-methods", "nearest", "linear",
                                             "--mod-name", "NEMO", "CROCO",
                                             "--polygon", "-5.8, 50.",
                                             "-4., 48.",
                                             "-7.3, 48.",
                                             "-9.5, 49.",
                                             "-9., 50.5",
                                             "-4., 51."
                                             ])
        print(ref_data == parser)
        assert ref_data == parser

    def test_cli_models_d(self):
        ref_data = {"functionality": "sst",
                    'colocate': 'observation',
                    "observation": {
                        "name": "Observation",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc"
                    },
                    "models": [{"name": "model_0", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "model_1", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}
                               ],
                    "meta_zones": {"name": "Meta-zone",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "cloud": [(-5.8, 50.), (-4., 48.),
                                             (-7.3, 48.), (-9.5, 49.),
                                             (-9., 50.5), (-4., 51.)],
                                   "radius": 1.0,
                                   "start": '2021-08-01T13:00:00',
                                   "end": "-2",
                                   "time_restriction": (20, 5),
                                   "quality": (3, 5),
                                   "vars": ["temp", "sal"]
                                   },
                    "outputs": [{"plot": "disp_diag_g",
                                 "attribute": "temp_p",
                                 "colormap": "thermal",
                                 "vmin": 10,
                                 "vmax": 15}],
                    "format": ["pdf", "html"]
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             '--colocate', 'observation',
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--meta-name", "Meta-zone",
                                             "--cloud", "-5.8, 50.", "-4., 48.",
                                             "-7.3, 48.", "-9.5, 49.",
                                             "-9., 50.5", "-4., 51.",
                                             "--polygon", "-5.8, 50.", "-4., 48.",
                                             "-7.3, 48.", "-9.5, 49.",
                                             "-9., 50.5", "-4., 51.",
                                             "--radius", "1.0",
                                             "--start", '2021-08-01T13:00:00',
                                             "--end", "-2",
                                             "--time-restriction", "20", "5",
                                             "--quality", "3", "5",
                                             "--vars", "temp", "sal",
                                             "--plot", "disp_diag_g",
                                             "--attribute", "temp_p",
                                             "--colormap", "thermal",
                                             "--vmin", "10",
                                             "--vmax", "15",
                                             "--format", "pdf", "html"
                                             ])
        print(ref_data == parser)
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(f'{parser = }')
        assert ref_data == parser

    def test_cli_models_from_configobj_2(self):
        from armoor import cli
        ref_data = {"functionality": "sst",
                    'colocate': 'auto',
                    "observation": {
                        "name": "Observation",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc"
                    },
                    "models": [{"name": "model_0", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "model_1", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}
                               ],
                    "meta_zones": {"name": "Meta-zone",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "cloud": [(-5.8, 50.), (-4., 48.),
                                             (-7.3, 48.), (-9.5, 49.),
                                             (-9., 50.5), (-4., 51.)],
                                   "start": '2021-08-01T13:00:00',
                                   "end": -2,
                                   "time_restriction": (20, 5),
                                   "quality": (3, 5)
                                   },

                    "outputs": [{"plot": "disp_diag_g", "attribute": "temp_p"},
                                {"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15},
                                {"plot": "time_series_p", "colormap": "thermal", "vmin": 10, "vmax": 15}
                                ],
                    "format": ["pdf", "html"]
                    }

        parser = cli.command_line_interface(['--file', "data/configobj/cli_2.ini"])
        print(f'{parser = }')
        print(f'{ref_data = }')
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(f'{parser = }')
        print(f'{ref_data == parser = }')
        assert ref_data == parser

    def test_cli_models_from_configobj(self):
        from armoor import cli
        ref_data = {"functionality": "sst",
                    'colocate': 'observation',
                    'output_path': '../../shared_output_data/',
                    "observation": {
                        "name": "Observation",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc",
                        "method": "nearest",
                        "method_z": "linear"
                    },
                    "models": [{"name": "model_0",
                                "path": ['../../shared_data/example/nemo.nc',
                                         '../../shared_data/example/croco.south-africa.meridional.nc'],
                                "method": "linear"},
                               {"name": "model_1",
                                "path": '../../shared_data/example/croco.south-africa.meridional.nc',
                                "method": "nearest"}
                               ],
                    "meta_zones": {"name": "Meta-zone",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "cloud": [(-5.8, 50.), (-4., 48.),
                                             (-7.3, 48.), (-9.5, 49.),
                                             (-9., 50.5), (-4., 51.)],
                                   "start": '2021-08-01T13:00:00',
                                   "end": -2,
                                   "radius": 1.0,
                                   "times": ['2021-08-01T13:00:00', '2021-08-02T13:00:00'],
                                   "time_highlight": ['2021-08-01T13:00:00', '2021-08-02T13:00:00'],
                                   "time_restriction": (20, 5),
                                   "interval": "5H",
                                   "cyclic": ["21/12", "21/03"],
                                   "quality": (3, 5),
                                   "bathy": (5, 10),
                                   "depth": [1.5],
                                   "vars": ["temp", "sal", "dens", "sndspd", "gbt", "mld", "uv"]
                                   },

                    "outputs": [{"plot": "disp_diag_g", "attribute": "temp_p"},
                                {"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15},
                                {"plot": "time_series_p", "colormap": "thermal", "vmin": 10, "vmax": 15}
                                ],
                    "format": ["pdf", "html"]
                    }

        parser = cli.command_line_interface(['--file', "data/configobj/config_read.ini"])
        print(f'{parser = }')
        print(f'{ref_data = }')
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(f'{parser = }')
        print(f'{ref_data == parser = }')
        assert ref_data == parser

    def test_cli_models(self):
        ref_data = {"functionality": "sst",
                    "colocate": "auto",
                    "observation": {
                        "name": "SST L3",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc"
                    },
                    "models": [{"name": "NEMO", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "CROCO", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}],
                    "meta_zones": {"name": "Meta-zone-default-name",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)]
                                   },
                    "outputs": [{"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15}],
                    "format": ["pdf"]
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--obs-name", "SST L3",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--mod-name", "NEMO", "CROCO",
                                             "--polygon", "-5.8, 50.",
                                             "-4., 48.",
                                             "-7.3, 48.",
                                             "-9.5, 49.",
                                             "-9., 50.5",
                                             "-4., 51.",
                                             "--format", "pdf",
                                             "--plot", "map",
                                             "--colormap", "thermal",
                                             "--vmin", "10",
                                             "--vmax", "15"
                                             ])
        print(ref_data == parser)
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(parser)
        assert ref_data == parser

    def test_cli_models_depth_1(self):
        ref_data = {"functionality": "sst",
                    "colocate": "auto",
                    "observation": {
                        "name": "SST L3",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc"
                    },
                    "models": [{"name": "NEMO", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "CROCO", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}],
                    "meta_zones": {"name": "Meta-zone-default-name",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "depth": [1.5],
                                   },
                    "outputs": [{"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15}],
                    "format": ["pdf"]
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--obs-name", "SST L3",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--mod-name", "NEMO", "CROCO",
                                             "--polygon", "-5.8, 50.",
                                             "-4., 48.",
                                             "-7.3, 48.",
                                             "-9.5, 49.",
                                             "-9., 50.5",
                                             "-4., 51.",
                                             "--depth", "1.5",
                                             "--format", "pdf",
                                             "--plot", "map",
                                             "--colormap", "thermal",
                                             "--vmin", "10",
                                             "--vmax", "15"
                                             ])
        print(ref_data == parser)
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(parser)
        assert ref_data == parser

    def test_cli_models_depth_3(self):
        ref_data = {"functionality": "sst",
                    "colocate": "auto",
                    "observation": {
                        "name": "SST L3",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc"
                    },
                    "models": [{"name": "NEMO", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "CROCO", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}],
                    "meta_zones": {"name": "Meta-zone-default-name",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "depth": [1.5, 42.0, 0.1],
                                   },
                    "outputs": [{"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15}],
                    "format": ["pdf"]
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--obs-name", "SST L3",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--mod-name", "NEMO", "CROCO",
                                             "--polygon", "-5.8, 50.",
                                             "-4., 48.",
                                             "-7.3, 48.",
                                             "-9.5, 49.",
                                             "-9., 50.5",
                                             "-4., 51.",
                                             "--depth", "1.5", "42.0", "0.1",
                                             "--format", "pdf",
                                             "--plot", "map",
                                             "--colormap", "thermal",
                                             "--vmin", "10",
                                             "--vmax", "15"
                                             ])
        print(ref_data == parser)
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(parser)
        assert ref_data == parser


    def test_cli_models_depth_3_output_path(self):
        from armoor import cli
        ref_data = {"functionality": "sst",
                    "output_path": "../../shared_output_data/",
                    "colocate": "auto",
                    "observation": {
                        "name": "SST L3",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc",
                        "method": "linear",
                        "method_z": "nearest"
                    },
                    "models": [{"name": "NEMO", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "CROCO", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}],
                    "meta_zones": {"name": "Meta-zone-default-name",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "depth": [1.5, 42.0, 0.1],
                                   "time_highlight": ['2021-08-01T13:00:00', '2021-08-02T13:00:00'],
                                   "interval": "5H"
                                   },
                    "outputs": [{"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15}],
                    "format": ["pdf"]
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             '--output-path', "../../shared_output_data/",
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--obs-name", "SST L3",
                                             "--obs-method", "linear",
                                             "--obs-method-z", "nearest",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--mod-name", "NEMO", "CROCO",
                                             "--polygon", "-5.8, 50.",
                                             "-4., 48.",
                                             "-7.3, 48.",
                                             "-9.5, 49.",
                                             "-9., 50.5",
                                             "-4., 51.",
                                             "--interval", "5H",
                                             "--time-highlight", '2021-08-01T13:00:00', '2021-08-02T13:00:00',
                                             "--depth", "1.5", "42.0", "0.1",
                                             "--format", "pdf",
                                             "--plot", "map",
                                             "--colormap", "thermal",
                                             "--vmin", "10",
                                             "--vmax", "15"
                                             ])
        print(ref_data == parser)
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(parser)
        assert ref_data == parser

    def test_cli_previous_cyclic_1(self):
        from armoor import cli
        ref_data = {"functionality": "sst",
                    "output_path": "../../shared_output_data/",
                    "colocate": "auto",
                    "observation": {
                        "name": "SST L3",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc",
                        "method": "linear",
                        "method_z": "nearest"
                    },
                    "models": [{"name": "NEMO", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "CROCO", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}],
                    "meta_zones": {"name": "Meta-zone-default-name",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "depth": [1.5, 42.0, 0.1],
                                   "cyclic": ["JFMAM"],
                                   "time_highlight": ['2021-08-01T13:00:00', '2021-08-02T13:00:00'],
                                   "interval": "5H"
                                   },
                    "outputs": [{"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15}],
                    "format": ["pdf"]
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             '--output-path', "../../shared_output_data/",
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--obs-name", "SST L3",
                                             "--obs-method", "linear",
                                             "--obs-method-z", "nearest",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--mod-name", "NEMO", "CROCO",
                                             "--polygon", "-5.8, 50.",
                                             "-4., 48.",
                                             "-7.3, 48.",
                                             "-9.5, 49.",
                                             "-9., 50.5",
                                             "-4., 51.",
                                             "--interval", "5H",
                                             "--time-highlight", '2021-08-01T13:00:00', '2021-08-02T13:00:00',
                                             "--depth", "1.5", "42.0", "0.1",
                                             "--cyclic", "JFMAM",
                                             "--format", "pdf",
                                             "--plot", "map",
                                             "--colormap", "thermal",
                                             "--vmin", "10",
                                             "--vmax", "15"
                                             ])
        print(ref_data == parser)
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(parser)
        assert ref_data == parser

    def test_cli_previous_cyclic_2(self):
        from armoor import cli
        ref_data = {"functionality": "sst",
                    "output_path": "../../shared_output_data/",
                    "colocate": "auto",
                    "observation": {
                        "name": "SST L3",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc",
                        "method": "linear",
                        "method_z": "nearest"
                    },
                    "models": [{"name": "NEMO", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "CROCO", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}],
                    "meta_zones": {"name": "Meta-zone-default-name",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "depth": [1.5, 42.0, 0.1],
                                   "cyclic": ["21/12", "21/03"],
                                   "time_highlight": ['2021-08-01T13:00:00', '2021-08-02T13:00:00'],
                                   "interval": "5H"
                                   },
                    "outputs": [{"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15}],
                    "format": ["pdf"]
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             '--output-path', "../../shared_output_data/",
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--obs-name", "SST L3",
                                             "--obs-method", "linear",
                                             "--obs-method-z", "nearest",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--mod-name", "NEMO", "CROCO",
                                             "--polygon", "-5.8, 50.",
                                             "-4., 48.",
                                             "-7.3, 48.",
                                             "-9.5, 49.",
                                             "-9., 50.5",
                                             "-4., 51.",
                                             "--interval", "5H",
                                             "--time-highlight", '2021-08-01T13:00:00', '2021-08-02T13:00:00',
                                             "--depth", "1.5", "42.0", "0.1",
                                             "--cyclic", "21/12", "21/03",
                                             "--format", "pdf",
                                             "--plot", "map",
                                             "--colormap", "thermal",
                                             "--vmin", "10",
                                             "--vmax", "15"
                                             ])
        print(ref_data == parser)
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(parser)
        assert ref_data == parser

    def test_cli_models_density_1(self):
        from armoor import cli
        ref_data = {"functionality": "sst",
                    "colocate": "auto",
                    "observation": {
                        "name": "SST L3",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc"
                    },
                    "models": [{"name": "NEMO", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "CROCO", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}],
                    "meta_zones": {"name": "Meta-zone-default-name",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "density": [1.5],
                                   },
                    "outputs": [{"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15}],
                    "format": ["pdf"]
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--obs-name", "SST L3",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--mod-name", "NEMO", "CROCO",
                                             "--polygon", "-5.8, 50.",
                                             "-4., 48.",
                                             "-7.3, 48.",
                                             "-9.5, 49.",
                                             "-9., 50.5",
                                             "-4., 51.",
                                             "--density", "1.5",
                                             "--format", "pdf",
                                             "--plot", "map",
                                             "--colormap", "thermal",
                                             "--vmin", "10",
                                             "--vmax", "15"
                                             ])
        print(ref_data == parser)
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(parser)
        assert ref_data == parser

    def test_cli_models_bathy(self):
        from armoor import cli
        ref_data = {"functionality": "sst",
                    "colocate": "auto",
                    "observation": {
                        "name": "SST L3",
                        "path": "../../shared_data/example/SST_L3MONOSENSOR.nc"
                    },
                    "models": [{"name": "NEMO", "path": '../../shared_data/example/nemo.nc'},
                               {"name": "CROCO", "path": '../../shared_data/example/croco.south-africa.meridional.nc'}],
                    "meta_zones": {"name": "Meta-zone-default-name",
                                   "polygon": [(-5.8, 50.), (-4., 48.),
                                               (-7.3, 48.), (-9.5, 49.),
                                               (-9., 50.5), (-4., 51.)],
                                   "density": [1.5],
                                   "bathy": (5, 10)
                                   },
                    "outputs": [{"plot": "map", "colormap": "thermal", "vmin": 10, "vmax": 15}],
                    "format": ["pdf"]
                    }

        parser = cli.command_line_interface(['--func', "sst",
                                             "--observation", "../../shared_data/example/SST_L3MONOSENSOR.nc",
                                             "--obs-name", "SST L3",
                                             "--models", '../../shared_data/example/nemo.nc',
                                             '../../shared_data/example/croco.south-africa.meridional.nc',
                                             "--mod-name", "NEMO", "CROCO",
                                             "--polygon", "-5.8, 50.",
                                             "-4., 48.",
                                             "-7.3, 48.",
                                             "-9.5, 49.",
                                             "-9., 50.5",
                                             "-4., 51.",
                                             "--density", "1.5",
                                             "--bathy", "5", "10",
                                             "--format", "pdf",
                                             "--plot", "map",
                                             "--colormap", "thermal",
                                             "--vmin", "10",
                                             "--vmax", "15"
                                             ])
        print(ref_data == parser)
        if ref_data != parser:
            for key, value in dict(parser).items():
                if parser[key] == ref_data[key]:
                    del parser[key]
            print(parser)
        assert ref_data == parser