# backend/app/config.py
import os
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(path='.env'):
        # no-op if python-dotenv isn't available; fallback parser will handle .env
        return


def _parse_dotenv_fallback(path='.env', override=False):
    """
    Parse a .env file that might use `KEY: value` or `KEY=value`, and set to os.environ
    without overwriting already set environment variables.
    """
    try:
        if not os.path.exists(path):
            return
        # Support multi-line values where a long key may be wrapped across lines.
        # Strategy: treat lines that don't contain `:` or `=` as continuations of the
        # previous value. When override=True, overwrite existing os.environ values.
        with open(path, 'r') as f:
            prev_k = None
            prev_v = None
            for raw in f:
                line = raw.rstrip('\n')
                if not line or line.lstrip().startswith('#'):
                    continue
                # If this line contains a key assignment, finalize any previous key
                # and start a new one. Support both `KEY: value` and `KEY=value`.
                if (':' in line and '=' not in line) or '=' in line:
                    # flush previous
                    if prev_k is not None:
                        if override:
                            os.environ[prev_k] = prev_v
                        else:
                            os.environ.setdefault(prev_k, prev_v)
                        prev_k = None
                        prev_v = None

                    if ':' in line and '=' not in line:
                        k, v = line.split(':', 1)
                    else:
                        k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip()
                    # remove optional surrounding quotes
                    if len(v) >= 2 and ((v[0] == v[-1]) and v[0] in ("'", '"')):
                        v = v[1:-1]
                    # normalize whitespace/newlines in values
                    v = v.replace('\r','').replace('\n','').strip()
                    prev_k = k
                    prev_v = v
                else:
                    # continuation of previous value; append without injection of extra whitespace
                    if prev_k is not None:
                        append_text = line.strip()
                        # If previous value already ends with a backslash, keep it
                        if prev_v and prev_v.endswith('\\'):
                            prev_v = prev_v[:-1] + '\n' + append_text
                        else:
                            prev_v = prev_v + append_text
                    else:
                        # stray fallback line that doesn't parse - ignore
                        continue
            # At EOF, flush any pending key
            if prev_k is not None:
                # normalize and set
                prev_v = prev_v.replace('\r','').replace('\n','').strip()
                if override:
                    os.environ[prev_k] = prev_v
                else:
                    os.environ.setdefault(prev_k, prev_v)
    except Exception:
        # don't fail startup if parsing fails
        return


def load_env(path='.env', override=True):
    """Load environment variables from a .env file. This first uses python-dotenv
    (supports standard KEY=VALUE), then a small fallback parser supporting KEY: VALUE.
    """
    # load standard dotenv first
    try:
        # If python-dotenv is available, prefer to let it handle loading and
        # optionally overwrite existing os.environ when requested
        # `load_dotenv` supports `override` param in modern versions.
        try:
            load_dotenv(path, override=override)
        except TypeError:
            # Older python-dotenv versions use `override` only when passing
            # `override` in some variants or use `load_dotenv(path, override=True)`
            load_dotenv(path)
    except Exception:
        pass
    # fallback for colon-style assignments
    _parse_dotenv_fallback(path, override=override)


def get_env(*names, default=None):
    """Return the first set environment variable found in `names`, or default."""
    for n in names:
        val = os.getenv(n)
        if val is not None and val != '':
            return val
    return default


def _sanitize_env_value(val: str):
    if val is None:
        return None
    # Remove accidental newlines/CRs and trim whitespace
    return val.replace('\r', '').replace('\n', '').strip()


def azure_config():
    """Return a tuple (endpoint, key, deployment, api_version)
    looking at supported names for variables.
    """
    endpoint = _sanitize_env_value(get_env('AZURE_OPENAI_ENDPOINT'))
    key = _sanitize_env_value(get_env('AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_KEY'))
    # Prefer *_DEPLOYMENT_NAME (used in this repo) over *_DEPLOYMENT if both are declared
    deployment = _sanitize_env_value(get_env('AZURE_OPENAI_DEPLOYMENT_NAME', 'AZURE_OPENAI_DEPLOYMENT'))
    api_version = _sanitize_env_value(get_env('AZURE_OPENAI_API_VERSION', 'AZURE_OPENAI_API_VERSION'))
    return endpoint, key, deployment, api_version


def openai_key():
    """Return OpenAI SaaS key if present."""
    return _sanitize_env_value(get_env('OPENAI_API_KEY', 'OPENAI_KEY'))


def openai_saas_model():
    """Return the model name to use for OpenAI SaaS. Honor ENABLE_RAPTOR_MINI toggle."""
    # If user explicitly sets OPENAI_MODEL, prefer that; otherwise, default to
    # 'raptor-mini' when ENABLE_RAPTOR_MINI=1 or 'gpt-4o-mini' otherwise.
    explicitly = _sanitize_env_value(get_env('OPENAI_MODEL'))
    if explicitly:
        return explicitly
    enable_raptor = _sanitize_env_value(get_env('ENABLE_RAPTOR_MINI'))
    # Default to 'raptor-mini' for all clients unless explicitly overridden
    if enable_raptor and enable_raptor.lower() in ('0','false','no'):
        return 'gpt-4o-mini'
    return 'raptor-mini'
