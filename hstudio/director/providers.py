"""LLM providers for the creative steps (mise en scène + titres). All return raw text.
- claude : Anthropic API (official SDK `anthropic`)
- gemini : Google Gemini API (official SDK `google-genai`)
- ollama : local open-source model through Ollama (free, runs on your GPU)
- openai_local : any local server speaking the OpenAI chat format (LM Studio, llama.cpp server, vLLM...)
"""
import json, os, re, requests

class ProviderError(RuntimeError): pass

def call_claude(settings, system, user, max_tokens=64000, log=print):
    import anthropic
    key = settings.get('anthropic_api_key') or os.environ.get('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    model = settings.get('claude_model') or 'claude-opus-5-5'
    effort = settings.get('claude_effort') or 'high'
    kwargs = dict(model=model, max_tokens=max_tokens,
                  system=[{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],
                  messages=[{'role': 'user', 'content': user}],
                  thinking={'type': 'adaptive'}, output_config={'effort': effort})
    use_fallback = settings.get('claude_fallbacks', True)
    def _stream(api, **kw):
        try: return api.stream(**kw)
        except TypeError:          # older SDK without these named params: send them in the body
            extra = dict(kw.pop('extra_body', {}) or {})
            for k in ('thinking', 'output_config'):
                if k in kw: extra[k] = kw.pop(k)
            return api.stream(extra_body=extra, **kw)
    try:
        if use_fallback:
            # server-side refusal fallback: if a safety classifier declines (horror stories can trigger false
            # positives), the API re-runs the request on a fallback model inside the same call
            with _stream(client.beta.messages, betas=['server-side-fallback-2026-07-01'], extra_body={'fallbacks': 'default'}, **kwargs) as stream:
                msg = stream.get_final_message()
        else:
            with _stream(client.messages, **kwargs) as stream:
                msg = stream.get_final_message()
    except anthropic.BadRequestError as e:
        if use_fallback:
            log(f'Claude : fallback refusé ({e.message[:120]}), nouvel essai sans.')
            with _stream(client.messages, **kwargs) as stream:
                msg = stream.get_final_message()
        else: raise ProviderError(f'Claude : requête invalide : {e.message}')
    except anthropic.AuthenticationError:
        raise ProviderError('Claude : clé API invalide (réglages).')
    except anthropic.RateLimitError:
        raise ProviderError('Claude : limite de débit atteinte, réessaie dans une minute.')
    except anthropic.APIConnectionError:
        raise ProviderError('Claude : pas de connexion réseau.')
    if msg.stop_reason == 'refusal':
        raise ProviderError('Claude a refusé la demande (filtre de sécurité). Reformule le script ou utilise Gemini / un modèle local.')
    if msg.stop_reason == 'max_tokens':
        log('Claude : réponse tronquée (max_tokens) - le découpage par morceaux va être utilisé.')
        raise ProviderError('TRUNCATED')
    u = msg.usage
    log(f'Claude ({model}) : {u.input_tokens} jetons en entrée (+{getattr(u, "cache_read_input_tokens", 0) or 0} en cache), {u.output_tokens} en sortie.')
    return ''.join(b.text for b in msg.content if b.type == 'text')

def call_gemini(settings, system, user, max_tokens=65536, log=print):
    from google import genai
    from google.genai import types
    key = settings.get('gemini_api_key') or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not key: raise ProviderError('Gemini : clé API manquante (réglages).')
    client = genai.Client(api_key=key)
    model = settings.get('gemini_model') or 'gemini-2.5-pro'
    resp = client.models.generate_content(model=model, contents=user, config=types.GenerateContentConfig(
        system_instruction=system, response_mime_type='application/json', max_output_tokens=max_tokens, temperature=.8))
    txt = getattr(resp, 'text', None)
    if not txt: raise ProviderError(f'Gemini : réponse vide ({getattr(resp, "prompt_feedback", "")}).')
    um = getattr(resp, 'usage_metadata', None)
    if um: log(f'Gemini ({model}) : {um.prompt_token_count} jetons en entrée, {um.candidates_token_count} en sortie.')
    return txt

def call_gemini_vertex(settings, system, user, max_tokens=16000, log=print):
    """Use the owner's existing Google Cloud ADC, with an explicit Vertex backend; never API-key fallback."""
    from google import genai
    from google.genai import types
    import google.auth
    project=settings.get('vertex_project') or os.environ.get('GOOGLE_CLOUD_PROJECT')
    location=settings.get('vertex_location') or os.environ.get('GOOGLE_CLOUD_LOCATION') or 'global'
    model=settings.get('vertex_model') or os.environ.get('GEMINI_MODEL')
    if not project or not model: raise ProviderError('Gemini Vertex : projet et modèle configurés requis.')
    credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    with genai.Client(vertexai=True,project=project,location=location,credentials=credentials) as client:
        response=client.models.generate_content(model=model,contents=user,config=types.GenerateContentConfig(system_instruction=system,response_mime_type='application/json',max_output_tokens=min(int(max_tokens),16000),temperature=.8))
    text=getattr(response,'text',None)
    if not text: raise ProviderError('Gemini Vertex : réponse vide.')
    usage=getattr(response,'usage_metadata',None)
    if usage: log('Gemini Vertex : '+str(usage.prompt_token_count)+' jetons en entrée, '+str(usage.candidates_token_count)+' en sortie.')
    return text

def call_ollama(settings, system, user, max_tokens=32000, log=print):
    host = (settings.get('ollama_host') or 'http://localhost:11434').rstrip('/')
    model = settings.get('ollama_model') or 'qwen2.5:32b-instruct'
    body = {'model': model, 'stream': False, 'format': 'json',
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'options': {'num_ctx': int(settings.get('ollama_ctx', 32768)), 'temperature': .7, 'num_predict': max_tokens}}
    try: r = requests.post(f'{host}/api/chat', json=body, timeout=3600)
    except requests.ConnectionError: raise ProviderError(f'Ollama introuvable sur {host} (lance "ollama serve").')
    if r.status_code >= 400: raise ProviderError(f'Ollama {r.status_code}: {r.text[:300]}')
    j = r.json(); log(f'Ollama ({model}) : {j.get("prompt_eval_count")} jetons en entrée, {j.get("eval_count")} en sortie.')
    return j['message']['content']

def call_openai_local(settings, system, user, max_tokens=32000, log=print):
    base = (settings.get('local_base_url') or 'http://localhost:1234/v1').rstrip('/')
    model = settings.get('local_model') or 'local-model'
    body = {'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'temperature': .7, 'max_tokens': max_tokens, 'response_format': {'type': 'json_object'}}
    try: r = requests.post(f'{base}/chat/completions', json=body, timeout=3600)
    except requests.ConnectionError: raise ProviderError(f'Serveur local introuvable sur {base}.')
    if r.status_code >= 400:
        body.pop('response_format'); r = requests.post(f'{base}/chat/completions', json=body, timeout=3600)
    if r.status_code >= 400: raise ProviderError(f'Serveur local {r.status_code}: {r.text[:300]}')
    return r.json()['choices'][0]['message']['content']

PROVIDERS = {'claude': call_claude, 'gemini': call_gemini, 'gemini_vertex':call_gemini_vertex, 'ollama': call_ollama, 'openai_local': call_openai_local}

def call(provider, settings, system, user, log=print, max_tokens=None):
    f = PROVIDERS.get(provider)
    if not f: raise ProviderError(f'fournisseur inconnu : {provider}')
    return f(settings, system, user, **({'max_tokens': max_tokens} if max_tokens else {}), log=log)

def parse_json(text):
    t = text.strip()
    t = re.sub(r'^```(?:json)?\s*', '', t); t = re.sub(r'\s*```$', '', t)
    try: return json.loads(t)
    except json.JSONDecodeError: pass
    a, b = t.find('{'), t.rfind('}')
    if a >= 0 and b > a:
        s = t[a:b + 1]
        try: return json.loads(s)
        except json.JSONDecodeError:
            s2 = re.sub(r',\s*([}\]])', r'\1', s)        # trailing commas (local models)
            return json.loads(s2)
    raise ValueError('pas de JSON dans la réponse')
