from pathlib import Path
from copy import deepcopy
from zipfile import ZipFile
from lxml import etree as E
import ast, hashlib, json

ROOT = Path.cwd()
SOURCE = ROOT / 'thesis-13.docx'
OUT = ROOT / 'thesis-13-results-discussion-iteration-1-highlighted.docx'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
def tag(x): return '{'+W+'}'+x
def elem(name, **attrs):
    n = E.Element(tag(name))
    for k, v in attrs.items(): n.set(tag(k), str(v))
    return n

with ZipFile(SOURCE) as z:
    data = {n: z.read(n) for n in z.namelist()}
xml = E.fromstring(data['word/document.xml'])
body = xml.find('w:body', NS)
paras = body.findall('w:p', NS)
before = [E.tostring(n) for n in body]
start = list(body).index(paras[437])
end = list(body).index(paras[609])
prefix = before[:start]
suffix = before[end:]
def text(n): return ''.join(n.itertext())
def run(s, bold=False):
    r = elem('r'); pr = elem('rPr')
    if bold: pr.append(elem('b', val='1'))
    pr.append(elem('color', val='000000'))
    pr.append(elem('sz', val='22'))
    pr.append(elem('highlight', val='yellow'))
    r.append(pr); t = elem('t'); t.set('{http://www.w3.org/XML/1998/namespace}space','preserve'); t.text = s; r.append(t)
    return r
def paragraph(s, template=608, bold=False, heading=None, pagebreak=False):
    p = elem('p')
    oldpr = paras[template].find('w:pPr', NS)
    pr = deepcopy(oldpr) if oldpr is not None else elem('pPr')
    for name in ['numPr', 'rPr', 'sectPr', 'pageBreakBefore', 'outlineLvl']:
        for n in pr.findall('w:'+name, NS): pr.remove(n)
    if heading is not None:
        for n in pr.findall('w:jc', NS): pr.remove(n)
        pr.append(elem('jc', val='left'))
        pr.append(elem('outlineLvl', val=heading))
        pr.append(elem('keepNext', val='1'))
        pr.append(elem('keepLines', val='1'))
    if pagebreak: pr.append(elem('pageBreakBefore', val='1'))
    p.append(pr); p.append(run(s,bold)); return p
def replace(index, s):
    p = paras[index]
    for n in list(p):
        if n.tag != tag('pPr'): p.remove(n)
    p.append(run(s))
def table(rows, widths):
    tbl = elem('tbl'); pr = elem('tblPr')
    # Preserve the source chapter's plain black grid, Arial 11 and cell padding.
    sourcepr = body.findall('w:tbl',NS)[30].find('w:tblPr',NS)
    for n in sourcepr:
        if n.tag not in [tag('tblStyle'),tag('tblW')]: pr.append(deepcopy(n))
    pr.insert(0,elem('tblW',w=sum(widths),type='dxa'))
    tbl.append(pr); grid = elem('tblGrid')
    for width in widths: grid.append(elem('gridCol',w=width))
    tbl.append(grid)
    for ri, row in enumerate(rows):
        tr = elem('tr'); trpr = elem('trPr'); trpr.append(elem('cantSplit',val='1'))
        if ri == 0: trpr.append(elem('tblHeader',val='1'))
        tr.append(trpr)
        for ci, s in enumerate(row):
            tc = elem('tc'); cp = elem('tcPr'); cp.append(elem('tcW',w=widths[ci],type='dxa'))
            mar=elem('tcMar')
            for side in ['top','left','bottom','right']: mar.append(elem(side,w=100,type='dxa'))
            cp.append(mar); cp.append(elem('vAlign',val='center')); tc.append(cp)
            p=elem('p'); pp=elem('pPr'); pp.append(elem('spacing',before=0,after=0,line=240,lineRule='auto'))
            pp.append(elem('jc',val='center' if ri==0 or (len(widths)==2 and ci==1) else 'left'))
            if len(rows) == 5 and ri < len(rows)-1: pp.append(elem('keepNext',val='1'))
            p.append(pp); p.append(run(str(s),ri==0 or row[0]=='Total')); tc.append(p); tr.append(tc)
        tbl.append(tr)
    return tbl
def caption(s):
    p=paragraph(s,604)
    pp=p.find('w:pPr',NS)
    for n in pp.findall('w:jc',NS): pp.remove(n)
    pp.append(elem('jc',val='center')); pp.append(elem('keepNext',val='0'))
    for n in pp.findall('w:spacing',NS): pp.remove(n)
    pp.append(elem('spacing',before=120,after=120,line=240,lineRule='auto'))
    p.find('w:r/w:rPr',NS).append(elem('i',val='1'))
    return p
def spacer():
    p=elem('p'); pp=elem('pPr'); pp.append(elem('spacing',before=0,after=0,line=240,lineRule='auto')); p.append(pp); return p

replace(439, "This section presents the baseline evaluation and the revisions completed during Iteration 1 of MENDO. It discusses symptom detection results and documents the changes made to the symptom dictionary, keyword processing, medicine catalog, and recommendation rules following consultation with a pharmacist.")
replace(441, "The Iteration 1 revisions were implemented across symptom extraction, hybrid matching, and medicine recommendation. The active medicine catalog and validation label definitions were also updated to apply the revised scope consistently.")
replace(444, "During Iteration 1, a baseline evaluation was performed on the initial version of MENDO to assess symptom detection and identify recurring errors. The following tables report the results recorded before the revisions described later in this iteration. Toothache is retained in these baseline tables because it was included in the symptom scope at the time of that evaluation.")
replace(608, "The baseline findings show recurring differences in symptom recognition and negation handling across the tested categories and languages. During the same iteration, the researchers revised the symptom scope and medicine selection following consultation with a pharmacist and aligned the implementation with these decisions. The following subsections document the dictionary, keyword, medicine, and recommendation changes completed during Iteration 1.")
body.insert(list(body).index(paras[439]),paragraph('Iteration 1',443,bold=True,heading=1))
# Keep the source baseline hierarchy subordinate to the new iteration heading.
baselinepr=paras[443].find('w:pPr',NS)
oldoutline=baselinepr.find('w:outlineLvl',NS)
if oldoutline is not None: baselinepr.remove(oldoutline)
baselinepr.append(elem('outlineLvl',val=2))
for r in paras[443].findall('w:r',NS):
    rp=r.find('w:rPr',NS)
    if rp is None: rp=elem('rPr'); r.insert(0,rp)
    rp.append(elem('highlight',val='yellow'))

added=[]
def p(s): added.append(paragraph(s))
def h(s): added.extend([spacer(),paragraph(s,443,bold=True,heading=2,pagebreak=s.startswith('B.'))])
def t(rows,widths,label): added.extend([table(rows,widths),caption(label),spacer()])

h('B. Revisions to the Symptom Dictionary')
p("Following the pharmacist consultation, the researchers removed toothache from the supported symptom scope. The TOOTHACHE label and its 53 English, Filipino, Taglish, and Bisaya/Cebuano dictionary phrases were deleted. This included expressions such as ‘toothache,’ ‘sakit ng ngipin,’ ‘ngilo,’ and ‘sakit akong ngipon.’ The revised dictionary contains 13 supported labels and 541 phrase entries, as shown in Table 22.")
tree=ast.parse((ROOT/'mendo_core/step1.py').read_text(encoding='utf-8'))
dictionary=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.AnnAssign) and getattr(n.target,'id','')=='SYMPTOM_DICTIONARY')
labels=['HEADACHE','FEVER','BODY_ACHES','RASHES','STOMACH_ACHE','SORE_THROAT','COUGH_PRODUCTIVE','ALLERGIC_RHINITIS','COUGH_GENERAL','COUGH_DRY','DIARRHEA','NASAL_CONGESTION','RUNNY_NOSE']
t([['Supported symptom label','Phrase entries']]+[[k,len(dictionary[k])] for k in labels]+[['Total',sum(map(len,dictionary.values()))]],[6500,2500],'Table 22. Revised Symptom Dictionary during Iteration 1')
p("To apply the scope change consistently, toothache was also removed from the standard and advanced fuzzy matching anchors and from the proximity rule that previously detected pain near tooth-related words. The standard English fuzzy anchor list consequently changed from 18 to 17 entries. The annotation import and export tools were aligned with the same 13-label set. Historical toothache cases were retained in the evaluation records, with their current expected output marked as outside the supported scope.")

h('C. Revisions to Keyword Processing')
p("Removing the dictionary label required corresponding changes to keyword handling. Dental terms were retained as exclusion cues so that a dental complaint would not be reassigned to another supported symptom. These cues include ‘tooth,’ ‘teeth,’ ‘molar,’ ‘ngipin,’ ‘ngipon,’ ‘bagang,’ and ‘ngilo,’ together with recognized misspellings such as ‘tootache’ and ‘totache.’ Dental anatomy terms no longer generate a symptom label through the body-part rules.")
p("The revised extraction rule requires independent dictionary evidence before retaining nasal, cough, bodyache, or sore-throat labels in a statement containing dental terms. This prevents a word such as ‘ngipon’ from being treated as ‘sipon’ through fuzzy matching. When dental terms are present without a supported dictionary match, the hybrid detector skips semantic fallback and records the dental complaint as outside the supported scope. Independently stated supported symptoms remain eligible for processing in mixed complaints. Table 23 shows representative cases covered by the revised rules.")
t([['Input expression','Revised symptom output'],
 ['toothache / tootache / totache','No supported symptom'],
 ['masakit ang ngipin ko','No supported symptom'],
 ['sakit akong ngipon','No supported symptom; not RUNNY_NOSE'],
 ['pain in one of my teeth','No supported symptom'],
 ['toothache and fever','FEVER'],
 ['sakit akong ngipon ug sipon','RUNNY_NOSE']],[5200,3800],'Table 23. Keyword Handling after Toothache Removal')
p("The recommendation engine also discards TOOTHACHE if it is submitted by an older client. A dental-only complaint receives no medicine recommendation and a message advising consultation with a dentist or pharmacist. This applies the revised symptom scope at both detection and recommendation stages.")

h('D. Revisions to the Medicine Catalog')
p("The pharmacist consultation led to four changes in the selected medicine list: Neozep was replaced with Buscopan, Tuseran with Sinecod, ibuprofen/Advil with Kremil-S, and Erceflora with a proposed generic Lactobacillus acidophilus product. The implementation was updated to reflect the revised products and their intended indications, as summarized in Table 24.")
t([['Previous selection','Revised selection','Implemented use or status'],
 ['Neozep','Buscopan','Active antispasmodic option for abdominal cramps'],
 ['Tuseran','Sinecod','Active cough suppressant option for dry cough'],
 ['Ibuprofen / Advil','Kremil-S','Active antacid option for acidity-related stomach complaints'],
 ['Erceflora','Lactobacillus acidophilus','Inactive generic placeholder; no product selected']],[2100,2700,4200],'Table 24. Pharmacist-Guided Medicine Revisions during Iteration 1')
p("Buscopan was assigned to abdominal cramping or spasm, consistent with its hyoscine N-butylbromide antispasmodic indication (Opella Healthcare Philippines, n.d.). Kremil-S was assigned to hyperacidity and related gastric discomfort, consistent with its antacid formulation (Unilab, n.d.). These changes required distinct symptom-to-medicine mappings because the revised products have different indications from the medicines they replaced in the selected list.")
p("Sinecod was linked to the existing Sinecod Forte butamirate citrate record for dry cough. The minimum age in that medicine record was corrected from 6 to 13 years, and the active catalog also uses 13 years. This represents the 50 mg tablet listing’s ‘over 12 years’ requirement within the application’s whole-year age input (Watsons Philippines, n.d.). The corresponding notes and contraindication text were revised to refer to that tablet formulation.")
p("Kremil-S’s dosage form was changed from ‘Tablet’ to ‘Chewable Tablet,’ and ‘stomach cramps’ was removed from its typical symptom list. The indication-source fields for Kremil-S, Buscopan, and Sinecod were updated with their product-information links. Neozep, Tuseran, Advil, and Erceflora are excluded from the active recommendation catalog, while their reference records remain in the source medicine dataset.")
p("The proposed Lactobacillus acidophilus replacement was recorded as an inactive generic placeholder because the consultation did not identify an exact brand or formulation. No strength, colony-forming unit count, dosage form, or age requirement was assigned to it. It is excluded from recommendation and purchase. The revised active catalog therefore contains nine products: Kremil-S, Bioflu, Biogesic, Cetirizine, Solmux, Sinecod, Symdex, Buscopan, and Loperamide.")

h('E. Revisions to Recommendation Rules')
p("The recommendation rules were revised together with the medicine catalog. For an acidity-related stomach complaint, candidate selection is restricted to the antacid category, represented by Kremil-S. For abdominal cramping, it is restricted to the antispasmodic category, represented by Buscopan. The previous fallback that could select another stomach medicine despite a known acidity or cramping context was removed. The existing clarification step continues to collect the character of an unspecified stomach complaint before applying these routes.")
t([['Context','Revised recommendation behavior'],
 ['Acidity / burning stomach discomfort','Select Kremil-S through the antacid route'],
 ['Abdominal cramping / spasm','Select Buscopan through the antispasmodic route'],
 ['Dry cough','Select Sinecod through the cough suppressant route; apply the tablet age filter'],
 ['Productive cough','Retain Solmux as the productive-cough option'],
 ['Dental-only complaint / retired TOOTHACHE label','Return no medicine recommendation'],
 ['Proposed Lactobacillus acidophilus product','Exclude the inactive placeholder from recommendations']],[3400,5600],'Table 25. Recommendation Rules Aligned with the Revised Catalog')
p("Dry-cough matching now uses Sinecod in place of Tuseran, while productive-cough matching retains Solmux. The existing warning for simultaneous cough suppressant and expectorant recommendations remains applicable. Kremil-S is matched to acidity-related complaints and does not inherit ibuprofen’s headache, fever, or body-pain indications. In the diarrhea warning, the named Erceflora reference was replaced with a generic statement about a pharmacist-approved probiotic as an adjunct to oral rehydration, consistent with the removal of Erceflora from the active catalog.")

added.extend([spacer(),paragraph('References for the Iteration 1 Revisions',446,bold=True,heading=3)])
p("Opella Healthcare Philippines. (n.d.). Hyoscine N-butylbromide (Buscopan). Retrieved October 13, 2026, from https://www.buscopan.com/en-ph/products/buscopan")
p("Unilab. (n.d.). Kremil-S product information. Retrieved October 13, 2026, from https://www.unilab.com.ph/products/kremil-s?sku=299")
p("Watsons Philippines. (n.d.). Sinecod butamirate citrate 50 mg tablet. Retrieved October 13, 2026, from https://www.watsons.com.ph/sinecod-sinecod-sinecod-butamirate-citrate-50mg-sold-per-piece/p/BP_10002745")
for reference in added[-3:]:
    rp=reference.find('w:pPr',NS)
    for n in rp.findall('w:jc',NS): rp.remove(n)
    rp.append(elem('jc',val='left'))
for reference in added[-3:-1]: reference.find('w:pPr',NS).append(elem('keepNext',val='1'))
at=list(body).index(paras[609])
for n in added: body.insert(at,n); at+=1

after=[E.tostring(n) for n in body]
assert after[:start] == prefix, 'Content before Results and Discussion changed'
assert after[-len(suffix):] == suffix, 'Content after Results and Discussion changed'
newtext=' '.join(''.join(n.itertext()) for n in added)
assert not any(x in newtext.lower() for x in ['hardware','iteration 2','limitations','raspberry','slot']), 'Unrequested content'
assert len(dictionary)==13 and sum(map(len,dictionary.values()))==541
data['word/document.xml']=E.tostring(xml,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(SOURCE) as zi, ZipFile(OUT,'w') as zo:
    for info in zi.infolist(): zo.writestr(info,data[info.filename])
with ZipFile(SOURCE) as zi, ZipFile(OUT) as zo:
    changed=[n for n in zi.namelist() if zi.read(n)!=zo.read(n)]
assert changed==['word/document.xml'], changed
report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'output':str(OUT),'changed_package_parts':changed,'unchanged_before_results':len(prefix),'unchanged_after_results':len(suffix),'new_tables':4,'new_text_words':len(newtext.split()),'all_original_baseline_tables_preserved':True}
(ROOT/'.tmp/rd-rebuild-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
