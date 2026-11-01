"""Application errors translated at the HTTP boundary."""


class AppError(Exception):
    def __init__(self, code, message, status=409, retryable=False):
        super().__init__(message)
        self.code, self.status, self.retryable = code, status, retryable
