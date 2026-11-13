# Bifrost Preflight

An AI-assisted, offline configuration checker for Bifrost. Published under Apache License 2.0 on 13 November 2026. No hackathon entry has been submitted.

An offline developer tool that checks a Bifrost `config.json` against a pinned upstream JSON Schema and selected configuration-hardening rules. It prints a redacted JSON review report and never calls a model, starts a paid service, uploads a file or changes configuration.

## Why this project

Bifrost already has budgets, provider failover, caching, a dashboard and a Mocker plugin. This prototype does not claim to implement those features. Its narrower task is checking a configuration before it leaves a developer's machine, especially hidden content retention and credential logging that can be missed when reviewing a configuration by hand.

Provisional challenge fit: Geek Room Global AI Hackathon's "Open-Source Bifrost Gateway" developer-tool category. It is not an upstream-approved contribution or proof the judges will accept this particular scope. The tool is external to the gateway, not a loaded gateway plugin.

## Developer workflow integration

Upstream Bifrost uses pre-commit with local hooks. `precommit-example.yaml` provides an opt-in local-hook configuration and `precommit_entry.py` supports multiple changed files without a shell or filename echo. It is not installed into any repository by this preparation. Five automated hook tests cover empty/defined statuses, negative signal exits, unexpected statuses, mixed signal/good results and spawn failures. A real pre-commit 4.6.2 runner was then invoked in a disposable local Git repository: good-only passed (0), and mixed-good/bypass failed (1). No user repository was changed. See `hook-integration-result.json` and `integration_hook_smoke.py`. The real upstream no-config-store example was also schema-checked with no local-profile findings; its source and report are included. This is a concrete developer-workflow integration, not a loaded gateway plugin or proof of upstream acceptance.

Sources: https://github.com/maximhq/bifrost/blob/dev/.pre-commit-config.yaml and https://github.com/maximhq/bifrost/blob/dev/examples/configs/noconfigstorenologstore/config.json

## Run

Python 3.10+ and `jsonschema==4.26.0` are required. Use a local virtual environment if installing dependencies. Do not activate billing or use a paid model.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python preflight.py examples/reference-only.json --hosted
python preflight.py examples/risky-fictional.json --hosted
python -m unittest test_preflight test_hook -v
```

Exit codes: 0 means no findings in the checked rules, 1 means review findings, 2 means invalid/unreadable/bounded-input failure. A 0 is not a security certificate. No findings implies nothing about uninspected runtime state.

Reports do not echo configuration values. Dynamic provider names and unexpected schema paths are masked. Do not upload real production configuration as a test fixture. The tool checks selected known credential locations, not every possible secret encoding or field.

`--hosted` is a review profile that requires explicit dashboard and inference authentication declarations. It does not determine network reachability. Runtime database settings, reverse proxies, SSO, environment overrides, TLS and infrastructure are not inspected. An existing deployment can be secure despite a file-only finding, or insecure despite no findings. Review actual deployment state separately.

## Implemented rules

- Pinned upstream JSON Schema validation, without printing error values.
- Inline provider key and admin-password warning.
- Content logging enabled without explicit content-disable flag.
- Hidden content retained in object storage despite dashboard suppression.
- Per-request content-storage overrides.
- Known credential/cookie headers selected for logging.
- Caller-supplied direct provider-key permission.
- Hosted-profile explicit authentication checks and bypass-route review.
- Specific governance inference-auth bypass takes precedence over the client flag; legacy bypass flagged conservatively too.
- Duplicate JSON key rejection and a 2 MB input limit.

It reads only the file explicitly passed on the command line. No home-directory scanning, account access, secret retrieval or environment-value inspection is performed.

## Verification completed

39 local automated tests passed, including schema validity of the reference fixture, malformed input, duplicates, redaction, known rules, legacy auth location and no configuration mutation. See `test-results.txt`. These are author-run tests, not a third-party security audit.

A separate local smoke test started the standard Bifrost v2.5.1 binary on `127.0.0.1`, using a temporary file-only configuration with no providers or API keys. The same configuration returned no findings and the gateway's `/health` returned HTTP 200. The process was stopped after the check. See `integration-result.json` and `integration_smoke.py`.

This proves a minimal shared configuration can be accepted by both the checker and a standard Bifrost installation. It does NOT prove runtime security analysis, loaded-plugin compatibility, inference behavior, AI capability, production readiness or challenge acceptance. No provider/inference requests were sent. The binary was downloaded through the documented Bifrost npm installer; the installer selected v2.5.1. The smoke test itself expects that exact binary path and is not a portable installer.

## Sources and attribution

Read on 12 November 2026:

- Event and challenge: https://hackculture.io/hackathons/ai-global-hackathon
- Event platform terms: https://hackculture.io/legal/terms-and-conditions
- Upstream Bifrost: https://github.com/maximhq/bifrost/
- Published schema: https://www.getbifrost.ai/schema
- Setup and local-only deployment warning: https://docs.getbifrost.ai/quickstart/gateway/setting-up
- Existing Mocker feature: https://docs.getbifrost.ai/features/plugins/mocker
- Existing plugin configuration: https://docs.getbifrost.ai/deployment-guides/config-json/plugins

The original schema snapshot has SHA256 `1075667f9c017190d96ff0feb92a0300d57e0ee6210549f9f0ff26ee564ab5e2`. GitHub's editor added a final newline on publication, so the public file has SHA256 `7665f739974e3a50cea7348338ba568e0b139469da834032ce8e5f50b8e5a558`; the parsed JSON is identical. `manifest.json` records the published file hashes. Preserve `UPSTREAM-LICENSE` for upstream Bifrost material. Bifrost is Apache-2.0 licensed. The checker source is newly prepared with AI assistance; it is not a copied Bifrost gateway or evidence that Ankush implemented it independently. The checker is licensed under Apache License 2.0; see LICENSE. Upstream attribution and licence are preserved in UPSTREAM-LICENSE.

## Additional AI-assisted review correction

The first private version missed `governance.auth_config.disable_auth_on_inference=true` when `client.enforce_auth_on_inference=true`. Additional AI-assisted review caught this false negative. The repaired version reports a specific bypass regardless of the client flag or hosted profile. Six regression cases cover modern/legacy locations, both locations together and false/no-bypass values. The published schema describes the legacy flag as deprecated/ignored, while deployment governance guidance describes specific overrides. Legacy bypass is conservatively reported rather than treated as safe. This does not resolve actual runtime behavior for every version.

Source: https://docs.getbifrost.ai/deployment-guides/config-json/governance.md

## Status and limitations

This is an external developer-tool prototype, not an upstream-approved Bifrost contribution or a production security audit. Additional AI-assisted code checks were used; no independent human security review is claimed. An editable pitch deck has been prepared separately and is not part of this source publication.

Challenge acceptance, required community membership and final submission remain separate from this public code release. No provider keys, private configurations or credentials should be committed. Broader version coverage and testing against public, non-secret fixtures would strengthen the tool.

Current inspected event deadline: 15 November 2026, 23:59 IST. Registration is separate from project submission. No final submission has been made.

The hook normalizes signal exits and any status outside checker-defined 0/1/2 to failure status 2. Additional AI-assisted review caught and prompted repair of an earlier negative-signal fail-open bug; the signal regression is included.
