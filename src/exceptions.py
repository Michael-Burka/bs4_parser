class ParserFindTagException(Exception):
    """Вызывается когда парсер не может найти тег"""
    pass


class NoResponse(Exception):
    """Вызывается, когда парсер не получил ответ на запрос"""

    pass
