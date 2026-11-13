"""Private Bifrost configuration preflight. Never starts Bifrost or calls a model."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

SCHEMA = Path(__file__).with_name('upstream-schema.json')
SAFE_PATH_KEYS = set('server client providers keys value config_store auth_config governance is_enabled enforce_auth_on_inference disable_content_logging enable_logging retain_content_in_object_storage allow_per_request_content_storage_override logging_headers allow_direct_keys whitelisted_routes admin_password plugins config path name enabled'.split())

def safe_path(parts):
    return '/' + '/'.join(str(p) if isinstance(p, int) or p in SAFE_PATH_KEYS else '*' for p in parts)

def is_reference(value):
    if isinstance(value, str):
        return value.startswith(('env.', 'vault.')) and len(value.split('.', 1)[1]) > 0
    if isinstance(value, dict):
        return (value.get('type') in ('env', 'vault') and bool(value.get('env_var') or value.get('ref') or value.get('value'))) or (value.get('from_env') is True and bool(value.get('env_var')))
    return False

def scan(config, hosted=False, schema_path=SCHEMA):
    """Returns fixed messages and sanitized paths. Does not echo configuration values."""
    import jsonschema
    schema_bytes = Path(schema_path).read_bytes()
    schema = json.loads(schema_bytes)
    issues = []
    def add(code, level, path, text):
        issues.append(dict(code=code, severity=level, location=path, message=text))
    validator = jsonschema.Draft201909Validator(schema)
    for error in validator.iter_errors(config):
        add('SCHEMA', 'error', safe_path(error.absolute_path), 'Does not match the pinned Bifrost schema. Inspect this location locally; values are omitted.')
    if not isinstance(config, dict):
        return result(issues, schema_bytes, hosted)
    # Deliberately narrow checks, not a claim to cover every credential type.
    providers = config.get('providers', {})
    if isinstance(providers, dict):
        for pi, provider in enumerate(providers.values()):
            if not isinstance(provider, dict): continue
            keys = provider.get('keys', [])
            if not isinstance(keys, list): continue
            for ki, key in enumerate(keys):
                if not isinstance(key, dict): continue
                value = key.get('value')
                if value and not is_reference(value):
                    add('INLINE_PROVIDER_KEY', 'error', f'/providers/*[{pi}]/keys/{ki}/value', 'Provider key is inline. Use a supported environment/vault reference before sharing config.')
    client = config.get('client', {})
    if not isinstance(client, dict): client = {}
    if client.get('enable_logging') is True and client.get('disable_content_logging') is not True:
        add('CONTENT_LOGGING', 'warning', '/client', 'Logging is enabled without explicitly disabling content storage. Prompts and outputs may be stored.')
    if client.get('retain_content_in_object_storage') is True:
        add('HIDDEN_CONTENT_RETENTION', 'warning', '/client/retain_content_in_object_storage', 'Content may still be retained in object storage even when dashboard content logging is disabled.')
    if client.get('allow_per_request_content_storage_override') is True:
        add('REQUEST_STORAGE_OVERRIDE', 'warning', '/client/allow_per_request_content_storage_override', 'Requests may override the global content-storage policy.')
    headers = client.get('logging_headers', [])
    if isinstance(headers, list) and any(isinstance(h, str) and h.lower() in ('authorization', 'x-api-key', 'x-bf-vk', 'cookie', 'x-goog-api-key') for h in headers):
        add('SENSITIVE_HEADER_LOGGING', 'error', '/client/logging_headers', 'Logging headers include a known credential/cookie header.')
    if client.get('allow_direct_keys') is True:
        add('DIRECT_KEYS', 'warning', '/client/allow_direct_keys', 'Callers can supply raw provider credentials. Verify this bypass of the registered key pool is intended.')
    auth = config.get('governance', {})
    auth = auth.get('auth_config', config.get('auth_config', {})) if isinstance(auth, dict) else config.get('auth_config', {})
    if not isinstance(auth, dict): auth = {}
    # Governance-specific override wins over the client default. Legacy placement is
    # conservatively flagged too: schema labels it ignored, while deployment docs
    # describe specific override precedence. Runtime version must settle ambiguity.
    legacy_auth = config.get('auth_config', {})
    if not isinstance(legacy_auth, dict): legacy_auth = {}
    modern_governance = config.get('governance', {})
    modern_auth = modern_governance.get('auth_config', {}) if isinstance(modern_governance, dict) else {}
    if isinstance(modern_auth, dict) and modern_auth.get('disable_auth_on_inference') is True:
        add('INFERENCE_AUTH_BYPASS', 'error', '/governance/auth_config/disable_auth_on_inference', 'Specific inference-auth bypass is enabled. It can override the client authentication setting.')
    if legacy_auth.get('disable_auth_on_inference') is True:
        add('LEGACY_INFERENCE_AUTH_BYPASS', 'error', '/auth_config/disable_auth_on_inference', 'Legacy inference-auth bypass is enabled. Schema and deployment guidance differ; remove the bypass and verify the pinned runtime.')
    if hosted:
        if auth.get('is_enabled') is not True:
            add('DASHBOARD_AUTH_UNCONFIRMED', 'error', '/governance/auth_config', 'Hosted profile requires explicit dashboard authentication in this file. Database, SSO and reverse-proxy state are not inspected.')
        if client.get('enforce_auth_on_inference') is not True:
            add('INFERENCE_AUTH_UNCONFIRMED', 'error', '/client/enforce_auth_on_inference', 'Hosted profile requires explicit inference authentication. Omitted values depend on deployment history.')
        if client.get('whitelisted_routes'):
            add('AUTH_BYPASS_ROUTES', 'warning', '/client/whitelisted_routes', 'Routes bypass authentication. Review them locally before hosting.')
    if auth.get('admin_password') and not is_reference(auth['admin_password']):
        add('INLINE_ADMIN_PASSWORD', 'error', '/governance/auth_config/admin_password', 'Admin password is inline. Do not share this configuration.')
    return result(issues, schema_bytes, hosted)

def result(issues, schema_bytes, hosted):
    return {'tool': 'Bifrost Preflight - private prototype', 'profile': 'hosted-review' if hosted else 'local-review',
            'schema_sha256': hashlib.sha256(schema_bytes).hexdigest(),
            'status': 'review_required' if issues else 'no_findings_in_checked_rules',
            'findings': issues,
            'limitations': ['Offline static checks only; not a security certification.', 'No runtime, database, environment variables, reverse proxy or TLS inspection.', 'Checks only selected known credential locations; not a general secret scanner.', 'No provider requests, API credits, configuration edits or uploads.']}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--hosted', action='store_true', help='Require explicit auth declarations; does not prove external reachability.')
    args = parser.parse_args()
    try:
        raw = args.config.read_bytes()
        if len(raw) > 2_000_000: raise ValueError('oversized')
        def pairs(items):
            d = {}
            for k,v in items:
                if k in d: raise ValueError('duplicate')
                d[k] = v
            return d
        cfg = json.loads(raw, object_pairs_hook=pairs)
        report = scan(cfg, args.hosted)
        print(json.dumps(report, indent=2))
        return 1 if report['findings'] else 0
    except (ValueError, OSError, RecursionError):
        # Never print the exception: JSON errors can contain secret input fragments.
        print(json.dumps({'status': 'input_error', 'message': 'Cannot read valid bounded JSON with unique keys. No input content is included.'}))
        return 2

if __name__ == '__main__':
    sys.exit(main())
