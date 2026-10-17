"""Real Terraform lifecycle for an explicitly configured isolated workspace.

The adapter refuses production, existing resources and unapproved resource types.
It never accepts HCL, shell fragments, provider credentials or CLI flags from callers.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from contextlib import contextmanager
from nexus_runtime_adapters import RuntimeErrorSafe

class TerraformAdapter:
    def __init__(self):
        root=os.getenv('NEXUS_TERRAFORM_CERTIFICATION_ROOT')
        if not root: raise RuntimeErrorSafe('terraform_certification_not_configured')
        self.root=Path(root).resolve()
        if not (self.root/'.nexus-certification').is_file(): raise RuntimeErrorSafe('isolated_workspace_marker_required')
        self.allowed=set(filter(None,os.getenv('NEXUS_TERRAFORM_RESOURCE_TYPES','terraform_data').split(',')))
    def run(self,*args,ok=(0,)):
        try:
            r=subprocess.run(['terraform',*args],cwd=self.root,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                env={**os.environ,'TF_IN_AUTOMATION':'1','TF_INPUT':'0'},timeout=90,check=False)
        except subprocess.TimeoutExpired as exc: raise RuntimeErrorSafe('terraform_timeout_outcome_unknown') from exc
        except OSError as exc: raise RuntimeErrorSafe('terraform_unavailable') from exc
        if r.returncode not in ok: raise RuntimeErrorSafe('terraform_operation_failed')
        return r.stdout
    def state(self):
        try: data=json.loads(self.run('show','-json'))
        except ValueError as exc: raise RuntimeErrorSafe('terraform_invalid_state') from exc
        resources=[]
        def visit(module):
            for resource in module.get('resources',[]):
                if resource.get('mode')=='managed': resources.append(resource)
            for child in module.get('child_modules',[]): visit(child)
        visit(data.get('values',{}).get('root_module',{}))
        return resources
    @contextmanager
    def lock(self):
        path=self.root/'.nexus-operation.lock'
        try: fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError as exc: raise RuntimeErrorSafe('terraform_operation_in_progress') from exc
        try: yield
        finally: os.close(fd);path.unlink()
    def plan(self,destroy=False):
        target=self.root/'.nexus-plan'
        args=['plan','-input=false','-lock-timeout=5s','-out='+str(target)]
        if destroy: args.append('-destroy')
        self.run(*args)
        try: data=json.loads(self.run('show','-json',str(target)))
        except ValueError as exc: raise RuntimeErrorSafe('terraform_invalid_plan') from exc
        changes=[x for x in data.get('resource_changes',[]) if x.get('change',{}).get('actions')!=['no-op']]
        expected=['delete'] if destroy else ['create']
        for change in changes:
            if change.get('type') not in self.allowed or change.get('change',{}).get('actions')!=expected:
                raise RuntimeErrorSafe('terraform_plan_scope_rejected')
        return target,changes
    def apply(self,request_id,environment='certification'):
        if environment!='certification': raise RuntimeErrorSafe('production_operation_forbidden')
        if not isinstance(request_id,str) or not re.fullmatch('[a-z0-9-]{1,40}',request_id): raise RuntimeErrorSafe('request_id_required')
        if os.getenv('NEXUS_TERRAFORM_APPLY_ENABLED')!='1': raise RuntimeErrorSafe('terraform_apply_not_enabled')
        receipt_path=self.root/'.nexus-receipt.json'
        with self.lock():
            if receipt_path.exists():
                receipt=json.loads(receipt_path.read_text())
                if receipt.get('request_id')!=request_id: raise RuntimeErrorSafe('terraform_request_conflict')
                self.run('plan','-refresh-only','-detailed-exitcode','-input=false','-lock-timeout=5s')
                addresses=sorted(x['address'] for x in self.state())
                if addresses!=receipt['addresses']: raise RuntimeErrorSafe('terraform_readback_mismatch')
                return {'success':True,'verified':True,'duplicate':True,'receipt':receipt}
            if self.state(): raise RuntimeErrorSafe('workspace_not_empty')
            plan,changes=self.plan()
            if not changes: raise RuntimeErrorSafe('terraform_empty_plan')
            # Persist pending ownership before apply so timeout recovery cannot be
            # mistaken for an unrelated fresh workspace. No retries apply blindly.
            pending=self.root/'.nexus-pending.json'
            if pending.exists(): raise RuntimeErrorSafe('terraform_previous_outcome_unconfirmed')
            pending.write_text(json.dumps({'request_id':request_id,'addresses':sorted(x['address'] for x in changes)}))
            self.run('apply','-input=false',str(plan))
            self.run('plan','-refresh-only','-detailed-exitcode','-input=false','-lock-timeout=5s')
            addresses=sorted(x['address'] for x in self.state())
            if addresses!=sorted(x['address'] for x in changes): raise RuntimeErrorSafe('terraform_readback_mismatch')
            receipt={'request_id':request_id,'addresses':addresses,'workspace':hashlib.sha256(str(self.root).encode()).hexdigest()}
            receipt_path.write_text(json.dumps(receipt));pending.unlink()
            return {'success':True,'verified':True,'duplicate':False,'receipt':receipt}
    def destroy(self,receipt,environment='certification'):
        if environment!='certification': raise RuntimeErrorSafe('production_operation_forbidden')
        if os.getenv('NEXUS_TERRAFORM_APPLY_ENABLED')!='1': raise RuntimeErrorSafe('terraform_apply_not_enabled')
        with self.lock():
            path=self.root/'.nexus-receipt.json'
            if not path.exists() or json.loads(path.read_text())!=receipt: raise RuntimeErrorSafe('terraform_receipt_required')
            if sorted(x['address'] for x in self.state())!=receipt['addresses']: raise RuntimeErrorSafe('terraform_destroy_scope_rejected')
            plan,changes=self.plan(destroy=True)
            if sorted(x['address'] for x in changes)!=receipt['addresses']: raise RuntimeErrorSafe('terraform_destroy_scope_rejected')
            self.run('apply','-input=false',str(plan))
            if self.state(): raise RuntimeErrorSafe('terraform_destroy_unconfirmed')
            path.unlink()
            return {'success':True,'verified':True,'destroyed':True,'rollback':True}
