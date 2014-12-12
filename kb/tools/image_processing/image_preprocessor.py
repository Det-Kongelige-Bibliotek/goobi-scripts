#!/usr/bin/env python
# -*- coding: utf-8
'''
Created on 11/12/2014

@author: jeel
'''
import os, datetime, sys,shutil
import time
import pprint
from tools.pdf import misc as pdf_tools
from tools.image_tools import misc as image_tools
from tools.filesystem import fs

class ImagePreprocessor():
    def __init__(self,src,settings,debug=False):
        self.settings = settings
        self.debug = debug
        if self.debug: pprint.pprint(self.settings)
        self.source_folder = src.rstrip(os.sep) # remove tailing / or \
        self.source_name = os.path.basename(self.source_folder)
        self.source_root = os.path.dirname(self.source_folder)
        self.output_root_location = self.settings['output_image_location']
        self.temp_folder = os.path.join(self.settings['temp_location'],self.source_name)
        self.pdf_dest = os.path.join(self.output_image_location,self.source_name+'.pdf')
        self.dest_folder = os.path.join(self.source_root,self.source_name+'_output')
        # Create output and working folders
        self.createFolders(self.output_image_location,
                           self.temp_folder,
                           self.dest_folder)
        if self.settings['output_images']: self.createFolders(self.output_image_location)
        
        # Change working dir so innercrop and imagemagick will use ramdisk for temp files
        os.chdir('/tmp/ramdisk/')
        ## Varaibles for the individual images
        self.img_proc_info = {'avg_time_stat': {},'images':{}}
        self.bindings = []
        ## Presumed in settings:
        #valid_exts = ['.tif','.jpg']
        # temp_location = '/tmp/ramdisk/'
    
    def createFolders(self,*folders):
        for folder in folders:
            if not os.path.exists(folder):
                os.mkdir(folder)
    
    def deleteWorkingFolders(self):
        fs.clear_folder(self.temp_folder, also_folder=True)
        fs.clear_folder(self.dest_folder, also_folder=True)
    
    def processFolder(self):
        if self.settings['skip_if_pdf_exists']:
            if os.path.exists(self.pdf_dest):
                self.deleteWorkingFolders()
                return
        try:
            self._process()
        except image_tools.InnerCropError as e:
            print('Innercrop erred for folder: {0}'.format(self.source_folder))
            self.deleteWorkingFolders()
            raise(e)
        except KeyboardInterrupt as e:
            self.deleteWorkingFolders()
            raise(e)
        except Exception as e:
            self.deleteWorkingFolders()
            raise(e)
        self.deleteWorkingFolders()
        
    def _process(self):
              
        # Initialize dictionary for image processing information
        self.getImageInformation()
        # Overvej:
            # måske der skal hentes statistik for bøgernes størrelse, således
            # at opslag ikke cropImage'es og deskewImage'es
            # f.eks. tilføjelse 'spread': False -> 
        if self.settings['spread_detection']: self.locate_spreads()
        # Get all cropping coordinates and evaluate these
        self.getCropCoordinates()
        # Select cropImage coordinates
        self.set_crop()
        # Crop images e.g. with output to bw-image file on ramdisk -> smaller and bw may be better for deskewImage test?
        self.create_temp_crops()
        # Get all deskewImage
        self.get_deskew_angles()
        # Select which images to deskewImage 
        self.set_deskew()
        # Process files
        self.processFiles()
        pprint.pprint(self.img_proc_info)
        if self.debug: print(str(datetime.datetime.now())+': '+'Merge pdf files to one pdf')
        if self.settings['output_pdf']:
            pdf_tools.mergePdfFilesInFolder(self.dest_folder,self.pdf_dest)
    
    def processFiles(self):
        file_paths = sorted(self.img_proc_info['images'].keys())
        for file_path in file_paths:
            info = self.img_proc_info['images'][file_path]
            proc_time_stat = self.processFile(file_path,info)
            self.add_to_avg_time_stat(proc_time_stat)
            fs.clear_folder(self.temp_folder)
        if self.settings['has_binding'] and not self.settings['remove_binding']:
            for b in self.bindings:
                file_name,_ = os.path.splitext(os.path.basename(b.rstrip(os.sep)))
                b_pdf_dest = os.path.join(self.dest_folder,file_name+'.pdf')
                if self.settings['output_images']: shutil.copy2(b,self.output_image_location)
                if self.settings['output_pdf']: image_tools.compressFile(b,b_pdf_dest,resize=50,quality=33)
    
    def processFile(self,file_path,info):
        time_stat = {}
        file_name,_ = os.path.splitext(os.path.basename(file_path.rstrip(os.sep)))
        if self.debug: print('File: {0}'.format(file_name))
        # 1: cropImage image with coordinates
        if self.debug: print('\tCrop image')
        t = time.time()
        file_path = image_tools.cropImage(file_path,self.temp_folder,info)
        time_stat['Crop image'] = time.time()-t
        # 2: deskewImage
        if info['deskewImage']:
            if self.debug: print('\tDeskew image')
            t = time.time()
            # Jeg har sat quality til 50% så de ikke fylder så meget når jeg skal gemme de resulterende jpgs til OCR
            file_path = image_tools.deskewImage(file_path,self.temp_folder,info['deskew_angle'],quality=50,resize=200)
            time_stat['Deskew image'] = time.time()-t
        else:
            if self.debug: print('\tNo deskewing')
            t = time.time()
            file_name,_ = os.path.splitext(os.path.basename(file_path))
            dest = os.path.join(self.temp_folder,file_name+'compressed.jpg')
            image_tools.compressFile(file_path,dest,quality=50,resize=200)
            file_path = dest
            time_stat['Compress/resize image'] = time.time()-t
        # 3: to pdf 
        if self.debug: print('\tConvert image to pdf files')
        t = time.time()
        if self.settings['output_images']: shutil.copy2(file_path,self.output_image_location)
        if self.settings['output_pdf']:
            output_pdf = os.path.join(self.dest_folder,file_name+'.pdf')
            image_tools.compressFile(file_path,output_pdf)
        time_stat['Convert to pdf'] = time.time()-t
        return time_stat
        
    def getImageInformation(self):
        valid_exts = self.settings['valid_exts']   
        # Get paths to all images
        file_paths = [os.path.join(self.source_folder,f) 
                      for f in sorted(os.listdir(self.source_folder))
                      if os.path.splitext(f)[-1] in valid_exts]
        # break if no images in folder
        if len(file_paths) == 0: return
        # place binding in a separate list
        if self.settings['has_binding']:
            self.bindings = [file_paths[0]]+[file_paths[-1]]
            file_paths = file_paths[1:-1]
        for p in file_paths:
            img_size = fs.getFileSize(p)
            img_w,img_h = image_tools.getImageDimensions(p)
            self.img_proc_info['images'][p] = {'crop_coordinates':{},
                                               'image_width':img_w,
                                               'image_height':img_h,
                                               'file_size': img_size,
                                               'deskew_angle':0,
                                               'r_crop':True, # right margin cropImage?
                                               't_crop':True, # top margin cropImage?
                                               'l_crop':True, # left margin cropImage?
                                               'b_crop':True, # bottom margin cropImage?
                                               'deskewImage':True, # deskewImage image?
                                               'spread':False, # is image a spread (opslag)?
                                               }
    def locate_spreads(self):
        '''
        Detect whether an image is a spread (da: opslag) 
        '''
        if self.debug: print('Locating spreads')
        heights = [x['image_height'] 
                   for x in self.img_proc_info['images'].values()
                   if isinstance(x['image_height'],int)]
        widths = [x['image_width'] 
                  for x in self.img_proc_info['images'].values()
                  if isinstance(x['image_width'],int)]
        heights_middle = int(len(heights)/2)
        widths_middle = int(len(widths)/2)
        height_mean = sorted(heights)[heights_middle]
        width_mean = sorted(widths)[widths_middle]
        limit_adjust = self.settings['spread_select_limit_adjust']
        height_mean_limit = height_mean * limit_adjust
        width_mean_limit = width_mean * limit_adjust
        image_paths = sorted(self.img_proc_info['images'].keys())
        for image_path in image_paths:
            height = self.img_proc_info['images'][image_path]['image_height']
            width = self.img_proc_info['images'][image_path]['image_width']
            if height > height_mean_limit or width > width_mean_limit:
                self.img_proc_info['images'][image_path]['spread'] = True
                if self.debug:
                    print('\t{0} detected as a spread.'.format(image_path))
                    msg = ('\tImage width: {0}, width limit: {1}, '
                           'image height: {2}, height limit: {3}.')
                    print(msg.format(width,width_mean_limit,height,height_mean_limit))
    
    def getCropCoordinates(self):
        image_paths = sorted(self.img_proc_info['images'].keys())
        debug_pivot = self.settings['debug_pivot']
        if self.debug: print('Get cropImage coordinates')
        for image_path in image_paths:
            w = self.img_proc_info['images'][image_path]['image_width']
            h = self.img_proc_info['images'][image_path]['image_height']
            time_stat = {}
            t = time.time()
            if self.settings['bw_for_innercrop']:
                threshold = self.settings['innercrop_bw_src_threshold']
                file_name,_ = os.path.splitext(os.path.basename(src))
                dest = os.path.join(self.temp_folder,file_name+'_bw_for_innercrop.tif')
                src = image_tools.convertToBw(image_path,dest,threshold=threshold)
            else:
                src = image_path
            time_stat['BW to get cropImage coordinates'] = time.time()-t
            t = time.time()
            fuzzval = self.settings['innercrop_fuzzval']
            mode = self.settings['innercrop_mode']
            _,coordinates = image_tools.inner_crop(src,self.temp_folder,w=w,h=h,mode=mode,fuzzval=fuzzval)
            self.img_proc_info['images'][image_path]['crop_coordinates'] = coordinates
            time_stat['Get cropImage coordinates'] = time.time()-t
            fs.clear_folder(self.temp_folder)
            self.add_to_avg_time_stat(time_stat)
            if self.debug:
                count = self.img_proc_info['avg_time_stat']['Get cropImage coordinates'][1]
                avg = self.img_proc_info['avg_time_stat']['Get cropImage coordinates'][2]
                if (count%debug_pivot) == 0: # log for every 10 processed iamges
                    left = len(image_paths)-count
                    time_used = get_delta_time(count*avg)
                    time_left = get_delta_time(left*avg)
                    msg = ('\t{0} images cropped, {1} images left, '
                           '{2} time elapsed, {3} est. time left.')
                    print(msg.format(count,left,time_used,time_left))

    def set_crop(self):
        if self.debug: print('Setting cropImage for images')
        c_list = [x['crop_coordinates'] 
                  for x in self.img_proc_info['images'].values()
                  if 'l_crop' in x['crop_coordinates']]
        limit_adjust = self.settings['crop_select_limit_adjust']#1.75 # 75%
        #type = self.settings['crop_select_limit_type']
        # get sorted lists of all the margin crops to get median
        # only take into consideration crops with more than 5 px
        # (for some reason no cropImage can be set to 1px - less than 0 is err anyway)
        l_crops = sorted([x['l_crop'] for x in c_list if x['l_crop'] >5])
        if len(l_crops) > 0:
            l_crop_avg = round(sum(l_crops)/len(l_crops),3)
            l_crop_avg_adj = l_crop_avg * limit_adjust
            l_crop_mean = l_crops[int(len(l_crops)/2)]
            l_crop_mean_adj = l_crop_mean * limit_adjust
            l_crop_limit = l_crop_avg_adj if type == 'avg' else l_crop_mean_adj
            l_crop_limit = round(l_crop_limit,3)
        else:
            l_crop_limit = 0
        if self.debug:
            msg = '\tLeft cropImage limit: {0}. Mean: {1}({2}). Avg: {3}({4})'
            print(msg.format(l_crop_limit,l_crop_mean,l_crop_mean_adj,l_crop_avg,l_crop_avg_adj))

        t_crops = sorted([x['t_crop'] for x in c_list if x['t_crop'] >5])
        if len(t_crops) > 0:
            t_crop_avg = round(sum(t_crops)/len(t_crops),3)
            t_crop_avg_adj = t_crop_avg * limit_adjust
            t_crop_mean = t_crops[int(len(t_crops)/2)]
            t_crop_mean_adj = t_crop_mean * limit_adjust
            t_crop_limit = t_crop_avg_adj if type == 'avg' else t_crop_mean_adj
            t_crop_limit = round(t_crop_limit,3)
        else:
            t_crop_limit = 0
        if self.debug:
            msg = '\tTop cropImage limit: {0}. Mean: {1}({2}). Avg: {3}({4})'
            print(msg.format(t_crop_limit,t_crop_mean,t_crop_mean_adj,t_crop_avg,t_crop_avg_adj))

        r_crops = sorted([x['r_crop'] for x in c_list if x['r_crop'] >5])
        if len(r_crops) > 0:
            r_crop_avg = round(sum(r_crops)/len(r_crops),3)
            r_crop_avg_adj = r_crop_avg * limit_adjust
            r_crop_mean = r_crops[int(len(r_crops)/2)]
            r_crop_mean_adj = r_crop_mean * limit_adjust
            r_crop_limit = r_crop_avg_adj if type == 'avg' else r_crop_mean_adj
            r_crop_limit = round(r_crop_limit,3)
        else:
            r_crop_limit = 0
        if self.debug:
            msg = '\tRight cropImage limit: {0}. Mean: {1}({2}). Avg: {3}({4})'
            print(msg.format(r_crop_limit,r_crop_mean,r_crop_mean_adj,r_crop_avg,r_crop_avg_adj))

        b_crops = sorted([x['b_crop'] for x in c_list if x['b_crop'] >5])
        if len(b_crops) > 0:
            b_crop_avg = round(sum(b_crops)/len(b_crops),3)
            b_crop_avg_adj = b_crop_avg * limit_adjust
            b_crop_mean = b_crops[int(len(b_crops)/2)]
            b_crop_mean_adj = b_crop_mean * limit_adjust
            b_crop_limit = b_crop_avg_adj if type == 'avg' else b_crop_mean_adj
            b_crop_limit = round(b_crop_limit,3)
        else:
            b_crop_limit = 0
        if self.debug:
            msg = '\tBottom cropImage limit: {0}. Mean: {1}({2}). Avg: {3}({4})'
            print(msg.format(b_crop_limit,b_crop_mean,b_crop_mean_adj,b_crop_avg,b_crop_avg_adj))

        image_paths = sorted(self.img_proc_info['images'].keys())
        for image_path in image_paths:
            if self.debug: print('\tSelect crops for: {0}'.format(os.path.basename(image_path)))
            if (self.settings['spread_detection'] and
                self.img_proc_info['images'][image_path]['spread']):
                # Spread (da: opslag) -> no cropping
                self.img_proc_info['images'][image_path]['l_crop'] = False
                self.img_proc_info['images'][image_path]['t_crop'] = False
                self.img_proc_info['images'][image_path]['r_crop'] = False
                self.img_proc_info['images'][image_path]['b_crop'] = False
                if self.debug: print('\t\tImage is a spread, no cropImage')
                continue
            width = self.img_proc_info['images'][image_path]['image_width']
            height = self.img_proc_info['images'][image_path]['image_height']
            crop_info = self.img_proc_info['images'][image_path]['crop_coordinates']
            if self.debug: print('\t\t{0}'.format(crop_info))
            if self.debug: print('\t\tWidth: {0}, height: {1}'.format(width,height))
            l_crop = self.img_proc_info['images'][image_path]['crop_coordinates']['l_crop']
            t_crop = self.img_proc_info['images'][image_path]['crop_coordinates']['t_crop']
            r_crop = self.img_proc_info['images'][image_path]['crop_coordinates']['r_crop']
            b_crop = self.img_proc_info['images'][image_path]['crop_coordinates']['b_crop']
            # Heuristic: for each margin, if absolute cropImage if higher than 2 
            # times the limit, then set it to the avgerage cropImage for that margin.
            new_crop_limit_adjust = 1 
            if (l_crop > l_crop_limit or l_crop < 5):
                if abs(l_crop) > (l_crop_limit*new_crop_limit_adjust):
                    # Recalculate nw_x: equal l_crop_avg
                    self.img_proc_info['images'][image_path]['crop_coordinates']['l_crop'] = l_crop_avg
                    self.img_proc_info['images'][image_path]['crop_coordinates']['nw_x'] = l_crop_avg
                    if self.debug: print('\t\tAvg left cropImage chosen instead: {0}->{1}'.format(l_crop,int(l_crop_avg)))
                else:
                    self.img_proc_info['images'][image_path]['l_crop'] = False
                    if self.debug: print('\t\tNo left cropImage')
            if (t_crop > t_crop_limit or t_crop < 5):
                if abs(t_crop) > (t_crop_limit*new_crop_limit_adjust):
                    # Recalculate nw_y: equal t_crop_avg
                    self.img_proc_info['images'][image_path]['crop_coordinates']['nw_y'] = t_crop_avg
                    self.img_proc_info['images'][image_path]['crop_coordinates']['t_crop'] = t_crop_avg
                    if self.debug: print('\t\tAvg top cropImage chosen instead: {0}->{1}'.format(t_crop,int(t_crop_avg)))
                else:
                    self.img_proc_info['images'][image_path]['t_crop'] = False
                    if self.debug: print('\t\tNo top cropImage')
            if (r_crop > r_crop_limit or r_crop < 5):
                if abs(r_crop) > (r_crop_limit*new_crop_limit_adjust):
                    # Recalculate se_x: equal width - r_crop_avg
                    self.img_proc_info['images'][image_path]['crop_coordinates']['se_x'] = width-r_crop_avg
                    self.img_proc_info['images'][image_path]['crop_coordinates']['r_crop'] = r_crop_avg
                    if self.debug: print('\t\tAvg right cropImage chosen instead: {0}->{1}'.format(r_crop,int(r_crop_avg)))
                else:
                    self.img_proc_info['images'][image_path]['r_crop'] = False
                    if self.debug: print('\t\tNo right cropImage')
            if (b_crop > b_crop_limit or b_crop < 5):
                if abs(b_crop) > (b_crop_limit*new_crop_limit_adjust):
                    # Recalculate se_y: equal height - b_crop_avg
                    self.img_proc_info['images'][image_path]['crop_coordinates']['se_y'] = height - b_crop_avg
                    self.img_proc_info['images'][image_path]['crop_coordinates']['b_crop'] = b_crop_avg
                    if self.debug: print('\t\tAvg bottom cropImage chosen instead: {0}->{1}'.format(b_crop,int(b_crop_avg)))
                else:
                    self.img_proc_info['images'][image_path]['b_crop'] = False
                    if self.debug: print('\t\tNo bottom cropImage')
    
    def get_deskew_angles(self):
        debug_pivot = self.settings['debug_pivot']
        image_paths = self.img_proc_info['images'].keys()
        if self.debug: print('Get deskewImage angles for {0} images'.format(len(image_paths)))
        for image_path in image_paths:
            time_stat = {}
            # Use alternative image - cropped tif-files
            src = self.img_proc_info['images'][image_path]['image_for_deskew']
            t = time.time()
            angle = image_tools.getDeskewAngle(src)
            self.img_proc_info['images'][image_path]['deskew_angle'] = angle
            time_stat['Get deskewImage angle'] = time.time()-t
            self.add_to_avg_time_stat(time_stat)
            if self.debug:
                count = self.img_proc_info['avg_time_stat']['Get deskewImage angle'][1]
                avg = self.img_proc_info['avg_time_stat']['Get deskewImage angle'][2]
                if (count%debug_pivot) == 0: # log for every 10 processed iamges
                    left = len(image_paths)-count
                    time_used = get_delta_time(count*avg)
                    time_left = get_delta_time(left*avg)
                    msg = ('\t{0} images deskewed, {1} images left, '
                           '{2} time elapsed, {3} est. time left.')
                    print(msg.format(count,left,time_used,time_left))

    def set_deskew(self):
        if self.debug: print('Set deskewImage for images')
        limit_adjust = self.settings['deskew_select_limit_adjust']#1.75 # 75%
        image_paths = sorted(self.img_proc_info['images'].keys())
        
        #angles = sorted(list(map(lambda x: x['deskew_angle'],img_info['images'].values())))
        # only find mean from the images that are actually set to deskewImage
        
        # Set the angles to absolute, so the mean wont be zero
        
        # TODO: consider using avg instead. Angles may lay on an asymptote curve
        angles = sorted([abs(a['deskew_angle']) for a in self.img_proc_info['images'].values()
                         if a['deskew_angle'] != 0])
        avg = sum(angles)/len(angles)
        avg_limit = avg * limit_adjust
        # Calculate mean and adjusted mean limit
        middle = int(len(angles)/2)
        mean = angles[middle]
        mean_limit = mean * limit_adjust
        if self.debug: 
            print('\tMean deskewImage: {0} - adjust with {1}% = {2}'.format(round(mean,3),limit_adjust*100,round(mean_limit,3)))
            print('\tAvg deskewImage: {0} - adjust with {1}% = {2}'.format(round(avg,3),limit_adjust*100,round(avg_limit,3)))
        for image_path in image_paths:
            if self.debug: print('\tSelect deskewImage for {0}'.format(image_path))
            if (self.settings['spread_detection'] and
                self.img_proc_info['images'][image_path]['spread']):
                self.img_proc_info['images'][image_path]['deskewImage'] = False
                if self.debug: print('\t\tImage is a spread, no deskewImage')
                continue
                
            angle = round(self.img_proc_info['images'][image_path]['deskew_angle'],3)
            if self.debug:
                l = mean_limit if self.settings['deskew_select_limit_type'] == 'mean' else avg_limit
                l = round(l,3)
                print('\t\tAngle: {0} ({1}<{2}?)'.format(angle,abs(angle),l))
            if angle == 0:
                self.img_proc_info['images'][image_path]['deskewImage'] = False
                if self.debug: print('\t\tAngle zero, no deskewImage')
            elif abs(angle) < self.settings['deskew_select_abs_limit']:
                self.img_proc_info['images'][image_path]['deskewImage'] = False
                if self.debug: print('\t\tAngle below margin value {0}, no deskewImage'.format(self.settings['deskew_select_abs_limit']))
            else:
                if (self.settings['deskew_select_limit_type'] == 'mean' and
                    (angle < -mean_limit or angle > mean_limit)):
                    self.img_proc_info['images'][image_path]['deskewImage'] = False
                    if self.debug: print('\t\tNo deskewImage, above limit')
                elif (self.settings['deskew_select_limit_type'] == 'avg' and
                    (angle < -avg_limit or angle > avg_limit)):
                    self.img_proc_info['images'][image_path]['deskewImage'] = False
                    if self.debug: print('\t\tNo deskewImage, above limit')
                elif self.debug: print('\t\tPerform deskewImage')
                
    def create_temp_crops(self):
        '''
        This methods creates cropped tif-files for the deskewImage selector. This 
        because the deskewImage may function better, if margins are removed beforehand.    
        
        The cropped tif files are placed in the temp folder and the paths to these
        are placed in the img_info for the deskewImage funtion to use.
        '''
        image_paths = sorted(self.img_proc_info['images'].keys())
        for image_path in image_paths:
            file_name = os.path.basename(image_path)
            file_name,_ = os.path.splitext(file_name)
            dest = os.path.join(self.temp_folder,file_name+'.tif')
            info = self.img_proc_info['images'][image_path]
            image_tools.cropImage(image_path,self.temp_folder,info,dest,to_tif=True)
            self.img_proc_info['images'][image_path]['image_for_deskew'] = dest 
    
    def add_to_avg_time_stat(self,proc_time_stat):
        for k,v in proc_time_stat.items():
            if k in self.img_proc_info['avg_time_stat']:
                self.img_proc_info['avg_time_stat'][k][0] += v # sum of secs
                self.img_proc_info['avg_time_stat'][k][1] += 1 # counts
                sum = self.img_proc_info['avg_time_stat'][k][0]
                count = self.img_proc_info['avg_time_stat'][k][1]
                avg = sum/count
                self.img_proc_info['avg_time_stat'][k][2] = avg # avg
            else:
                self.img_proc_info['avg_time_stat'][k] = []
                self.img_proc_info['avg_time_stat'][k].append(v) # sum of secs
                self.img_proc_info['avg_time_stat'][k].append(1) # counts
                self.img_proc_info['avg_time_stat'][k].append(v) # avg
    

    
def get_delta_time(s):
    if s == 0: return '0 ms'
    t = int(s * 100) / 100.0
    h, remainder = divmod(t, 3600)
    remainder = round(remainder,3)
    m, remainder = divmod(remainder, 60)
    s, ms = divmod(remainder, 1)
    ms = round(ms,2)*100
    ret_str = ''
    if h > 0:
        ret_str += str(int(h))+' h, '
    if m > 0:
        ret_str += str(int(m))+' m, '
    if s > 0 or ms > 0:
        if ms > 0:
            ret_str += (str(int(s))+'.'+str(int(ms))+' s')
        else:
            ret_str += str(int(s))+' s'
    return ret_str.rstrip(', ')


if __name__ == '__main__':
    settings = {'temp_location': '/tmp/ramdisk/',
                'output_image_location': '/home/jeel/processed_dod_books',
                'output_images': True,
                'output_pdf': False,
                'debug_pivot': 10, # Print debug for every N images processed
                'has_binding': True,
                'remove_binding': False,
                'valid_exts': '.tif;.jpg'.split(';'),
                'bw_for_innercrop': True,
                'innercrop_bw_src_threshold': 30,
                'innercrop_fuzzval': 75,
                'innercrop_mode': 'box',
                'crop_select_limit_adjust': 3,
                'crop_select_limit_type': 'mean', #use: ['mean','avg']
                'deskew_select_limit_adjust': 5.5, # experience tells that this one should be high
                'deskew_select_limit_type': 'avg', #use: ['mean','avg']
                'deskew_select_abs_limit': 0.1, # If an absolute deskewImage angle is below this, don't deskewImage
                'spread_detection': True, # detect spreads
                'spread_select_limit_adjust': 1.25, # If width or height is N more than mean, image is a spread
                'skip_if_pdf_exists': True
                }
    src = sys.argv[1]
    #folders = [os.path.join(src,f) 
    #           for f in os.listdir(src)
    #           if os.path.isdir(os.path.join(src,f))]
    #for src in sorted(folders):#[src]:#
    folders = [(os.path.join(src,f),len(os.listdir(os.path.join(src,f)))) 
               for f in os.listdir(src)
               if os.path.isdir(os.path.join(src,f))]
    for src, file_count in sorted(folders,key=lambda x:x[1]):#[src]:#
        print('Processing {0} with {1} images'.format(os.path.basename(src),file_count))
        t = time.time()
        ip = ImagePreprocessor(src,settings,debug=True)
        ip.processFolder()
        dt = time.time()-t
        print('{0} processed in {1}, avg. {2} pr page'.format(os.path.basename(src),get_delta_time(dt),get_delta_time(dt/file_count)))