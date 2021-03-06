#!/usr/bin/env python
# -*- coding: utf-8
'''
Created on 26/03/2014

@author: jeel
'''

import os
from goobi.goobi_step import Step
from tools.image_processing import image_preprocessor
from tools.image_tools import misc as image_tools
from tools.filesystem import fs


class PreprocessDodImageFiles( Step ) :

    def setup(self):
    
        self.name = "Automatisk billedbehandling"
        self.config_main_section = "preprocess_images"
        self.essential_config_sections = set( [] )
        self.folder_structure_section = 'process_folder_structure'
        self.valid_file_exts_section= 'valid_file_exts'
        self.essential_config_sections.update([self.folder_structure_section,
                                               self.valid_file_exts_section] )
        self.essential_commandlines = {
            "process_path":"folder",
            "step_id":"number",
            'process_title':'string'
        }
    
    def step(self):
        error = None
        try:
            #===================================================================
            # Get and set variables and settings for preprocessing
            # self.settings contains settigs for preprocessing script
            #===================================================================
            self.getVariables()
            #===================================================================
            # Remove previously preprocessed images
            #===================================================================
            fs.clear_folder(self.img_pre_processed_path)
            #===================================================================
            # Preprocess images
            #===================================================================
            ip = image_preprocessor.ImagePreprocessor(self.img_master_path,
                                                      self.settings,
                                                      self.glogger,
                                                      self.debug)
            ip.processFolder()
        except image_tools.ConvertError as e:
            error = str(e)
        return error

    
    def getVariables(self):
        '''
        Get all required vars from command line + config
        and confirm their existence.
        '''
        process_root = self.command_line.process_path
        process_title = self.command_line.process_title
        #=======================================================================
        # Set path to input folder, which files to be preprocessed
        #=======================================================================
        master_img_rel = self.getConfigItem('img_master_path',
                                            section = self.folder_structure_section) 
        self.img_master_path = os.path.join(process_root, master_img_rel)
        #=======================================================================
        # Set destination path to output preprocessed images
        #=======================================================================
        img_pre_processed_path = self.getConfigItem('img_pre_processed_path',
                                            section = self.folder_structure_section)
        self.img_pre_processed_path = os.path.join(process_root,
                                                   img_pre_processed_path)
        #=======================================================================
        # Get and set settings for ImagePreprocessor
        # Most of these are found in config.ini, but can also be set 
        # specifically for a process for testing
        #=======================================================================
        self.settings = dict()
        #=======================================================================
        # # output_image_location
        #=======================================================================
        self.settings['output_image_location'] = self.img_pre_processed_path
        #=======================================================================
        # # valid_exts: which file types to process
        #=======================================================================
        v_exts = self.getConfigItem('valid_file_exts',
                                    section=self.valid_file_exts_section)
        self.settings['valid_exts'] = v_exts.split(';')
        self.settings['process_title'] = process_title
        #=======================================================================
        # # temp_location: where to tempoarily store data -> absolute path
        #=======================================================================
        self.settings['temp_location'] = self.getSetting('temp_location')
        #=======================================================================
        # # output_images: output images?
        #=======================================================================
        self.settings['output_images'] = self.getSetting('output_images',
                                                         var_type=bool)
        #=======================================================================
        # # output_pdf: output a pdf-file from the preprocessed images?
        #=======================================================================
        self.settings['output_pdf'] = self.getSetting('output_pdf',
                                                      var_type=bool)
        #=======================================================================
        # # debug_pivot: Print debug for every N images processed 
        # #only used in few placed
        #=======================================================================
        self.settings['debug_pivot'] = self.getSetting('debug_pivot',
                                                       var_type=int)
        #=======================================================================
        # # has_binding: preprocess first and last image file?
        #=======================================================================
        self.settings['has_binding'] = self.getSetting('has_binding',
                                                       var_type=bool)
        #=======================================================================
        # # remove_binding: do not add first and last image file to outputfolder
        # # only meaningfull if has_binding is True
        #=======================================================================
        self.settings['remove_binding'] = self.getSetting('remove_binding',
                                                          var_type=bool)
        #=======================================================================
        # # crop_images: turn mechanism to crop images on/off.
        #=======================================================================
        self.settings['crop_images'] = self.getSetting('crop_images',
                                                       var_type=bool)
        #=======================================================================
        # # bw_for_innercrop: create a bw image of original to get crop
        # # coordinates from?
        #=======================================================================
        self.settings['bw_for_innercrop'] = self.getSetting('bw_for_innercrop',
                                                            var_type=bool)
        #=======================================================================
        # # innercrop_bw_src_threshold: if "bw_for_innercrop" is true then
        # # what threshold to use?
        #=======================================================================
        self.settings['innercrop_bw_src_threshold'] = self.getSetting('innercrop_bw_src_threshold',
                                                                      var_type=float)
        #=======================================================================
        # # innercrop_fuzzval: fuzzval for innercrop. Read documentation:
        # # http://www.fmwconcepts.com/imagemagick/innercrop/index.php
        #=======================================================================
        self.settings['innercrop_fuzzval'] = self.getSetting('innercrop_fuzzval',
                                                             var_type=int)
        #=======================================================================
        # # innercrop_mode: mode for innercrop. Read documentation:
        # # http://www.fmwconcepts.com/imagemagick/innercrop/index.php
        # # only meaningful for debugging
        #=======================================================================
        self.settings['innercrop_mode'] = self.getSetting('innercrop_mode')
        #=======================================================================
        # # crop_select_limit_adjust: how much to adjust the calculated limit of 
        # # crop coordinates that are used to select crop coordinates. 3 = 300%
        #=======================================================================
        self.settings['crop_select_limit_adjust'] = self.getSetting('crop_select_limit_adjust',
                                                                    var_type=float)
        #=======================================================================
        # # crop_select_limit_type: which method to use to calculate the limit
        # # for selecting crop coordinates. Valid: ['mean','avg']
        #=======================================================================
        self.settings['crop_select_limit_type'] = self.getSetting('crop_select_limit_type')
        #=======================================================================
        # # deskew_images: turn mechanism to deskew images on/off.
        #=======================================================================
        self.settings['deskew_images'] = self.getSetting('deskew_images',
                                                         var_type=bool)
        #=======================================================================
        # # deskew_select_limit_adjust: how much to adjust the calculated limit of 
        # # deskews that are used to select deskew angles. 5.5 = 550%
        # # experience tells that this one should be high
        #=======================================================================
        self.settings['deskew_select_limit_adjust'] = self.getSetting('deskew_select_limit_adjust',
                                                                      var_type=float)
        #=======================================================================
        # # deskew_select_limit_type: which method to use to calculate the limit
        # # for selecting deskew angles. Valid: ['mean','avg']
        #=======================================================================
        self.settings['deskew_select_limit_type'] = self.getSetting('deskew_select_limit_type')
        #=======================================================================
        # # deskew_select_abs_limit: If an absolute deskew angle is below 
        # # this, don't deskew image
        #=======================================================================
        self.settings['deskew_select_abs_limit'] = self.getSetting('deskew_select_abs_limit',
                                                                   var_type=float)
        #=======================================================================
        # # spread_detection: whether to detect spreads and leave them out of
        # # preprocessing
        #=======================================================================
        self.settings['spread_detection'] = self.getSetting('spread_detection',
                                                            var_type=bool)
        #=======================================================================
        # # spread_select_limit_adjust: how much to adjust the calculated limit of 
        # # spreads that are used to select spreads. 1.25 = 125%
        #=======================================================================
        self.settings['spread_select_limit_adjust'] = self.getSetting('spread_select_limit_adjust',
                                                                      var_type=float)
        #=======================================================================
        # # output_resize: resize the output images, e.g. 200% fra 300DPI to 600DPI
        # # if = 100, no resize
        #=======================================================================
        self.settings['output_resize'] = self.getSetting('output_resize',
                                                         var_type=int)
        #=======================================================================
        # # skip_if_pdf_exists: skip if pdf exists?
        #=======================================================================
        self.settings['skip_if_pdf_exists'] = self.getSetting('skip_if_pdf_exists',
                                                              var_type=bool)
        #=======================================================================
        # # innercrop_location: the relative path to where the innercrop script is placed
        #=======================================================================
        innercrop_loc = self.getSetting('innercrop_location')
        self.settings['innercrop_location'] = os.path.join(process_root,innercrop_loc)
        #=======================================================================
        # # innercrop_exe_path: the absolute path to where the innercrop script should be executed from
        #=======================================================================
        self.settings['innercrop_exe_path'] = self.getSetting('innercrop_exe_path')
        
if __name__ == '__main__' :
    PreprocessDodImageFiles().begin()
