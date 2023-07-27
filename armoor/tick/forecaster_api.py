"""
Api for forecaster web interface
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ldap3 import ALL, NTLM, Connection, Server

from armoor.tick.forecaster import Forecaster
from armoor.tick.models import StatusUpdate, TicketData, User
from armoor.tick.ticket import Ticket

# api : application to launch with the forecaster web interface
app = FastAPI()

forecaster = Forecaster()
app.add_middleware(
    CORSMiddleware,
    allow_origins=forecaster.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/login/")
def login(user: User):
    """
    Login check
    Parameters
    ----------
    user : use who wants to login

    Returns
    -------
    username if authorized to login
    """
    # Check if a user is in the right group to log-in
    def is_in_authorized_group(groups):
        if isinstance(groups, str):
            groups = [groups]
        for group in groups:
            for branch in group.split(','):
                branch = branch.split('=')
                if branch[0] in ['CN', 'cn'] and branch[1] == forecaster.authorized_user_group:
                    return True
        return False

    # Get params from request
    username = user.username
    password = user.password

    # Open connection to LDAP
    server = Server(forecaster.ldap_server_url, get_info=ALL)
    connection = Connection(server=server,
                            user=f'{forecaster.domain}\\{username}',
                            password=password,
                            authentication=NTLM)
    connection.bind()

    # Check if the result of the bind is successful
    if connection.result['description'] == 'success':
        # Search for the groups to which the user belongs
        connection.search(search_base=forecaster.search_base,
                          search_filter=f'(sAMAccountName={username})',
                          attributes=['memberOf'])
        # Check if the user is not in the authorized group
        if not is_in_authorized_group(connection.entries[0].memberOf.value):
            raise HTTPException(status_code=403,
                                detail='Not authorized')
    else:
        raise HTTPException(status_code=403,
                            detail='Not authorized')

    # The user is authorized to login
    return {'username': username}


@app.get("/ping/")
async def ping():
    """
    Check if the api is running
    Returns
    -------
    message response
    """
    return 'pong'


@app.post("/create/")
async def create(ticket_data: TicketData) -> str:
    """
    Create a ticket (issue in gitlab)
    Parameters
    ----------
    ticket_data : all the information to create an issue

    Returns
    -------

    """
    issue_id = Ticket().create_ticket(ticket_data.info)
    return f"Ticket created {issue_id}"


@app.get("/get_template/")
async def get_template(ticket_kind: str):
    """
    Retrieve the template of af ticket before creating one
    Parameters
    ----------
    ticket_kind : kind of the ticket, can be either numeric, nodata or field_value

    Returns
    -------
    The template of the selected kind of issue
    """
    return Ticket().get_template(ticket_kind)


@app.get("/search_tickets/")
async def search_tickets(config_reg: str, request: str, state: str) -> dict:
    """
    Search for tickets
    Parameters
    ----------
    config_reg : the regional configuration
    request : an input search request
    state: the state of the tickets wanted ('opened' | 'closed' | 'all')

    Returns
    -------
    A dictionary of the resulting search tickets
    """
    return Ticket().search_tickets(config_reg,
                                   request,
                                   state)


@app.get("/get_description/")
async def get_description(issue_id: str) -> list:
    """
    Get ticket description
    Parameters
    ----------
    issue_id : ticket id of the issue

    Returns
    -------
    Description of the issue
    """
    return Ticket().get_description_api(issue_id)


@app.get("/get_validation_status/")
async def get_validation_status(config_reg: str, production_time: str):
    """
    Get validation status
    Parameters
    ----------
    production_time : time of production
    config_reg : the regional configuration

    Returns
    -------
    The status of the production
    """
    return forecaster.get_status(config_reg,
                                 production_time)


@app.post("/status_update/")
async def update_validation_status(status_update: StatusUpdate) -> str:
    """
    Update validation status
    Parameters
    ----------
    status_update : information needed to update the status

    Returns
    -------

    """
    forecaster.set_status(status_update.config_reg,
                          status_update.production_time,
                          status_update.status,
                          status_update.reporter
                          )

    return "Status ticket updated"
