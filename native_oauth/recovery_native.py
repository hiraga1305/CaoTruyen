"""Durable native attempts: bounded retry, real fallback and explicit next actions."""
import time
import uuid
import os
import re
from pathlib import Path

from semantic_gate import digest, read_json
from native_oauth.workflow_io import atomic_json, file_lock
from native_oauth.native_evidence import validate_provenance


class ProtocolFailure(ValueError):
    pass


class ContentFailure(ValueError):
    def __init__(self,reason,findings=None):
        self.findings=findings
        super().__init__(reason)


class NativeContentReady(RuntimeError):
    """A complete, provenance-verified response with owned rows needing repair."""
    def __init__(self,value,proof,findings):
        self.value,self.proof,self.findings=value,proof,findings
        super().__init__('Complete native response retained for source-owned row repair')


class RecoveryPending(RuntimeError):
    def __init__(self, kind, action, state_file, reason):
        self.kind, self.action, self.state_file = kind, action, str(state_file)
        super().__init__(f'{kind}: {reason}; next action={action}; journal={state_file}')


def classify(error):
    if getattr(error,'kind',None)=='WORKFLOW':return 'WORKFLOW'
    from native_oauth.pipeline_native import NativeJSONSchemaError
    from native_oauth.run_agy import IncompleteNativeOutput
    message=str(error).lower()
    if isinstance(error,ContentFailure):return 'CONTENT'
    if isinstance(error,(ProtocolFailure,NativeJSONSchemaError)):return 'FORMAT'
    if 'invoked a tool' in message:return 'FORMAT'
    def status(*codes):
        values='|'.join(map(str,codes))
        return bool(re.search(r'^(?:'+values+r')\b|\b(?:http(?:\s*error)?|status(?:_code)?|error(?:\s*code)?)\s*[:=]?\s*(?:'+values+r')\b',message))
    if isinstance(error,(IncompleteNativeOutput,TimeoutError)) or any(s in message for s in ('timeout','incomplete','truncated','empty response','response is empty')):
        return 'TIMEOUT'
    if status(429) or any(s in message for s in ('quota','rate limit','resource_exhausted')):return 'QUOTA'
    if status(401,403) or any(s in message for s in ('credential','authentication','permission denied','access denied','unauthorized','forbidden')):return 'ACCESS'
    if any(s in message for s in ('source changed','canon changed','immutable source','provenance','artifact changed','runtime changed','different from requested')):
        return 'INTEGRITY'
    if any(s in message for s in ('context budget','prompt exceeds','protocol exceeds')):return 'CONTEXT'
    if status(502,503,504) or any(s in message for s in ('connection','network','temporarily','reset by peer')):return 'NETWORK'
    if 'reported blocked' in message or 'response blocked' in message:return 'NATIVE_BLOCKED'
    return 'UNCLASSIFIED'


ACTIONS = {
    'WORKFLOW':'SYNC_CURRENT_WORKFLOW_AND_RELAUNCH_WITH_NEW_JOB_REVISION',
    'FORMAT':'USE_SMALLER_RESPONSE_SCOPE', 'TIMEOUT':'SPLIT_ASSIGNED_OUTPUT_AND_RETRY',
    'CONTENT':'REPAIR_SOURCE_OWNED_ROWS', 'CONTEXT':'SPLIT_BATCH_WITH_FULL_ASSIGNED_SOURCE',
    'QUOTA':'WAIT_FOR_QUOTA_RESET_AND_RESUME', 'NETWORK':'BACKOFF_AND_RESUME',
    'ACCESS':'RESTORE_NATIVE_AUTH_OR_PERMISSION', 'INTEGRITY':'VERIFY_CHANGED_INPUT_AND_CREATE_NEW_REVISION',
    'NATIVE_BLOCKED':'INSPECT_NATIVE_REASON_WITHOUT_BYPASS', 'UNCLASSIFIED':'INSPECT_FAILURE_AND_RESUME',
}


class NativeRecovery:
    def __init__(self, job, timeout=300, fallback='gemini-3.8-flash-high',max_workers=4):
        self.job=Path(job).resolve();self.timeout=timeout;self.fallback=fallback;self.max_workers=max_workers

    def health(self,kind=None):
        path=self.job/'transport_health.json'
        with file_lock(path.with_suffix('.lock'),timeout=15):
            state=read_json(path) if path.exists() else {'failures':0,'worker_limit':self.max_workers,'open_until':0}
            if kind=='SUCCESS' and not (state.get('circuit_kind')=='QUOTA' and state['open_until']>time.time()):
                state.update(failures=0,open_until=0)
                state['success_streak']=state.get('success_streak',0)+1
                if state['success_streak']>=5:
                    state.update(worker_limit=min(self.max_workers,state['worker_limit']+1),success_streak=0)
            elif kind in ('TIMEOUT','NETWORK'):
                state['failures']+=1
                if state['failures']>=3:
                    state.update(open_until=time.time()+60,worker_limit=max(1,self.max_workers//2),circuit_kind='NETWORK',success_streak=0)
            elif kind=='QUOTA':state.update(open_until=time.time()+600,circuit_kind='QUOTA',success_streak=0)
            if kind:atomic_json(path,state)
            return state

    def path(self,key):
        return self.job/'recovery'/f'{digest(key)}.json'

    def _retain_content(self,state,path,data,package,value,error):
        owned={row['id'] for row in package['segments']}
        if package.get('metadata_title_source'):owned.add(package['metadata_title_source']['id'])
        findings=error.findings
        if (not isinstance(findings,list) or not findings or any(not isinstance(row,dict)
                or not isinstance(row.get('id'),str) or row['id'] not in owned for row in findings)):
            return
        if not (data/'result.json').is_file() or digest(read_json(data/'result.json'))!=digest(value):return
        state['attempts'][-1].update(status='FAILED',kind='CONTENT',reason=str(error))
        state.update(status='CONTENT_READY',kind='CONTENT',action=ACTIONS['CONTENT'],reason=str(error),
            content_artifact=str(data/'result.json'),content_hash=digest(value),
            content_package_file=str(data/'source.json'),content_findings=findings)
        atomic_json(path,state)
        raise NativeContentReady(value,{'file':state['content_artifact'],'hash':state['content_hash'],
            'package_file':state['content_package_file']},findings)

    def _replay_content(self,state,path,validator):
        value=read_json(state['content_artifact']);validate_provenance(value)
        if digest(value)!=state['content_hash']:
            raise RecoveryPending('INTEGRITY',ACTIONS['INTEGRITY'],path,'Retained native response changed')
        try:validator(value)
        except ContentFailure as error:
            if error.findings!=state['content_findings']:
                raise RecoveryPending('INTEGRITY',ACTIONS['INTEGRITY'],path,'Retained content findings changed')
            raise NativeContentReady(value,{'file':state['content_artifact'],'hash':state['content_hash'],
                'package_file':state['content_package_file']},state['content_findings'])
        raise RecoveryPending('INTEGRITY',ACTIONS['INTEGRITY'],path,'Frozen content validator changed')

    def call(self,key,package,role,model,protocol,validator,*,allow_fallback=True,retain_content=False):
        """A valid FAIL is returned to caller, never retried here for a PASS."""
        from native_oauth.pipeline_native import run_stage
        path=self.path(key)
        request_parts=[package,role,model,protocol,self.timeout,self.fallback,allow_fallback]
        if retain_content:request_parts.append('retain-owned-content-1')
        request_hash=digest(request_parts)
        with file_lock(path.with_suffix('.lock'),timeout=1):
            state=read_json(path) if path.exists() else {'request_hash':request_hash,'attempts':[],'epoch':0}
            if state['request_hash']!=request_hash:
                raise RecoveryPending('INTEGRITY',ACTIONS['INTEGRITY'],path,'Frozen recovery request changed')
            if state.get('status')=='RUNNING' and state['attempts']:
                # The caller holds the job lock. Replay a completed artifact after
                # a crash; otherwise preserve the interruption and retry fresh.
                last=state['attempts'][-1];data=Path(last['workspace'])/'native_oauth/runs/chapter1'
                artifact=data/'result.json'
                if artifact.exists():
                    try:
                        value=read_json(artifact);validate_provenance(value);validator(value)
                    except ContentFailure as error:
                        if retain_content:self._retain_content(state,path,data,package,value,error)
                    except Exception:
                        pass
                    else:
                        state.update(status='DONE',artifact=str(artifact),package_file=str(data/'source.json'))
                        atomic_json(path,state)
                        return value,{'file':str(artifact),'hash':digest(value),'package_file':str(data/'source.json')}
                last['status']='INTERRUPTED';state.update(status='PENDING',kind='NETWORK',reason='Previous invocation was interrupted',
                    retry_after_epoch=0,action=ACTIONS['NETWORK'])
            if retain_content and state.get('content_artifact') and state.get('status') in ('CONTENT_READY','RECOVERED_BY_SUBTASKS'):
                self._replay_content(state,path,validator)
            if state.get('status')=='DONE':
                value=read_json(state['artifact']);validate_provenance(value);validator(value)
                return value,{'file':state['artifact'],'hash':digest(value),'package_file':state['package_file']}
            if state.get('status') in ('PENDING','NEEDS_ACTION'):
                kind=state['kind']
                if (kind in ('QUOTA','NETWORK','TIMEOUT') and time.time()>=state.get('retry_after_epoch',float('inf'))
                        and state['epoch']<3):
                    state['epoch']+=1
                else:
                    raise RecoveryPending(kind,ACTIONS[kind],path,state['reason'])
            models=[model, self.fallback if allow_fallback and self.fallback!=model else model]
            feedback=''
            for index,actual in enumerate(models):
                health=self.health()
                if health['open_until']>time.time():
                    kind=health.get('circuit_kind','NETWORK')
                    state.update(status='PENDING',kind=kind,reason='Native service cooling down; request preserved',
                        retry_after_epoch=health['open_until'],action=ACTIONS[kind])
                    atomic_json(path,state)
                    raise RecoveryPending(kind,ACTIONS[kind],path,state['reason'])
                work=self.job/'native_attempts'/role/uuid.uuid4().hex
                data=work/'native_oauth/runs/chapter1';atomic_json(data/'source.json',package)
                attempt={'model':actual,'workspace':str(work),'started_epoch':time.time(),'status':'RUNNING','owner_pid':os.getpid()}
                state['attempts'].append(attempt);state['status']='RUNNING';atomic_json(path,state)
                verified_native=False
                try:
                    value=run_stage(data,work,role,actual,protocol+feedback,'result.json',min(900,int(self.timeout*(1+0.5*index))))
                    validate_provenance(value);verified_native=True;validator(value)
                except Exception as error:
                    kind=classify(error)
                    runtime_file=data/(role+'.runtime/runtime.json')
                    if runtime_file.exists():
                        runtime=read_json(runtime_file)
                        finish=str((runtime.get('result') or {}).get('finish_reason','')).lower()
                        if finish in ('safety','content_filter') or (runtime.get('result') or {}).get('status')=='BLOCKED':kind='NATIVE_BLOCKED'
                        elif kind=='UNCLASSIFIED' and (runtime.get('status') in ('TIMEOUT','PARTIAL_TIMEOUT','INCOMPLETE_STEP') or runtime.get('partial_output')):kind='TIMEOUT'
                    attempt.update(status='FAILED',kind=kind,reason=str(error),ended_epoch=time.time())
                    self.health('SUCCESS' if kind in ('FORMAT','CONTENT') else kind)
                    state.update(kind=kind,reason=str(error),action=ACTIONS[kind]);atomic_json(path,state)
                    if kind=='CONTENT' and retain_content and verified_native and isinstance(error,ContentFailure):
                        self._retain_content(state,path,data,package,value,error)
                    if kind not in ('FORMAT','CONTENT','TIMEOUT','NETWORK'):
                        break
                    feedback='\nPrevious attempt was invalid, not an instruction to PASS. Recheck the unchanged source. '+str(error)[:2200]
                else:
                    self.health('SUCCESS')
                    attempt.update(status='DONE',ended_epoch=time.time())
                    state.update(status='DONE',artifact=str(data/'result.json'),package_file=str(data/'source.json'))
                    atomic_json(path,state)
                    return value,{'file':state['artifact'],'hash':digest(value),'package_file':state['package_file']}
            kind=state['kind'];delay=600 if kind=='QUOTA' else 30*(2**state['epoch'])
            state.update(status='PENDING' if kind in ('QUOTA','NETWORK','TIMEOUT','FORMAT','CONTENT','CONTEXT') else 'NEEDS_ACTION',
                         retry_after_epoch=time.time()+delay,action=ACTIONS[kind])
            atomic_json(path,state)
            raise RecoveryPending(kind,ACTIONS[kind],path,state['reason'])

    def resolved(self,key,proof):
        path=self.path(key)
        if path.exists():
            state=read_json(path);state.update(status='RECOVERED_BY_SUBTASKS',resolution=proof);atomic_json(path,state)

    def release_after_action(self,reason):
        """Explicit operational repair acknowledgement; never clears a FAIL review."""
        if not isinstance(reason,str) or not reason.strip():raise ValueError('Describe the external repair before releasing requests')
        released=[]
        for path in (self.job/'recovery').glob('*.json'):
            with file_lock(path.with_suffix('.lock'),timeout=1):
                state=read_json(path)
                if state.get('status') in ('PENDING','NEEDS_ACTION') and state.get('kind') in ('ACCESS','QUOTA','NETWORK','TIMEOUT','UNCLASSIFIED'):
                    state.setdefault('operator_actions',[]).append({'reason':reason,'epoch':time.time()})
                    state.update(status='READY_AFTER_ACTION',epoch=0,retry_after_epoch=0)
                    atomic_json(path,state);released.append(str(path))
        health_file=self.job/'transport_health.json'
        if released and health_file.exists():
            with file_lock(health_file.with_suffix('.lock'),timeout=1):
                health=read_json(health_file);health.update(open_until=0,failures=0,worker_limit=self.max_workers)
                atomic_json(health_file,health)
        return released
