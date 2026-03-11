# -*- coding: utf-8 -*-
import json
import glob
import os
os.chdir(r'c:\Users\owner\war')
nb_path = glob.glob('*.ipynb')[0]
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)
keywords = ['원자재','금융','공포','VIX','외환','주식','원유','WTI','Brent','코스피','S&P','Vix','vix','yfinance','yahoo','fred','금가격','변동','위기','크레딧','credit','fear','PART II','part 2','위기지표']
open('crisis_cells.txt', 'w', encoding='utf-8').close()
for i, c in enumerate(nb['cells']):
    src = ''.join(c.get('source', []))
    if any(k in src for k in keywords):
        with open('crisis_cells.txt', 'a', encoding='utf-8') as out:
            out.write('--- CELL %d ---\n%s\n\n' % (i, src[:4000]))
