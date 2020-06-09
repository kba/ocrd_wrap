from __future__ import absolute_import

import os.path
from PIL import Image
import numpy as np
from skimage.morphology import (
    remove_small_objects,
    remove_small_holes
)

from ocrd import Processor
from ocrd_utils import (
    getLogger, concat_padded,
    MIMETYPE_PAGE,
    MIME_TO_PIL,
    MIME_TO_EXT
)
from ocrd_modelfactory import page_from_file
from ocrd_models.ocrd_page import (
    LabelType, LabelsType,
    MetadataItemType,
    AlternativeImageType,
    to_xml
)
from .config import OCRD_TOOL

TOOL = 'ocrd-skimage-denoise'
LOG = getLogger('processor.SkimageDenoise')
FALLBACK_FILEGRP_IMG = 'OCR-D-IMG-DEN'

class SkimageDenoise(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(SkimageDenoise, self).__init__(*args, **kwargs)
        if hasattr(self, 'output_file_grp'):
            try:
                self.page_grp, self.image_grp = self.output_file_grp.split(',')
            except ValueError:
                self.page_grp = self.output_file_grp
                self.image_grp = FALLBACK_FILEGRP_IMG
                LOG.info("No output file group for images specified, falling back to '%s'",
                         FALLBACK_FILEGRP_IMG)
    
    def process(self):
        """Performs binary denoising of segment or page images with Skimage on the workspace.
        
        Open and deserialize PAGE input files and their respective images,
        then iterate over the element hierarchy down to the requested
        ``level-of-operation`` in the element hierarchy.
        
        For each segment element, retrieve a segment image according to
        the layout annotation (from an existing AlternativeImage, or by
        cropping via coordinates into the higher-level image, and -
        when applicable - deskewing), in binarized form.
        
        Next, denoise the image by removing too small connected components
        with skimage.
        
        Then write the new image to the workspace with the fileGrp USE given
        in the second position of the output fileGrp, or ``OCR-D-IMG-DEN``,
        and an ID based on input file and input element.
        
        Produce a new PAGE output file by serialising the resulting hierarchy.
        """
        oplevel = self.parameter['level-of-operation']
        
        for (n, input_file) in enumerate(self.input_files):
            page_id = input_file.pageId or input_file.ID
            file_id = input_file.ID.replace(self.input_file_grp, self.image_grp)
            if file_id == input_file.ID:
                file_id = concat_padded(self.image_grp, n)
            LOG.info("INPUT FILE %i / %s", n, page_id)
            
            pcgts = page_from_file(self.workspace.download_file(input_file))
            page = pcgts.get_Page()
            metadata = pcgts.get_Metadata() # ensured by from_file()
            metadata.add_MetadataItem(
                MetadataItemType(type_="processingStep",
                                 name=self.ocrd_tool['steps'][0],
                                 value=TOOL,
                                 Labels=[LabelsType(
                                     externalModel="ocrd-tool",
                                     externalId="parameters",
                                     Label=[LabelType(type_=name,
                                                      value=self.parameter[name])
                                            for name in self.parameter.keys()])]))
            
            for page in [page]:
                page_image, page_coords, page_image_info = self.workspace.image_from_page(
                    page, page_id, feature_selector='binarized')
                if self.parameter['dpi'] > 0:
                    dpi = self.parameter['dpi']
                    LOG.info("Page '%s' images will use %d DPI from parameter override", page_id, dpi)
                elif page_image_info.resolution != 1:
                    dpi = page_image_info.resolution
                    if page_image_info.resolutionUnit == 'cm':
                        dpi = round(dpi * 2.54)
                    LOG.info("Page '%s' images will use %d DPI from image meta-data", page_id, dpi)
                else:
                    dpi = 300
                    LOG.info("Page '%s' images will use 300 DPI from fall-back", page_id)
                maxsize = self.parameter['maxsize'] # in pt
                maxsize *= dpi/72 # in px
                #maxsize **= 2 # area
                
                if oplevel == 'page':
                    self._process_segment(page, page_image, page_coords, maxsize,
                                          "page '%s'" % page_id, input_file.pageId,
                                          file_id)
                    continue
                regions = page.get_AllRegions(classes=['Text'])
                if not regions:
                    LOG.warning("Page '%s' contains no text regions", page_id)
                for region in regions:
                    region_image, region_coords = self.workspace.image_from_segment(
                        region, page_image, page_coords, feature_selector='binarized')
                    if oplevel == 'region':
                        self._process_segment(region, region_image, region_coords, maxsize,
                                              "region '%s'" % region.id, None,
                                              file_id + '_' + region_id)
                        continue
                    lines = region.get_TextLine()
                    if not lines:
                        LOG.warning("Region '%s' contains no text lines", region.id)
                    for line in lines:
                        line_image, line_coords = self.workspace.image_from_segment(
                            line, region_image, region_coords, feature_selector='binarized')
                        if oplevel == 'line':
                            self._process_segment(line, line_image, line_coords, maxsize,
                                                  "line '%s'" % line.id, None,
                                                  file_id + '_' + line.id)
                            continue
                        words = line.get_Word()
                        if not words:
                            LOG.warning("Line '%s' contains no words", line.id)
                        for word in words:
                            word_image, word_coords = self.workspace.image_from_segment(
                                word, line_image, line_coords, feature_selector='binarized')
                            if oplevel == 'word':
                                self._process_segment(word, word_image, word_coords, maxsize,
                                                      "word '%s'" % word.id, None,
                                                      file_id + '_' + word.id)
                                continue
                            glyphs = word.get_Glyph()
                            if not glyphs:
                                LOG.warning("Word '%s' contains no glyphs", word.id)
                            for glyph in glyphs:
                                glyph_image, glyph_coords = self.workspace.image_from_segment(
                                    glyph, word_image, word_coords, feature_selector='binarized')
                                self._process_segment(glyph, glyph_image, glyph_coords, maxsize,
                                                      "glyph '%s'" % glyph.id, None,
                                                      file_id + '_' + glyph.id)
            
            # Use input_file's basename for the new file -
            # this way the files retain the same basenames:
            file_id = input_file.ID.replace(self.input_file_grp, self.page_grp)
            if file_id == input_file.ID:
                file_id = concat_padded(self.page_grp, n)
            self.workspace.add_file(
                ID=file_id,
                file_grp=self.page_grp,
                pageId=input_file.pageId,
                mimetype=MIMETYPE_PAGE,
                local_filename=os.path.join(self.page_grp,
                                            file_id + '.xml'),
                content=to_xml(pcgts))
    
    def _process_segment(self, segment, image, coords, maxsize, where, page_id, file_id):
        features = coords['features'] # features already applied to image
        features += ',despeckled'
        array = np.array(image)
        # suppress bg specks in fg (holes in binary-inverted)
        remove_small_objects(array, min_size=maxsize, in_place=True)
        # suppress fg specks in bg (blobs in binary-inverted)
        remove_small_holes(array, area_threshold=maxsize, in_place=True)
        image = Image.fromarray(array)
        # annotate results
        file_path = self.workspace.save_image_file(
            image,
            file_id,
            file_grp=self.image_grp,
            page_id=page_id)
        segment.add_AlternativeImage(AlternativeImageType(
            filename=file_path, comments=features))