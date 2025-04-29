"""
Api for forecaster web interface
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ldap3 import ALL, SIMPLE, Connection, Server

from armoor.cli.logger_tools import setup_logging
from armoor.tick.forecaster import Forecaster
from armoor.tick.models import StatusUpdate, TicketData, User
from armoor.tick.ticket import Ticket

setup_logging()
logger = logging.getLogger(__name__)

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
    # Get params from request
    username = user.username
    password = user.password

    # Open connection to LDAP
    server = Server(forecaster.ldap_server_url, get_info=ALL)
    logger.info("Server : OK.")
    conn = Connection(
        server=server,
        user=forecaster.ldap_bind_user,
        password=forecaster.ldap_bind_password,
        authentication=SIMPLE,
        auto_bind=True,
    )
    logger.info("Connection : OK.")

    def authenticate_user(user2authenticate, pwd):
        search_base = forecaster.search_base
        search_filter = (
            f"(&(objectClass={forecaster.ldap_user_object_class})"
            f"(memberOf={forecaster.authorized_user_group})"
            f"({forecaster.ldap_user_attribute}={user2authenticate})) "
        )

        # Search for the user in the LDAP directory
        conn.search(search_base, search_filter)

        if len(conn.entries) == 1:
            logger.info(f"{user2authenticate} in authorized group or gid")
            user_dn = conn.entries[0].entry_dn

            # Attempt to bind with the user's DN and password
            user_conn = Connection(
                server, user=user_dn, password=pwd, authentication=SIMPLE
            )
            if user_conn.bind():
                # User authenticated successfully
                logger.info("User authenticated!")
                user_conn.unbind()
                return True
            logger.info(
                "The user bind attempt failed. Most likely, the password failed."
            )

        # User authentication failed
        logger.info("User authentication failed.")
        return False

    # Check if the result of the bind is successful
    if conn.result["description"] == "success":
        logger.info(f"Successful bind with {forecaster.ldap_bind_user}")
        # Check if the user is not in the authorized group
        if not authenticate_user(username, password):
            logger.info(f"Bind failed : {username}")
            raise HTTPException(status_code=403, detail="Not authorized")
    else:
        logger.info(f"Unsuccessful bind with {forecaster.ldap_bind_user}")
        raise HTTPException(status_code=403, detail="Not authorized")

    logger.info(f"Successful bind : {username}")
    # The user is authorized to login
    conn.unbind()
    return {"username": username}


@app.get("/ping/")
async def ping():
    """
    Check if the api is running
    Returns
    -------
    message response
    """
    logger.info("pong")
    return "pong"


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
    logger.info("create")
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
    logger.info("get_template")
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
    logger.info("search_tickets")
    return Ticket().search_tickets(config_reg, request, state)


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
    logger.info("get_description")
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
    logger.info("get_validation_status")
    return forecaster.get_status(config_reg, production_time)


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
    logger.info("update_validation_status")
    forecaster.set_status(
        status_update.config_reg,
        status_update.production_time,
        status_update.status,
        status_update.reporter,
    )

    return "Status ticket updated"
