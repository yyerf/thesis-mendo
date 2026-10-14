from pathlib import Path
import os, sys, tempfile, importlib.util
from PIL import Image, ImageDraw
root=Path.cwd()
out=root/'.tmp/rd-render'
out.mkdir(exist_ok=True)
scratch=root/'.tmp/rd-render-temp'
scratch.mkdir(exist_ok=True)
tempfile.tempdir=str(scratch)
os.environ['PATH']=r'C:\Users\john\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin'+os.pathsep+os.environ['PATH']
skill=Path(r'C:\Users\john\.codex\plugins\cache\openai-primary-runtime\documents\26.1011.11113\skills\documents')
sys.path.insert(0,str(skill))
spec=importlib.util.spec_from_file_location('render_docx',skill/'render_docx.py')
renderer=importlib.util.module_from_spec(spec); spec.loader.exec_module(renderer)
renderer.convert_to_pdf=lambda *args,**kwargs:(str(root/'.tmp/rd-preview.pdf'),'Read-only Microsoft Word export')
renderer.rasterize(str(root/'thesis-13-results-discussion-iteration-1-highlighted.docx'),str(out),dpi=96,verbose=False,emit_pdf=False)
pages=sorted(out.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))
for offset in range(0,len(pages),4):
    chunk=pages[offset:offset+4]
    sheet=Image.new('RGB',(1632,2168),'#eeeeee'); draw=ImageDraw.Draw(sheet)
    for j,p in enumerate(chunk):
        im=Image.open(p).convert('RGB')
        x=(j%2)*816;y=(j//2)*1084
        draw.text((x+10,y+5),p.stem,fill='black');sheet.paste(im,(x,y+24))
    sheet.save(out/f'contact-{offset//4+1:02d}.png')
print(f'Rendered {len(pages)} pages; {((len(pages)+3)//4)} contact sheets at native resolution')
