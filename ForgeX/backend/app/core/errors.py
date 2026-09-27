"""Domain exceptions → standard API error format (architecture §06)."""
from __future__ import annotations

from typing import Any


class ForgeXError(Exception):
    code = "INTERNAL_ERROR"
    status = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if status:
            self.status = status
        if code:
            self.code = code


class AuthError(ForgeXError):
    code, status = "UNAUTHENTICATED", 401


class AccountDisabled(ForgeXError):
    code, status = "ACCOUNT_DISABLED", 403


class PermissionDenied(ForgeXError):
    code, status = "FORBIDDEN", 403


class PolicyDenied(ForgeXError):
    code, status = "POLICY_DENIED", 403


class NotFound(ForgeXError):
    code, status = "NOT_FOUND", 404


class Conflict(ForgeXError):
    code, status = "CONFLICT", 409


class ValidationError(ForgeXError):
    code, status = "VALIDATION_ERROR", 422


class FqlParseError(ValidationError):
    code = "FQL_PARSE_ERROR"


class ScriptValidationError(ValidationError):
    code = "SCRIPT_VALIDATION_ERROR"


class RateLimited(ForgeXError):
    code, status = "RATE_LIMITED", 429


class ExecutionTimeout(ForgeXError):
    code, status = "EXECUTION_TIMEOUT", 504


class SandboxViolation(ForgeXError):
    code, status = "SANDBOX_VIOLATION", 403


class EvidenceUnavailable(ForgeXError):
    code, status = "EVIDENCE_UNAVAILABLE", 410


class UnsupportedArtifact(ForgeXError):
    code, status = "UNSUPPORTED_ARTIFACT", 415


class ParserError(ForgeXError):
    code, status = "PARSER_ERROR", 422


class AiProcessingError(ForgeXError):
    code, status = "AI_PROCESSING_FAILED", 502


class TargetUnreachable(ForgeXError):
    code, status = "TARGET_UNREACHABLE", 503


class DatabaseError(ForgeXError):
    code, status = "DATABASE_FAILURE", 500
