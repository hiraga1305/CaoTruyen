"""Ground diagnostic findings without converting them into approval evidence."""


def ground_diagnosis(package, candidate, diagnosis):
    expected=[r['id'] for r in package['segments']]
    if diagnosis.get('coverage_ids') != expected:
        raise ValueError('Diagnostic coverage is incomplete/reordered')
    if [r['id'] for r in candidate['segments']] != expected:
        raise ValueError('Diagnostic candidate does not cover this source')
    accepted=[];rejected=[]
    for finding in diagnosis.get('findings',[]):
        source_quote=finding.get('source_quote');target_quote=finding.get('target_quote')
        matches=[raw['id'] for raw,target in zip(package['segments'],candidate['segments'])
                 if isinstance(source_quote,str) and source_quote.strip() and source_quote in raw['source']
                 and isinstance(target_quote,str) and target_quote.strip() and target_quote in target['text']]
        declared=finding.get('id')
        if len(matches)!=1 or (declared in expected and declared!=matches[0]):
            rejected.append({'raw_finding':finding,'reason':'Source/target quotes do not uniquely match the declared paragraph'})
            continue
        accepted.append({'finding_id':declared,'source_id':matches[0],**{k:v for k,v in finding.items() if k!='id'},
                         'scope':'Quotes anchored only; correctness and proposed text still require independent review'})
    return {'status':'GROUNDED_DIAGNOSTIC_NOT_APPROVAL','accepted':accepted,'rejected':rejected}
