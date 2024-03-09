class ParserFindTagException(Exception):
    """
    Exception for when parser can't find a specified HTML tag.

    Indicates parsing process halt due to the absence of an expected tag,
    possibly requiring alternative parsing strategies or error handling.
    """

    pass
