"""
Objects for the forecaster api
"""
from pydantic import BaseModel


class User(BaseModel):
    """
    Parameters
    ----------
    username : username
    username : password
    """
    username: str
    password: str


class TicketData(BaseModel):
    """
    Parameters
    ----------
    info : all the information to create an issue
    """
    info: dict


class Production(BaseModel):
    """
    Parameters
    ----------
    config_reg : regional configuration selected
    """
    config_reg: str


class StatusInfo(Production):
    """
    Parameters
    ----------
    production_time : time of production
    """
    production_time: str


class StatusUpdate(StatusInfo):
    """
    Parameters
    ----------
    reporter : who update the status
    status : status to update to, can be either no_production, not_processed, validated or refused
    """
    reporter: str
    status: str
