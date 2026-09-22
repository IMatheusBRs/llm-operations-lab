class LabError(Exception):
    status_code = 500
    code = "internal_error"
    retryable = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code


class AuthenticationError(LabError):
    status_code = 401
    code = "invalid_api_key"


class ModelNotAllowedError(LabError):
    status_code = 403
    code = "model_not_allowed"


class RateLimitError(LabError):
    status_code = 429
    code = "rate_limit_exceeded"
    retryable = True


class ConcurrencyLimitError(LabError):
    status_code = 429
    code = "concurrency_limit_exceeded"
    retryable = True


class ProviderTimeoutError(LabError):
    status_code = 504
    code = "provider_timeout"
    retryable = True


class ProviderTransientError(LabError):
    status_code = 502
    code = "provider_transient_error"
    retryable = True


class ProviderPermanentError(LabError):
    status_code = 502
    code = "provider_error"


class PromptNotFoundError(LabError):
    status_code = 400
    code = "prompt_version_not_found"


class PurchaseOrderNotFoundError(LabError):
    status_code = 404
    code = "purchase_order_not_found"


class PurchaseOrderAdapterError(LabError):
    status_code = 502
    code = "purchase_order_adapter_error"
    retryable = True
