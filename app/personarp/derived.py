"""Apply a writing-style output head to a private copy of a base model.

This is a text-style variant, not speech synthesis. The base weights are never
modified: a separate GGUF is written next to them and verified before use.
No code from the remote repository is executed.
"""
import json,struct
from pathlib import Path
from cytools_core import CyToolError
from .paths import read_json,write_json

def derived_status(model,verify=False,ctx=None):
    from . import models as lm
    from .models import sha
    info=lm.catalog()[model];path=lm.model_path(model);receipt=read_json(path.with_suffix('.prepared.json'))
    expected={'recipe':info['recipe'],'voiceSha256':info['files'][0]['sha256'],'baseSha256':lm.catalog()[info['baseModel']]['files'][0]['sha256']}
    if not path.is_file() or any(receipt.get(k)!=v for k,v in expected.items()) or receipt.get('size')!=path.stat().st_size or not receipt.get('sha256'):return False
    return not verify or sha(path,ctx)==receipt['sha256']

def prepare(model,ctx):
    import numpy as np
    from gguf import GGUFReader,GGUFWriter,GGMLQuantizationType as Q
    from gguf.gguf_writer import GGUFValue
    from gguf.quants import quantize
    from . import models as lm
    from .models import sha
    info=lm.catalog()[model]
    if derived_status(model,True,ctx):return
    base=lm.model_path(info['baseModel']);voice=lm.directory(model)/info['files'][0]['name'];dest=lm.model_path(model)
    with voice.open('rb') as f:
        size=struct.unpack('<Q',f.read(8))[0]
        if size>1024**2:raise CyToolError('InvalidModel','Invalid safetensors header.')
        header=json.loads(f.read(size))
    head=header.get('lm_head.weight',{});shape=tuple(head.get('shape',[]));offsets=head.get('data_offsets',[])
    if head.get('dtype')!='BF16' or len(shape)!=2 or shape[1]%32 or len(offsets)!=2 or offsets[1]-offsets[0]!=2*shape[0]*shape[1] or 8+size+offsets[1]>voice.stat().st_size:
        raise CyToolError('InvalidModel','Unsupported DarkIdol head geometry.')
    reader=GGUFReader(str(base));target=next((t for t in reader.tensors if t.name=='output.weight'),None)
    if target is None or tuple(reversed(target.shape))!=shape:raise CyToolError('IncompatibleModel','DarkIdol head does not match the base model output tensor.')
    arch=reader.fields['general.architecture'].contents()
    source=np.memmap(voice,dtype='<u2',mode='r',offset=8+size+offsets[0],shape=shape)
    scratch=ctx.path('temporary/darkidol-head-q8.bin');qshape=(shape[0],shape[1]//32*34)
    quantized=np.memmap(scratch,dtype=np.uint8,mode='w+',shape=qshape)
    temporary=dest.with_suffix('.preparing.gguf');writer=None
    try:
        for start in range(0,shape[0],512):
            ctx.cancellation.check();end=min(start+512,shape[0])
            values=(source[start:end].astype(np.uint32)<<16).view(np.float32)
            quantized[start:end]=quantize(values,Q.Q8_0)
            ctx.progress(60+15*end/shape[0],currentStep='Preparing DarkIdol output head')
        quantized.flush()
        writer=GGUFWriter(str(temporary),arch)
        for field in reader.fields.values():
            if field.name=='general.architecture' or field.name.startswith('GGUF.'):continue
            writer.kv_data[0][field.name]=GGUFValue(value=field.contents(),type=field.types[0],sub_type=field.types[-1] if len(field.types)>1 else None)
        for t in reader.tensors:
            data=quantized if t.name=='output.weight' else t.data
            writer.add_tensor_info(t.name,data.shape,data.dtype,data.nbytes,raw_dtype=Q.Q8_0 if t.name=='output.weight' else t.tensor_type)
        writer.write_header_to_file();writer.write_kv_data_to_file();writer.write_ti_data_to_file()
        for index,t in enumerate(reader.tensors):
            ctx.cancellation.check();writer.write_tensor_data(quantized if t.name=='output.weight' else t.data)
            ctx.progress(75+20*(index+1)/len(reader.tensors),currentStep='Writing separate DarkIdol model')
        writer.close();writer=None
        digest=sha(temporary,ctx);temporary.replace(dest)
        write_json(dest.with_suffix('.prepared.json'),{'recipe':info['recipe'],'voiceSha256':info['files'][0]['sha256'],'baseSha256':lm.catalog()[info['baseModel']]['files'][0]['sha256'],'sha256':digest,'size':dest.stat().st_size})
    finally:
        if writer:writer.close()
        source._mmap.close();quantized._mmap.close();scratch.unlink(missing_ok=True);temporary.unlink(missing_ok=True)
