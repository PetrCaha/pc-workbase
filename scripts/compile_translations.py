"""Compile the reviewed UTF-8 translation source to standard GNU .po/.mo files.
No gettext executable is required on the deployment host.
"""
from pathlib import Path
import json
import struct
ROOT=Path(__file__).resolve().parent.parent
messages={}
for line in (ROOT/'locale/en/translations.tsv').read_text().splitlines():
    if not line or line.startswith('#'):continue
    source,target=line.split('\t',1)
    messages[source]=target
messages['']='Content-Type: text/plain; charset=UTF-8\nLanguage: en\nPlural-Forms: nplurals=2; plural=(n != 1);\n'

def compile_catalog(domain):
    keys=sorted(messages)
    originals=[key.encode() for key in keys]; translated=[messages[key].encode() for key in keys]
    count=len(keys);start=28+16*count
    original_blob=b'\0'.join(originals)+b'\0';translated_blob=b'\0'.join(translated)+b'\0'
    offsets=[];cursor=start
    for value in originals:offsets.extend((len(value),cursor));cursor+=len(value)+1
    for value in translated:offsets.extend((len(value),cursor));cursor+=len(value)+1
    binary=struct.pack('<7I',0x950412de,0,count,28,28+8*count,0,0)+struct.pack('<'+'I'*len(offsets),*offsets)+original_blob+translated_blob
    folder=ROOT/'locale/en/LC_MESSAGES'
    (folder/(domain+'.mo')).write_bytes(binary)
    (folder/(domain+'.po')).write_text('\n\n'.join('msgid '+json.dumps(key,ensure_ascii=False)+'\nmsgstr '+json.dumps(messages[key],ensure_ascii=False) for key in keys)+'\n')
for domain in ('django','djangojs'):compile_catalog(domain)
print(f'Compiled {len(messages)-1} reviewed translations.')
