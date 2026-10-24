# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub:
**Security → Report a vulnerability** on this repository. Don't open a public issue or pull
request for one.

Include what's affected (the API, the playground, the image or the Helm chart), how to
reproduce it, and what an attacker could do with it. You'll get a reply within a week, and
a fix or a plan once the report is confirmed. Reporters are credited in the advisory
unless they'd rather not be.

## Supported versions

Only the latest `main` is supported. Fixes are released by merging to `main`, which
publishes a new signed image.

## Scope

In scope:

- the service in `src/` and its API;
- the playground in `web/`;
- the container image built from `docker/Dockerfile`;
- the Helm chart in `chart/`;
- the CI and release workflows in `.github/`.

Out of scope:

- **Bugs in Stockfish itself.** Report those to the
  [Stockfish project](https://github.com/official-stockfish/Stockfish).
- **Load and denial-of-service testing against the hosted service.** Run the image
  yourself for that; see the README.
- **Reports from automated scanners** with no demonstrated impact.

## Verifying a release

Every published image is signed with cosign (keyless, by `images.yml` on `main`) and
carries an SBOM and SLSA provenance. "Releases" in the README has the `cosign verify`
command.
