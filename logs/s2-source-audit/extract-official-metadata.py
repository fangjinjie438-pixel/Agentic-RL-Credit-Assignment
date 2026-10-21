"""Read target metadata only to extend local official quarantine, never tasks."""
from pathlib import Path
import hashlib,json,platform,sys,datetime,unicodedata,re,shutil
root=Path.cwd();audit=root/'logs/s2-source-audit';destination=root/'fixtures/s2/official-exclusions.json'
old=audit/'official-exclusions-id-only.json'
if not old.exists():shutil.copyfile(destination,old)
source=root/'third_party/ecomagentbench/97eff345811fdf652a2135d38d874f2932e11702/data/benchmark/benchmark.jsonl'
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
def norm(value):return ' '.join(re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',value).casefold()))
ids=set();titles=set();families=set();models={};unknown=set();task_count=0;brand_tasks=0;model_tasks=0
for line in source.read_text().splitlines():
 target=json.loads(line)['target_product'];task_count+=1
 pid=target['product_id'];ids.add(pid)
 title=target.get('title')
 if isinstance(title,str) and norm(title):titles.add(title)
 details=target.get('details')
 if isinstance(details,str):details=json.loads(details)
 details=details if isinstance(details,dict) else {}
 brand=next((v.strip() for k,v in details.items() if norm(k)=='brand' and isinstance(v,str) and norm(v)),None)
 if brand:
  brand_tasks+=1;families.add('brand:'+norm(brand))
  actual_models=[v.strip() for k,v in details.items() if norm(k) in {'item model number','model number'} and isinstance(v,str) and norm(v)]
  if actual_models:model_tasks+=1
  for model in actual_models:models[(norm(brand),norm(model))]={'brand':brand,'model':model}
 else:unknown.add(pid)
index={'schema_version':1,'source_revision':'97eff345811fdf652a2135d38d874f2932e11702',
 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_path':str(source.relative_to(root)),
 'source_url':'https://raw.githubusercontent.com/Morizeyao/EComAgentBench_/97eff345811fdf652a2135d38d874f2932e11702/data/benchmark/benchmark.jsonl',
 'accessed_fields':['target_product.product_id','target_product.title','target_product.details.Brand',
                    'target_product.details.Item model number','target_product.details.Model Number'],
 'official_task_count':task_count,'product_ids':sorted(ids),'titles':sorted(titles),'families':sorted(families),
 'brand_models':[models[k] for k in sorted(models)],'coverage':'target_ids_and_available_brand_model_title',
 'family_method':'conservative_whole_source_brand','unknown_family_product_ids':sorted(unknown),
 'family_exclusion_status':'partial_available_metadata_indexed_missing_brands_remain',
 'metadata_complete':False,'purpose':'quarantine_only_never_task_or_reward_generation',
 'counts':{'tasks_with_brand':brand_tasks,'tasks_with_explicit_model_number_and_brand':model_tasks,
           'unique_product_ids':len(ids),'unique_titles':len(titles),'unique_brand_families':len(families),
           'unique_brand_models':len(models),'unknown_family_product_ids':len(unknown)}}
destination.write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
script=Path('/tmp/s2-extract-official-metadata.py');shutil.copyfile(script,audit/'extract-official-metadata.py')
summary={'command':'.venv-cpu/bin/python /tmp/s2-extract-official-metadata.py','started_at':started,
 'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'machine':platform.node(),'interpreter':sys.executable,
 'python_version':sys.version,'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),
 'source_revision':index['source_revision'],'source_sha256':index['source_sha256'],
 'output_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'counts':index['counts'],
 'accessed_fields':index['accessed_fields'],'gpu_compute_performed':False,'teacher_calls':0,'seed':None,
 'model_revision':None,'checkpoint':None}
(audit/'official-metadata-extraction.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'counts':index['counts'],'coverage':index['coverage'],'metadata_complete':False}))
