#!/usr/bin/env python
# -*- coding: utf-8


'''
Created on 11/12/2014

@author: jeel
'''
import os
from tools.processing import processing

def mergePdfFilesInFolder(input_folder,pdf_dest):
    '''
    Merges all the pdf-files in a folder and outputs to a specified path
    '''
    src = os.path.join(input_folder,'*.pdf')
    cmd = 'pdftk {0} cat output {1}'.format(src,pdf_dest)
    processing.run_cmd(cmd,shell=True)
    
def joinPdfFiles(pdf_list,dest_path):
    '''
    Adds a list of pdf-files in front of a master pdf. It creates a new temp
    pdf in the temp_folder and if everything goes right, it overwrites the
    master with the outputted pdf-file.
    '''
    if len(pdf_list) == 0:
        raise ValueError('No pdf files to join')
    # Make sure that all pdf-files exists
    for pdf in pdf_list:
        if not os.path.exists(pdf):
            raise OSError('{0} does not exists.'.format(pdf))
    pdfs = ' '.join(pdf_list)
    cmd = 'pdftk {0} cat output {1}'.format(pdfs, dest_path)
    output = processing.run_cmd(cmd,shell=True)
    if output['erred'] or 'error' in str(output['stdout']):
        raise OSError('An error occured when converting files to pdf with ' 
                      'command {0}. Error: {1}.'.format(cmd,output))

def getDensity(src, layer):
    '''
    Use identify to get information about a pdf-file. Use some simple text
    search to get resolution fra raw identify-output
    :param src:
    :param layer:
    
    Notes: consider to output a default density (DPI), e.g. 72, if using 
    "identify" fails.
    '''
    
    cmd = 'identify -verbose {0}[{1}]'.format(src,layer)
    output = processing.run_cmd(cmd,shell=True)
    if output['erred'] or 'error' in str(output['stdout']):
        raise OSError('An error occured when identifying pdf-file with ' 
                      'command {0}. Error: {1}.'.format(cmd,output))
    # txt = (output['stdout'].decode('utf-8')).splitlines()
    txt_raw_list = (output['stdout']).splitlines()
    line_counter = 0
    txt = []
    for t in txt_raw_list:
        line_counter += 1
        try:
            t = t.decode('utf-8')
        except UnicodeError as e:
            t = "[skipped line {0} - Error: {1}]".format(line_counter, e)
            print(t)
        txt.append(t)
    res_s = 'Resolution: '
    res_e = 'x'
    rl = [l for l in txt if res_s in l]
    error = ('Resolusion could not be found with identify. Cmd: '
             '"{0}". Output: "{1}"'.format(cmd,txt))
    if len(rl) == 0: raise ValueError(error)
    rl = rl[0]
    res = rl[rl.find(res_s)+len(res_s):rl.find(res_e)]
    if not res.isdigit(): raise ValueError(error)
    res = int(res)
    return res
    


