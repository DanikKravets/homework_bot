class APINot200(Exception):
    """Response code must be equal too 200."""

    pass


class APIRequestError(Exception):
    """Error within request to API."""

    pass
