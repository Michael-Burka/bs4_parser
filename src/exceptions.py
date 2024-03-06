class ParserFindTagException(Exception):
    """
    Exception for when parser can't find a specified HTML tag.

    Indicates parsing process halt due to the absence of an expected tag,
    possibly requiring alternative parsing strategies or error handling.
    """

    pass


class NoResponse(Exception):
    """
    Exception for when no response is received by the parser.

    Signifies network or server issues preventing data retrieval. Handling
    might include request retries, incident logging, or user notifications.
    """

    pass
