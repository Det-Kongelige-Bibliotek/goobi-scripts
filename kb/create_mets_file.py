#!/usr/bin/env python
# -*- coding: utf-8

import os
from goobi.goobi_step import Step
from tools.xml_tools import dict_tools, xml_tools
from tools.mets import mets_tools


class CreateMetsFile(Step):
    def setup(self):
        self.name = 'Oprettelse af METS-filer'
        self.config_main_section = 'create_mets_file'
        self.essential_config_sections = set(['process_folder_structure', 'process_files'])
        self.essential_commandlines = {
            'process_path': 'folder'
        }

    def step(self):
        error = None
        try:
            self.getVariables()
            self.checkPaths()
            self.createMetsFile()
        except ValueError as e:
            error = e
        except IOError as e:
            error = e.strerror
        except OSError as e:
            error = e
        return error


    def getVariables(self):
        """
        This method pulls in all the variables
        from the command line and the config file
        that are necessary for its running.
        We need a path to our toc file, our meta.xml
        and a link to our DBC data service (eXist API).
        Errors in variables will lead to an
        Exception being thrown.
        """
        self.meta_file = os.path.join(
            self.command_line.process_path,
            self.getConfigItem('metadata_goobi_file', section='process_files')
        )
        self.img_src = os.path.join(
            self.command_line.process_path,
            self.getConfigItem('img_master_path', section='process_folder_structure')
        )


    def checkPaths(self):
        """
        Check if the file meta.xml exist and check if there are files in
        master_orig folder.
        """
        if not os.path.exists(self.meta_file):
            err = '{0} does not exist.'.format(self.meta_file)
            raise OSError(err)
        if not len(os.listdir(self.img_src)):
            err = '{0} is empty and must contain files.'.format(self.img_src)
            raise OSError(err)


    def createMetsFile(self):
        """
        Given a toc object consisting of articles with dbc ids
        use the DBC service to 	generate data for each article.
        When all data is created, append this to the exising
        meta.xml data
        """
        # legr: Parse the META.XML and put it into a dictionary tree
        dt, _ = dict_tools.parseXmlToDict(self.meta_file)

        # legr: Dont do anything if there already are FILE_nnnn's and PHYS_nnnn's in the META.XML
        # legr: todo : what if a step is pushed back because of missing images. When they are added, this doesn't get
        # legr: todo : updated? I think we need a possibilty to clean the mets-file.
        if not mets_tools.containsImages(dt):
            # legr: we are here because META.XML was empty, so FILE_nnnn and PHYS_nnnn references to actual files
            # legr: in /master_orig/
            dt = mets_tools.addImages(dt, self.img_src)
            # legr: now update the META.XML with the references from above
            # legr: it seems the overall META.XML file structure also is somewhat reformatted - METS standard?
            xml_tools.writeDictTreeToFile(dt, self.meta_file)


if __name__ == '__main__':
    CreateMetsFile().begin()