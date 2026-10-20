"""Two self-authored genre fixtures; these are NOT crawled novel chapters."""
import sys
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from semantic_gate import build_package,write_json,digest
from native_oauth.parse_source import load_parser


def main():
    fixtures={
        'tien_hiep':(['陆川收起飞剑，没有追杀那名逃走的弟子。',
                    '师父沉默片刻，道：“此事未必与掌门有关。你不可妄下结论。”',
                    '她在心中想道：“只要再等三天，师兄就会回来。”',
                    '他服下两枚丹药，体内的灵气却并未增加。'],{'陆川':'Lục Xuyên'}),
        'hien_dai':(['李明看了看手机里的短信：“工资明天到账，你别着急。”',
                   '“妈，我今天加班，不能回家吃饭。”他说。',
                   '她没有答应，只说需要再考虑两天。',
                   '张经理要求库存不少于900件，而不是多于900件。'],{'李明':'Lý Minh'})}
    model,provenance=load_parser()
    for genre,(texts,lore) in fixtures.items():
        p=build_package(1,'SYNTHETIC GENRE FIXTURE',texts,lore,'Self-authored Chinese regression fixture, 2026-10-13')
        p['scope']={'kind':'SYNTHETIC_FIXTURE','genre':genre,'not_a_crawled_chapter':True}
        p['package_hash']=digest({k:v for k,v in p.items() if k!='package_hash'})
        result=model.pipeline(texts,tasks=['cws','pos','ner','srl','dep','sdp'])
        rows=[]
        for i,s in enumerate(p['segments']):
            dep=result.dep[i]
            rows.append({'id':s['id'],'source_hash':digest(s['source']),'cws':result.cws[i],'pos':result.pos[i],
                         'ner':result.ner[i],'srl':result.srl[i],'sdp':result.sdp[i],
                         'dep':[{'id':k+1,'word':word,'pos':result.pos[i][k],
                                 'head':dep['head'][k],'relation':dep['label'][k]} for k,word in enumerate(result.cws[i])]})
        out=ROOT/'native_oauth/research'/('fixture_'+genre)
        write_json(str(out)+'.source.json',p)
        write_json(str(out)+'.analysis.json',{'source_package_hash':p['package_hash'],'provenance':provenance,
                                            'limits':'Model-predicted syntax/SRL, not truth; self-authored fixture',
                                            'segments':rows})
        work=ROOT/'native_oauth'/('pilot_'+genre)
        (work/'.agents/agents').mkdir(parents=True,exist_ok=True)
        for agent in (ROOT/'.agents/agents').glob('novel-*.md'):
            shutil.copy2(agent,work/'.agents/agents'/agent.name)
        print('Prepared synthetic fixture',genre,flush=True)


if __name__=='__main__':
    main()
