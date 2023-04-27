"""
Functions to manage gitlab issues
"""
import os
import sys
import pathlib
from argparse import ArgumentParser

from xoa import cfgm
import gitlab

from .ticket import Ticket


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
    current_dir = pathlib.Path().resolve()
    cfgm_fields = cfgm.ConfigManager(os.path.join(rootdir, "auth.ini"))

    if not argv:
        argv = sys.argv[1:]
    parser = ArgumentParser(description="Update gitlab authentication information")
    cfg_auth_lines, _ = cfgm_fields.arg_parse(parser=parser,
                                              getargs=True,
                                              args=argv,
                                              cfgfile=os.path.join(current_dir, "auth.cfg"))

    formatted_cfg_auth = create_update_auth_cfg(cfg_auth_lines)
    with open(os.path.join(current_dir, "auth.cfg"), "w", encoding="utf-8") as auth_file:
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
