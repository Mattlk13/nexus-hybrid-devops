"""Existing staging Worker version deployment only. No provisioning or production."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib import error, request
from nexus_runtime_adapters import RuntimeErrorSafe


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeErrorSafe('cloudflare_redirect_rejected')


class CloudflareStagingAdapter:
    def __init__(self):
        self.token=os.getenv('NEXUS_CLOUDFLARE_TOKEN')
        self.account=os.getenv('NEXUS_CLOUDFLARE_ACCOUNT')
        self.worker=os.getenv('NEXUS_CLOUDFLARE_WORKER')
        root=os.getenv('NEXUS_CLOUDFLARE_RECEIPTS')
        if not all((self.token,self.account,self.worker,root)):
            raise RuntimeErrorSafe('deployment_runner_not_configured')
        if not re.fullmatch(r'[a-f0-9]{32}',self.account) or not re.fullmatch(r'[a-z0-9-]+-staging',self.worker):
            raise RuntimeErrorSafe('cloudflare_staging_scope_required')
        self.root=Path(root).resolve()
        if not (self.root/'.nexus-cloudflare-staging').is_file():
            raise RuntimeErrorSafe('cloudflare_isolated_receipts_required')
        self.receipt=self.root/(self.worker+'.json')
        self.base='https://api.cloudflare.com/client/v4/accounts/'+self.account+'/workers/scripts/'+self.worker

    def _scope(self,service,environment):
        if service!=self.worker or environment!='staging':
            raise RuntimeErrorSafe('cloudflare_staging_scope_required')

    def _api(self,method,suffix,body=None):
        req=request.Request(self.base+suffix,method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        try:
            with request.build_opener(NoRedirect()).open(req,timeout=15) as response:
                raw=response.read(1048577)
            if len(raw)>1048576: raise RuntimeErrorSafe('cloudflare_response_too_large')
            data=json.loads(raw)
            if not isinstance(data,dict) or data.get('success') is not True or 'result' not in data:
                raise RuntimeErrorSafe('cloudflare_response_unverified')
            return data['result']
        except error.HTTPError as exc:
            raise RuntimeErrorSafe({401:'cloudflare_authentication_failed',403:'cloudflare_authentication_or_permission_denied',404:'cloudflare_worker_not_found'}.get(exc.code,'cloudflare_http_failure')) from None
        except (TimeoutError,error.URLError) as exc:
            raise RuntimeErrorSafe('cloudflare_request_state_unconfirmed') from None
        except (ValueError,TypeError):
            raise RuntimeErrorSafe('cloudflare_response_unverified') from None

    def _current(self):
        result=self._api('GET','/deployments')
        if not isinstance(result,dict) or not isinstance(result.get('deployments'),list) or not result['deployments']:
            raise RuntimeErrorSafe('cloudflare_deployment_unverified')
        item=result['deployments'][0]
        if not isinstance(item,dict) or not isinstance(item.get('versions'),list) or len(item['versions'])!=1:
            raise RuntimeErrorSafe('cloudflare_single_version_required')
        version=item['versions'][0]
        if not isinstance(version,dict) or version.get('percentage')!=100:
            raise RuntimeErrorSafe('cloudflare_single_version_required')
        for value in (item.get('id'),version.get('version_id')):
            if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9-]{36}',value):
                raise RuntimeErrorSafe('cloudflare_deployment_unverified')
        return item

    @contextmanager
    def _lock(self):
        lock=self.root/(self.worker+'.lock')
        try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError: raise RuntimeErrorSafe('cloudflare_operation_in_progress') from None
        try: yield
        finally: os.close(fd);lock.unlink()

    def _save(self,data):
        temp=self.receipt.with_suffix('.tmp')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as out: json.dump(data,out)
        os.replace(temp,self.receipt)

    def _load(self):
        if not self.receipt.exists(): return None
        try: data=json.loads(self.receipt.read_text())
        except (OSError,ValueError): raise RuntimeErrorSafe('cloudflare_receipt_unverified') from None
        if not isinstance(data,dict): raise RuntimeErrorSafe('cloudflare_receipt_unverified')
        if data.get('account')!=self.account or data.get('worker')!=self.worker:
            raise RuntimeErrorSafe('cloudflare_receipt_scope_mismatch')
        return data

    def _write_version(self,version,message):
        # Never retries a mutation. A timeout leaves a pending receipt.
        self._api('POST','/deployments',{'strategy':'percentage','versions':[{'version_id':version,'percentage':100}],
            'annotations':{'workers/message':message}})
        for attempt in range(5):
            current=self._current()
            if current['versions'][0]['version_id']==version and current.get('annotations',{}).get('workers/message')==message:
                return current
            if attempt<4: time.sleep(.5)
        raise RuntimeErrorSafe('cloudflare_deployment_state_unconfirmed')

    def deploy(self,service,environment,version):
        self._scope(service,environment)
        if not isinstance(version,str) or not re.fullmatch(r'[a-f0-9-]{36}',version):
            raise RuntimeErrorSafe('cloudflare_existing_version_uuid_required')
        with self._lock():
            receipt=self._load()
            current=self._current()
            if receipt and receipt.get('status') in ('pending','rollback_pending'):
                raise RuntimeErrorSafe('cloudflare_pending_outcome_requires_reconciliation')
            if current['versions'][0]['version_id']==version:
                return {'success':True,'duplicate':True,'verified':True,'created':False,'version':version}
            if receipt and receipt.get('status')=='deployed':
                raise RuntimeErrorSafe('cloudflare_rollback_receipt_already_active')
            receipt={'account':self.account,'worker':self.worker,'before_id':current['id'],
                'before_version':current['versions'][0]['version_id'],'version':version,
                'operation':'nexus-cert-'+secrets.token_hex(16),'status':'pending'}
            self._save(receipt)
            deployed=self._write_version(version,receipt['operation'])
            receipt.update(status='deployed',deployment_id=deployed['id']);self._save(receipt)
            return {'success':True,'duplicate':False,'created':True,'verified':True,
                'version':version,'deployment_id':deployed['id'],'rollback_supported':True}

    def rollback(self,service,environment):
        self._scope(service,environment)
        with self._lock():
            receipt=self._load()
            if not receipt: raise RuntimeErrorSafe('cloudflare_owned_receipt_required')
            current=self._current()
            if receipt.get('status')=='rolled_back' and current['versions'][0]['version_id']==receipt['before_version']:
                return {'success':True,'duplicate':True,'verified':True,'version':receipt['before_version']}
            # Reconcile a lost acknowledgement using our persisted operation ID.
            # This is readback, not a second mutation attempt.
            message=current.get('annotations',{}).get('workers/message')
            if receipt.get('status')=='pending' and message==receipt['operation'] and current['versions'][0]['version_id']==receipt['version']:
                receipt.update(status='deployed',deployment_id=current['id']);self._save(receipt)
            if receipt.get('status')=='rollback_pending' and message==receipt['operation']+'-rollback' and current['versions'][0]['version_id']==receipt['before_version']:
                receipt.update(status='rolled_back',rollback_id=current['id']);self._save(receipt)
                return {'success':True,'duplicate':True,'verified':True,'version':receipt['before_version']}
            # A receipt cannot authorize overwriting another actor's deployment.
            if receipt.get('status')!='deployed' or current['id']!=receipt.get('deployment_id') or current['versions'][0]['version_id']!=receipt['version']:
                raise RuntimeErrorSafe('cloudflare_rollback_ownership_unconfirmed')
            receipt['status']='rollback_pending';self._save(receipt)
            restored=self._write_version(receipt['before_version'],receipt['operation']+'-rollback')
            receipt.update(status='rolled_back',rollback_id=restored['id']);self._save(receipt)
            return {'success':True,'duplicate':False,'verified':True,'version':receipt['before_version'],
                'deployment_id':restored['id']}

    def history(self,service,environment):
        self._scope(service,environment)
        current=self._current()
        return {'success':True,'verified':True,'current_deployment':current['id'],
            'current_version':current['versions'][0]['version_id']}
