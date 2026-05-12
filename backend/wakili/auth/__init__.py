"""Authentication / authorization for Verda.

Standards-first OIDC integration. The default deployment ships with Keycloak,
but the same code path verifies tokens from any RFC 8414 / OpenID Connect
discovery-compliant identity provider — Auth0, Authentik, Okta, Azure AD,
Google, AWS Cognito.

Adding a new provider is a single declarative entry in `providers.py`.

When `WAKILI_AUTH_ENABLED=false` (default), all routes pass through
anonymously. This keeps the local demo flow runnable while the user spins up
their identity provider.
"""

from .dependencies import current_user, optional_user, require_user
from .providers import OIDCProvider, list_providers, get_provider, default_provider

__all__ = [
    "current_user",
    "optional_user",
    "require_user",
    "OIDCProvider",
    "list_providers",
    "get_provider",
    "default_provider",
]
