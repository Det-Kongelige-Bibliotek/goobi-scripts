#!/usr/bin/env python
# -*- coding: utf-8

"""
Created on 19/06/2014

@author: jeel
"""
import signal
import sys
import os
import json

lib_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__))+os.sep+'../')
sys.path.append(lib_path)
from goobi.step_job_processor import StepJobProcessor, StepJobQueue
from goobi.tcp_server import StepJobTCPServer, StepJobTCPHandler
import tools.logging.logger as logger

class ConvertServer():
    
    def signal_term_handler(self,signal, frame):
        self.logger.info('Processor terminated with SIGTERM. Closing gently down.')
        self.server.server_close()
        self.logger.info('Server closed.')
        self.logger.info('Closing {0} step job processor(s).'.format(len(self.step_job_processors)))
        for step_processor in self.step_job_processors:
            step_processor.stop()
            step_processor.join()
        self.logger.info('{0} step job processor(s) stopped.'.format(len(self.step_job_processors)))
        self.logger.log_section('Existing server.')
        sys.exit(0)
    
    def __init__(self,config_path=None):
        '''
        Initialize step server.
        
        NB: confGet not yet implemented. Consider using 
        kb/config/config_reader.py and thus use the settings in 
        kb/workflows/system/config.ini
        
        ''' 
        def confGet(config, var,default):
            if not config: return default
            if not var in config: return default
            return config[var]
        
        config = None
        if config_path and os.path.exists(config_path):
            config = json.load(config_path, parse_float= True, parse_int=True)
        
        # Setup logger
        log_path = confGet(config,'log_path','/opt/digiverso/logs/step_server/')
        log_level = confGet(config,'log_level','INFO')
        self.logger = logger.logger(log_path,log_level)
        self.logger.log_section('Setting up step server')
        # Setup host and port for connection
        host = confGet(config,'host','localhost')
        port = confGet(config,'port',37000)
        self.address = (host, port)
        # Create one processor per core - tesseract 3.03 is not multithreaded
        # TODO: Add functionality so first thread will always take from non shared
        # queue, and the others always from the shared.
        # I.e. if multiple threads call a program with multithreading built-in
        # the system will heavily loaded. 
        self.core_num = confGet(config,'core_num',1)
        self.step_job_processors = []
        
        self.job_queue = StepJobQueue(self.logger)
        # Create StepJobProcesser and StepJobServer 
        self.logger.info('Initiating {0} step job processor(s)...'.format(self.core_num))
        for i in range(self.core_num):
            self.logger.info('Initiating step job processor {0}...'.format(i+1))
            self.step_job_processors.append(StepJobProcessor(shared_job_queue=self.job_queue,
                                                             logger=self.logger))
        self.logger.info('Step job processor(s) started.')
        self.server = StepJobTCPServer(server_address = self.address,
                                       RequestHandlerClass = StepJobTCPHandler,
                                       bind_and_activate=True,
                                       step_job_queue= self.job_queue,
                                       logger=self.logger)
    
    def start(self):
        self.logger.log_section('Starting step job processor(s)...')
        for step_processor in self.step_job_processors:
            step_processor.start()
            self.logger.info('Step job processor started.')
        self.logger.info('Step server started, awaiting jobs...')
        signal.signal(signal.SIGTERM, self.signal_term_handler)
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            msg = 'KeyboardInterrupt called. Closing server gently.'
            self.logger.log_section(msg)
        except Exception as e:
            err = 'An error occured: {0}. Closing server gently.'
            err = err.format(str(e))
            self.logger.log_section(err,log_level='ERROR')
        self.server.server_close()
        self.logger.info('Server closed.')
        self.logger.log_section('Stopping {0} step job processor thread(s).'.format(len(self.step_job_processors)))
        for step_processor in self.step_job_processors:
            step_processor.stop()
            step_processor.join()
            self.logger.info('{0} step job processor thread stopped.')
        self.logger.info('{0} step job processor thread(s) stopped.'.format(len(self.step_job_processors)))
        self.logger.log_section('Existing server.')

if __name__ == "__main__":
    cs = ConvertServer()
    cs.start()
