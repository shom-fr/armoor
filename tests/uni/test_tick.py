"""Unit tests for armoor.tick (armoor-tick GitLab issue management).

Regression coverage for update_auth_cfg: it used to render empty nested
sections (e.g. `[[proxies]]` with no configured proxy) as a bare scalar
line `proxies = "{}"`, which armoor/tick/auth.ini declares as a section,
not a scalar -- reloading such a file raised XoaValidateError and broke
every `armoor-tick-authentication` run past the first.
"""
from unittest.mock import MagicMock, patch

import gitlab
import pytest
from xoa import cfgm

from armoor.cli.tick import AUTH_INI, main_tick_description
from armoor.tick.misc import update_auth_cfg
from armoor.tick.ticket import Ticket


@pytest.fixture
def mock_project():
    """A Ticket wired to a mocked GitLab project instead of the network."""
    project = MagicMock()
    with patch.object(Ticket, "connect_to_project", return_value=project):
        yield Ticket(), project


class TestUpdateAuthCfg:

    def test_round_trips_through_validation(self, tmp_path):
        """The rendered auth.cfg must be re-loadable by the same schema."""
        cfg_auth_lines = {
            "gitlab": {"token": "TOKEN", "url": "https://gitlab.com", "project": "42", "proxies": {}}
        }
        lines = update_auth_cfg(cfg_auth_lines)
        cfgfile = tmp_path / "auth.cfg"
        cfgfile.write_text("\n".join(lines))

        cfg = cfgm.ConfigManager(AUTH_INI).load(str(cfgfile))

        assert cfg["gitlab"]["token"] == "TOKEN"
        assert cfg["gitlab"]["project"] == 42

    def test_empty_subsection_is_omitted(self):
        lines = update_auth_cfg({"gitlab": {"token": "TOKEN", "proxies": {}}})
        assert not any("proxies" in line for line in lines)

    def test_populated_subsection_is_nested_not_inlined(self, tmp_path):
        cfg_auth_lines = {
            "gitlab": {
                "token": "TOKEN",
                "proxies": {"corp": {"address": "proxy.example.com", "port": "3128"}},
            }
        }
        lines = update_auth_cfg(cfg_auth_lines)
        cfgfile = tmp_path / "auth.cfg"
        cfgfile.write_text("\n".join(lines))

        cfg = cfgm.ConfigManager(AUTH_INI).load(str(cfgfile))

        assert cfg["gitlab"]["proxies"]["corp"]["port"] == 3128


class TestTicketFormatFromCli:

    def test_drops_none_valued_fields(self, mock_project):
        ticket, _ = mock_project
        cfg = {"title": "my title", "config": None, "model": "hycom3d"}
        formatted = ticket.format_ticket_from_cli(cfg)
        assert formatted == {"title": "my title", "model": "hycom3d"}


class TestTicketCreate:

    def test_builds_title_and_description(self, mock_project):
        ticket, project = mock_project
        project.issues.create.return_value.get_id.return_value = 123

        issue_id = ticket.create_ticket({
            "title": "my title",
            "production_time": "06/03/2023",
            "config": "manga",
            "model": "hycom3d",
        })

        assert issue_id == 123
        kwargs = project.issues.create.call_args[0][0]
        assert kwargs["title"] == "hycom3d_manga - 06/03/2023 - my title"

    def test_related_list_becomes_issue_links(self, mock_project):
        ticket, project = mock_project
        project.issues.create.return_value.get_id.return_value = 1

        ticket.create_ticket({
            "title": "t", "production_time": "p", "config": "c",
            "related": [10, 11],
        })

        linked_ids = {call.args[0] for call in project.issues.get.call_args_list}
        assert linked_ids == {1, 10, 11}

    def test_missing_required_field_aborts(self, mock_project):
        ticket, _ = mock_project
        with pytest.raises(SystemExit):
            ticket.create_ticket({"title": "t"})  # no production_time/config


class TestTicketSearch:

    def test_search_tickets_formats_results(self, mock_project):
        ticket, project = mock_project
        project.search.return_value = [
            {"iid": 1, "title": "nodata issue", "state": "opened",
             "created_at": "2023-03-06T10:00:00.000Z"},
        ]
        project.issues.get.return_value.links.list.return_value = []

        results = ticket.search_tickets("med", "numeric")

        assert results[1]["title"] == "nodata issue"
        assert results[1]["created_at"] == "2023-03-06T10:00:00"
        project.search.assert_called_once_with(
            gitlab.const.SearchScope.ISSUES, "med numeric", state="opened", all=True
        )


class TestMainTickDescription:

    def test_unknown_ticket_is_reported_not_raised(self, mock_project, monkeypatch, capsys):
        _, project = mock_project
        project.issues.get.side_effect = gitlab.exceptions.GitlabGetError("not found")
        monkeypatch.setattr("sys.argv", ["armoor-tick-description", "999"])

        main_tick_description()  # must not raise

        assert "Retrieving ticket 999" in capsys.readouterr().out
