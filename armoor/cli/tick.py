import os
import sys
import pathlib

from argparse import ArgumentParser
import gitlab

from xoa import cfgm

from armoor.tick.ticket import Ticket
from armoor.tick.misc import show_create, show_tickets, show_description, update_auth_cfg


def create(argv=None):
    """
    Create a gitlab ticket from command line
    Parameters
    ----------
    argv : command line parameters

    For more information use : armoor-tick-create -h

    Returns
    -------
    None
    """
    rootdir = os.path.abspath(os.path.dirname(__file__))

    cfgm_fields = cfgm.ConfigManager(os.path.join(rootdir, "..", "tick", "fields.ini"))

    if not argv:
        argv = sys.argv[1:]

    parser = ArgumentParser(description="Create a gitlab ticket")
    cfg_ticket_lines, _ = cfgm_fields.arg_parse(parser=parser,
                                                getargs=True,
                                                args=argv)

    ticket = Ticket()
    formatted_ticket = ticket.format_ticket_from_cli(cfg_ticket_lines)

    show_create(formatted_ticket)
    if ticket.query_yes_no('Do you want to create a ticket with the information above ?'):
        issue_id = ticket.create_ticket(formatted_ticket)
        print(f"Ticket created : {issue_id}")
    else:
        print('Ticket aborted')


def search(argv=None):
    """
    Search for gitlab ticket
    Parameters
    ----------
    argv : command line parameters

    For more information use : armoor-tick-search -h

    Returns
    -------
    None
    """
    rootdir = os.path.abspath(os.path.dirname(__file__))
    cfgm_fields = cfgm.ConfigManager(os.path.join(rootdir, "..", "tick", "search.ini"))

    if not argv:
        argv = sys.argv[1:]
    parser = ArgumentParser(description="Search for gitlab tickets")
    cfg_ticket_lines, _ = cfgm_fields.arg_parse(parser=parser,
                                                getargs=True,
                                                cfgfileopt=False,
                                                args=argv)

    ticket = Ticket()
    formated_ticket = ticket.format_ticket_from_cli(cfg_ticket_lines)

    request = formated_ticket.get('request')
    config = formated_ticket.get('config')
    state = formated_ticket.get('state')

    show_tickets(ticket.search_tickets(request, config, state))


def description():
    """
    Retrieve ticket description from gitlab
    For more information use : armoor-tick-description -h
    Returns
    -------
    None
    """
    target_id = sys.argv[1]
    try:
        target_id = int(target_id)
        ticket = Ticket()

        print(f'Retrieving ticket {target_id} description from GitLab.')
        show_description(ticket.get_description(target_id))

    except gitlab.exceptions.GitlabGetError:
        print(f'GitlabGetError : An error occurred while retrieving ticket number {target_id}.')
        print('Most common error caused by a ticket that does not exist.')
    except ValueError:
        print(f'ValueError "{target_id}" : Please enter a number to retrieve the description.')


def authentication_info():
    """
    Displays the gitlab authentication information
    Returns
    -------
    None
    """
    ticket = Ticket()
    ticket.print_auth_info()


def authentication_update(argv=None):
    """
    Update gitlab authentication information

    Parameters
    ----------
    argv : command line parameters

    For more information use : armoor-tick-authentication -h

    Returns
    -------

    """
    rootdir = os.path.abspath(os.path.dirname(__file__))
    current_dir = pathlib.Path().resolve()
    cfgm_fields = cfgm.ConfigManager(os.path.join(rootdir, "..", "tick", "auth.ini"))

    if not argv:
        argv = sys.argv[1:]
    parser = ArgumentParser(description="Update gitlab authentication information")
    cfg_auth_lines, _ = cfgm_fields.arg_parse(parser=parser,
                                              getargs=True,
                                              args=argv,
                                              cfgfile=os.path.join(current_dir, "auth.cfg"))

    formatted_cfg_auth = update_auth_cfg(cfg_auth_lines)
    with open(os.path.join(current_dir, "auth.cfg"), "w", encoding="utf-8") as auth_file:
        auth_file.write("\n".join(formatted_cfg_auth))

    print('Update done')
    Ticket()