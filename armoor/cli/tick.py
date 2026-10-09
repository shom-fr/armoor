"""Command-line interface for armoor-tick.

Create, search, read and authenticate against GitLab issues ("tickets")
used to report and track anomalies found in armoor comparison outputs.
"""

import logging
import os
import pathlib
from argparse import ArgumentParser

import gitlab
from xoa import cfgm

import armoor.tick as _tick_pkg
from armoor.io import ArmoorArgumentHelpFormatter
from armoor.cli.log import add_logging_parser_arguments, main_setup_logging
from armoor.tick.misc import (
    show_create,
    show_description,
    show_tickets,
    update_auth_cfg,
)
from armoor.tick.ticket import Ticket

logger = logging.getLogger(__name__)

_TICKDIR = os.path.dirname(_tick_pkg.__file__)
FIELDS_INI = os.path.join(_TICKDIR, "fields.ini")
SEARCH_INI = os.path.join(_TICKDIR, "search.ini")
AUTH_INI = os.path.join(_TICKDIR, "auth.ini")


def main_tick_create() -> None:
    """Create a GitLab ticket from the command line."""
    cfgm_fields = cfgm.ConfigManager(FIELDS_INI)

    parser = ArgumentParser(
        description="Create a GitLab ticket.",
        formatter_class=ArmoorArgumentHelpFormatter,
    )
    add_logging_parser_arguments(parser)
    cfg_ticket_lines, args = cfgm_fields.arg_parse(parser=parser, getargs=True)
    main_setup_logging(args)

    extra_keys = set(cfg_ticket_lines.keys()).difference(cfgm_fields.defaults.dict().keys())
    if extra_keys:
        print("Ticket aborted")
        print(f"armoor-tick-create: error: unrecognized arguments in cfgfile: {extra_keys}")
        return

    ticket = Ticket()
    formatted_ticket = ticket.format_ticket_from_cli(cfg_ticket_lines)

    show_create(formatted_ticket)
    if ticket.query_yes_no("Do you want to create a ticket with the information above ?"):
        issue_id = ticket.create_ticket(formatted_ticket)
        print(f"Ticket created : {issue_id}")
    else:
        print("Ticket aborted")


def main_tick_search() -> None:
    """Search for GitLab tickets from the command line."""
    cfgm_fields = cfgm.ConfigManager(SEARCH_INI)

    parser = ArgumentParser(
        description="Search for GitLab tickets.",
        formatter_class=ArmoorArgumentHelpFormatter,
    )
    add_logging_parser_arguments(parser)
    cfg_ticket_lines, args = cfgm_fields.arg_parse(parser=parser, getargs=True, cfgfileopt=False)
    main_setup_logging(args)

    ticket = Ticket()
    formatted_ticket = ticket.format_ticket_from_cli(cfg_ticket_lines)

    request = formatted_ticket.get("request", "")
    config = formatted_ticket.get("config", "")
    state = formatted_ticket.get("state", "opened")

    show_tickets(ticket.search_tickets(config, request, state))


def get_parser_tick_description() -> ArgumentParser:
    """Get parser for retrieving a ticket description."""
    parser = ArgumentParser(
        description="Retrieve a GitLab ticket description.",
        formatter_class=ArmoorArgumentHelpFormatter,
    )
    add_logging_parser_arguments(parser)
    parser.add_argument(
        'issue_id', type=int, help="Id of the ticket to retrieve the description of."
    )
    return parser


def main_tick_description() -> None:
    """Retrieve a ticket description from GitLab."""
    parser = get_parser_tick_description()
    args = parser.parse_args()
    main_setup_logging(args)

    ticket = Ticket()
    print(f"Retrieving ticket {args.issue_id} description from GitLab.")
    try:
        show_description(ticket.get_description(args.issue_id))
    except gitlab.exceptions.GitlabGetError as e:
        logger.error(
            f"GitlabGetError : An error occurred while retrieving ticket number {args.issue_id}."
        )
        logger.error("Most common error caused by a ticket that does not exist.")
        logger.error(e)


def get_parser_tick_authentication_info() -> ArgumentParser:
    """Get parser for displaying the GitLab authentication information."""
    parser = ArgumentParser(
        description="Display the GitLab authentication information.",
        formatter_class=ArmoorArgumentHelpFormatter,
    )
    add_logging_parser_arguments(parser)
    return parser


def main_tick_authentication_info() -> None:
    """Display the GitLab authentication information."""
    parser = get_parser_tick_authentication_info()
    args = parser.parse_args()
    main_setup_logging(args)

    Ticket().print_auth_info()


def main_tick_authentication() -> None:
    """Update the GitLab authentication information."""
    cfgm_fields = cfgm.ConfigManager(AUTH_INI)
    current_dir = pathlib.Path().resolve()

    parser = ArgumentParser(
        description="Update the GitLab authentication information.",
        formatter_class=ArmoorArgumentHelpFormatter,
    )
    add_logging_parser_arguments(parser)
    cfg_auth_lines, args = cfgm_fields.arg_parse(
        parser=parser,
        getargs=True,
        cfgfile=os.path.join(current_dir, "auth.cfg"),
    )
    main_setup_logging(args)

    formatted_cfg_auth = update_auth_cfg(cfg_auth_lines)
    with open(os.path.join(current_dir, "auth.cfg"), "w", encoding="utf-8") as auth_file:
        auth_file.write("\n".join(formatted_cfg_auth))

    print("Update done")
    Ticket()
