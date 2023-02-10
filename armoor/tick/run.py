"""
Functions to manage gitlab issues
"""
import os
import sys
from argparse import ArgumentParser

from xoa import cfgm
import gitlab

from .ticket import Ticket


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

    cfgm_fields = cfgm.ConfigManager(os.path.join(rootdir, "config/fields_spec.ini"))

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


def show_create(ticket):
    """
    Show description of a ticket for humans
    Parameters
    ----------
    ticket : formatted ticket description

    Returns
    -------
    None
    """
    title_column_1 = "Champ"
    title_column_2 = "Description"
    line = '-'
    gitlab_ticket = f"| {title_column_1 : <20} | {title_column_2 : <100} |\n" \
                    f"| {line * 20 : <20} | {line * 100 : <100} |"
    for field in ticket:
        gitlab_ticket += f"\n| {field : <20} | {str(ticket[field]) : <100} |"
    print(gitlab_ticket)


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
    cfgm_fields = cfgm.ConfigManager(os.path.join(rootdir, "config/search_spec.ini"))

    if not argv:
        argv = sys.argv[1:]
    parser = ArgumentParser(description="Create a gitlab ticket")
    cfg_ticket_lines, _ = cfgm_fields.arg_parse(parser=parser,
                                                getargs=True,
                                                args=argv)

    ticket = Ticket()
    formated_ticket = ticket.format_ticket_from_cli(cfg_ticket_lines)

    request = formated_ticket['request']
    config = formated_ticket['config']
    state = formated_ticket['state']

    show_tickets(ticket.search_tickets(request, config, state))


def show_tickets(tickets):
    """

    Parameters
    ----------
    tickets

    Returns
    -------

    """
    if tickets == {}:
        print('No ticket found with information from above.')
    else:
        title_column_1 = "ID"
        title_column_2 = "Title"
        title_column_3 = "State"
        title_column_4 = "Created at"
        title_column_5 = "Linked issues"

        gitlab_column_title = f"| {title_column_1 : <5} " \
                              f"| {title_column_2 : <70} " \
                              f"| {title_column_3 : <6} " \
                              f"| {title_column_4 : <19} " \
                              f"| {title_column_5 : <16} |"
        print(gitlab_column_title)

        for ticket in tickets:
            gitlab_ticket = f"| {ticket:<5} " \
                            f"| {tickets[ticket]['title']:<70} " \
                            f"| {tickets[ticket]['state']:<6} " \
                            f"| {tickets[ticket]['created_at']:<19} " \
                            f"| {str(tickets[ticket]['linked_issues']):<16} |"
            print(gitlab_ticket)


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


def show_description(ticket):
    """
    Print ticket
    Parameters
    ----------
    ticket : ticket to print

    Returns
    -------
    None
    """
    print(ticket)


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
    cfgm_fields = cfgm.ConfigManager(os.path.join(rootdir, "config/auth_spec.ini"))

    if not argv:
        argv = sys.argv[1:]
    parser = ArgumentParser(description="Update gitlab authentication information")
    cfg_auth_lines, _ = cfgm_fields.arg_parse(parser=parser,
                                              getargs=True,
                                              args=argv,
                                              cfgfile=os.path.join(rootdir, "config/auth.ini"))

    formatted_cfg_auth = create_update_auth_cfg(cfg_auth_lines)
    with open(os.path.join(rootdir, "config/auth.ini"), "w", encoding="utf-8") as auth_file:
        auth_file.write("\n".join(formatted_cfg_auth))

    print('Update done')
    Ticket()


def create_update_auth_cfg(cfg_auth_lines) -> list:
    """
    Format cfg to be writen in file
    Parameters
    ----------
    cfg_auth_lines :

    Returns
    -------
    Formatted cfg file
    """
    cfg_auth = []

    for title in cfg_auth_lines:
        cfg_auth.append(f'[{title}]')
        for sub_title in cfg_auth_lines[title]:
            cfg_auth.append(f'   {sub_title} = "{cfg_auth_lines[title][sub_title]}"')

    return cfg_auth
