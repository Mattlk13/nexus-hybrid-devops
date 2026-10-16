"""Bounded adapters: local runtime inspection and Terraform state discovery only.

Mutating infrastructure/deployment operations remain disabled pending isolated
account tests and rollback certification. No shell commands or user flags.
"""
import json
import os
from pathlib import Path
import re
import subprocess

class RuntimeErrorSafe(RuntimeError):
    pass

def _run(argv, cwd=None):
    try:
        result=subprocess.run(argv,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                              timeout=20,check=False)
    except subprocess.TimeoutExpired as exc: raise RuntimeErrorSafe('adapter_timeout') from exc
    except OSError as exc: raise RuntimeErrorSafe('adapter_unavailable') from exc
    if result.returncode: raise RuntimeErrorSafe('adapter_operation_failed')
    if len(result.stdout)>1048576: raise RuntimeErrorSafe('adapter_response_too_large')
    try: return json.loads(result.stdout)
    except ValueError as exc:
        if argv[1:2] == ['ps']:
            try: return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            except ValueError: pass
        raise RuntimeErrorSafe('adapter_invalid_json') from exc

def list_containers(status=None):
    runtime=os.getenv('NEXUS_CONTAINER_RUNTIME')
    if runtime not in ('docker','podman'): raise RuntimeErrorSafe('container_runtime_not_configured')
    if status is not None and status not in ('running','exited','created','paused'):
        raise RuntimeErrorSafe('invalid_container_status')
    # Only resources explicitly labeled as NEXUS certification fixtures.
    args=[runtime,'ps','--all','--filter','label=nexus.scope=certification','--format','json']
    if status: args+=['--filter','status='+status]
    data=_run(args)
    if isinstance(data,dict): data=[data]
    if not isinstance(data,list): raise RuntimeErrorSafe('adapter_invalid_schema')
    # Do not expose environment variables, mount paths, or arbitrary runtime fields.
    clean=[]
    for item in data:
        if not isinstance(item,dict): raise RuntimeErrorSafe('adapter_invalid_schema')
        identity=item.get('Id',item.get('ID'))
        if not isinstance(identity,str) or not re.fullmatch('[a-fA-F0-9]{12,64}',identity):
            raise RuntimeErrorSafe('adapter_invalid_schema')
        clean.append({'id':identity,'state':item.get('State')})
    return {'success':True,'containers':clean,'total':len(clean),'mode':'read_only','verified':True}

def infrastructure_state():
    root=os.getenv('NEXUS_TERRAFORM_CHECKOUT')
    if not root: raise RuntimeErrorSafe('infrastructure_adapter_not_configured')
    path=Path(root).resolve()
    if not path.is_dir(): raise RuntimeErrorSafe('terraform_checkout_missing')
    data=_run(['terraform','show','-json'],cwd=path)
    if not isinstance(data,dict) or 'format_version' not in data:
        raise RuntimeErrorSafe('terraform_state_unconfirmed')
    # State output can include secrets even when marked sensitive. Never return it.
    values=data.get('values',{})
    count=0
    def visit(module):
        nonlocal count
        if not isinstance(module,dict): raise RuntimeErrorSafe('terraform_invalid_schema')
        resources=module.get('resources',[])
        if not isinstance(resources,list): raise RuntimeErrorSafe('terraform_invalid_schema')
        count+=len(resources)
        for child in module.get('child_modules',[]): visit(child)
    if not isinstance(values,dict): raise RuntimeErrorSafe('terraform_invalid_schema')
    visit(values.get('root_module',{}))
    return {'success':True,'resource_count':count,'mode':'state_snapshot',
            'live_provider_verified':False,'secrets_redacted':True}

def _runtime():
    runtime=os.getenv('NEXUS_CONTAINER_RUNTIME')
    if runtime not in ('docker','podman'): raise RuntimeErrorSafe('container_runtime_not_configured')
    return runtime

def _inspect(runtime,name):
    data=_run([runtime,'inspect',name])
    if not isinstance(data,list) or len(data)!=1 or not isinstance(data[0],dict):
        raise RuntimeErrorSafe('container_verification_failed')
    item=data[0]
    if item.get('Config',{}).get('Labels',{}).get('nexus.scope')!='certification':
        raise RuntimeErrorSafe('container_outside_certification_scope')
    return item

def create_container(config):
    runtime=_runtime()
    if not isinstance(config,dict) or set(config)-{'image','request_id'}:
        raise RuntimeErrorSafe('unsupported_container_configuration')
    image=config.get('image');key=config.get('request_id')
    if not isinstance(key,str) or not re.fullmatch('[a-z0-9-]{1,40}',key):
        raise RuntimeErrorSafe('request_id_required')
    # Operator must pre-pull one immutable image. No registry pulls by this adapter.
    if not isinstance(image,str) or not re.fullmatch(r'sha256:[a-f0-9]{64}',image) or image!=os.getenv('NEXUS_CERTIFICATION_IMAGE'):
        raise RuntimeErrorSafe('image_not_allowed')
    name='nexus-cert-'+key
    # `docker create` atomically reserves the deterministic name; a duplicate is
    # reconciled by inspect and never starts an additional container.
    try:
        result=subprocess.run([runtime,'create','--name',name,'--label','nexus.scope=certification',
            '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--pids-limit','32','--memory','32m','--cpus','0.25',image,'sleep','120'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=False)
    except subprocess.TimeoutExpired as exc: raise RuntimeErrorSafe('creation_outcome_unknown') from exc
    except OSError as exc: raise RuntimeErrorSafe('adapter_unavailable') from exc
    item=_inspect(runtime,name)
    if item.get('Image')!=image: raise RuntimeErrorSafe('duplicate_request_conflict')
    if item.get('State',{}).get('Running'):
        return {'success':True,'container':{'id':item['Id'],'status':'running'},'verified':True,'duplicate':True}
    if result.returncode: raise RuntimeErrorSafe('duplicate_request_not_running')
    try:
        subprocess.run([runtime,'start',name],check=True,stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,timeout=20)
        item=_inspect(runtime,name)
        if not item.get('State',{}).get('Running'): raise RuntimeErrorSafe('container_not_running')
    except (OSError,subprocess.SubprocessError,RuntimeErrorSafe) as exc:
        # Only remove this attempt's newly created, deterministic fixture.
        try:
            subprocess.run([runtime,'rm','--force',name],check=True,stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,timeout=20)
        except (OSError,subprocess.SubprocessError):
            raise RuntimeErrorSafe('container_start_failed_cleanup_unconfirmed') from exc
        raise RuntimeErrorSafe('container_start_failed_cleanup_requested') from exc
    return {'success':True,'container':{'id':item['Id'],'status':'running'},'verified':True,'duplicate':False}

def stop_container(identity):
    runtime=_runtime()
    if not isinstance(identity,str) or not re.fullmatch(r'nexus-cert-[a-z0-9-]{1,40}',identity):
        raise RuntimeErrorSafe('certification_name_required')
    _inspect(runtime,identity)
    try:
        subprocess.run([runtime,'stop','--time','5',identity],check=True,stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,timeout=20)
    except (OSError,subprocess.SubprocessError) as exc: raise RuntimeErrorSafe('stop_outcome_unconfirmed') from exc
    item=_inspect(runtime,identity)
    if item.get('State',{}).get('Running') is not False: raise RuntimeErrorSafe('container_stop_unconfirmed')
    return {'success':True,'container_id':identity,'status':'stopped','verified':True}
