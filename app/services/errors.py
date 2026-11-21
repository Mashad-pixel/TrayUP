class OrderError(Exception):
    """Raised for expected, user-facing order failures.

    The route layer turns this into the standard error response:
    {"success": false, "message": ..., "error": {"code": ...}}
    """

    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
