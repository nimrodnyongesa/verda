# Changelog

All notable changes to Verda are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial open-core MVP for the Kenyan Article 22 / 23 constitutional
  petition track.
- FastAPI backend with cases, plan, generation, exports, MCP, profile,
  and audit routes.
- Next.js 16 + Tailwind v4 frontend with App Router, hand-rolled OIDC
  client, and i18n (en, sw, ar, fr, pt).
- Four generated modules: Evidence Codex, Procedural Engine, Precedent
  Linker, Defender Safety Build.
- Four exporter targets: zip, AES-256-GCM encrypted, Docker manifest,
  USB launcher.
- Three MCP servers: `kenyalaw-mcp`, `africanlii-mcp`,
  `case-knowledge-mcp` — with append-only audit log.
- Keycloak local stack with seeded demo users and branded Verda theme.
- 67-test backend suite covering modules, services, exporters, IAM,
  end-to-end sample case.
- Repository governance: AGPL-3.0 license, NOTICE, TRADEMARK policy,
  Code of Conduct, CONTRIBUTING (DCO), SECURITY (responsible disclosure),
  CODEOWNERS.
- CI: DCO sign-off enforcement, Conventional Commits title check,
  gitleaks secret scan, Dependabot for pip / npm / actions.
- Main-branch protection: PR-only, no force-push, no deletion, required
  signed commits, required conversation resolution.

### Security
- AES-256-GCM bundle encryption with scrypt KDF (N=2¹⁵, r=8, p=1) and
  constant-time tag check.
- `WAKILI1` magic header is stable — bundled `decrypt.py` stays pure
  stdlib so a defender recovers data without Verda installed.
- MCP audit log is append-only; no API to delete rows.
- OIDC: RS256 / ES256 / EdDSA, JWKS auto-rotation, `kid` matching.

## Release process

When cutting a release:

1. Move everything in `[Unreleased]` under a new `[X.Y.Z] — YYYY-MM-DD`
   heading.
2. Tag with `vX.Y.Z` on a signed annotated tag
   (`git tag -s -a vX.Y.Z -m "Release X.Y.Z"`).
3. Push the tag — a GitHub Release is created and a Security Advisory
   draft is opened for anything in the **Security** section.
4. Open a new empty `[Unreleased]` section on `main`.

Version bumps follow SemVer strictly:

- **MAJOR** — any change that breaks the bundle.json schema, the
  `WAKILI1` header, the OIDC contract, or removes a documented API.
- **MINOR** — additive features, new jurisdictions, new exporters.
- **PATCH** — bug fixes, doc updates, dependency bumps.

[Unreleased]: https://github.com/nyongesa637/verda/compare/HEAD...HEAD
